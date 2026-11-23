"""Estado diario persistente del autopiloto: `estado_autopiloto.json`.

Que guarda, por dia (YYYY-MM-DD):

* `fotos` / `videos`: cuantas se han publicado ya (se recalculan siempre desde `publicaciones`).
* `publicaciones`: cada una con tipo, franja, hora, archivo, id de Meta y estado (`ok` o `ambiguo`).
* `franjas`: el estado de cada franja horaria, con clave `foto@11:30`: `programada`, `en_curso`, `ejecutada`, `ambigua`,
  `error` u `omitida` (con su motivo).

Garantias para no duplicar publicaciones:

* **Escritura atomica**: se escribe un temporal, se fuerza a disco (`fsync`) y se sustituye con `os.replace`; antes se deja
  una copia `.bak`. Si el PC se apaga a mitad de un guardado queda el archivo anterior entero, nunca uno a medias.
* **Anotacion previa** (`begin`): justo antes de hablar con Meta la franja queda como `en_curso` en disco. Si el programa
  muere mientras publica, al volver a abrirlo esa franja pasa a `ambigua` (pudo publicarse) y NO se repite sola.
* Un archivo dañado se aparta como `*.corrupto-*` y se recupera la copia `.bak`.
* El formato antiguo (`autopiloto_estado.json`) se migra solo la primera vez.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import time
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

LOG = logging.getLogger("autopiloto")
VERSION = 2
KEEP_DAYS = 45
MAX_ATTEMPTS = 3                              # una franja con error se reintenta al reiniciar hasta este numero de veces
PUBLISHED = ("ok", "ambiguo")                 # publicaciones que cuentan para el limite diario
CONSUMED = ("ejecutada", "ambigua", "en_curso")    # franjas que no se vuelven a lanzar nunca
PLURAL = {"foto": "fotos", "video": "videos"}


# =========================================================================== escritura atomica
def atomic_write(path: Path, text: str, backup: bool = True) -> None:
    """Escribe `text` en `path` de forma atomica: o queda el contenido viejo entero o el nuevo entero."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    if backup and path.exists():
        try:
            shutil.copyfile(path, path.with_name(path.name + ".bak"))
        except OSError:
            pass                                   # la copia es un extra: no impide guardar
    for attempt in range(8):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:                    # Windows: un antivirus o el indexador tiene el archivo abierto un instante
            if attempt == 7:
                raise
            time.sleep(0.05 * (attempt + 1))


def _iso(day) -> str:
    return day.isoformat() if hasattr(day, "isoformat") else str(day)


def _new_day() -> dict:
    return {"fotos": 0, "videos": 0, "publicaciones": [], "franjas": {}}


def cover_note(pub: dict) -> str:
    return "cubierta por una publicación anterior" if pub.get("franja") == "migrado" else "cubierta por una publicación manual"


def slot_key(kind: str, franja: str) -> str:
    return f"{kind}@{franja}"


# =========================================================================== el estado
class State:
    """Estado del autopiloto en un JSON. Con `readonly=True` solo lee (para `--estado`: no toca nada del archivo)."""

    def __init__(self, path: Path, *, legacy: Path | None = None, readonly: bool = False, clock=datetime.now):
        self.path, self.readonly, self.clock = Path(path), readonly, clock
        self._defer, self._dirty = 0, False
        self.data = self._load(Path(legacy) if legacy else None)

    # ------------------------------------------------------------------ carga y recuperacion
    def _load(self, legacy: Path | None) -> dict:
        data, changed = None, False
        if self.path.exists():
            data, changed = self._read_valid()
        if data is None and legacy is not None and legacy != self.path and legacy.exists():
            data, changed = self._from_legacy(legacy), True
        if data is None:
            data = {"version": VERSION, "dias": {}}
        data["version"] = VERSION
        for key, day in list(data["dias"].items()):
            data["dias"][key] = self._normalize(day)
        if self._recover_interrupted(data):
            changed = True
        if changed:
            self._dirty = True
        self._sync_counts(data)
        if changed and not self.readonly:
            self.data = data
            self.save()
        return data

    def _read_valid(self):
        """-> (datos, hay_que_guardar). Si el principal esta dañado se aparta y se prueba la copia .bak."""
        bak = self.path.with_name(self.path.name + ".bak")
        for cand in (self.path, bak):
            try:
                parsed = json.loads(cand.read_text("utf-8-sig"))
                if not isinstance(parsed, dict) or not isinstance(parsed.get("dias", {}), dict):
                    raise ValueError("estructura no válida")
            except FileNotFoundError:
                continue
            except (OSError, ValueError) as e:
                LOG.error("%s está dañado (%s).", cand.name, e)
                if cand == self.path and not self.readonly:
                    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                    try:
                        os.replace(cand, cand.with_name(f"{cand.name}.corrupto-{stamp}"))
                    except OSError:
                        pass
                continue
            parsed.setdefault("dias", {})
            if cand == bak:
                LOG.warning("Se recuperó el estado desde la copia %s.", bak.name)
            return parsed, cand == bak
        LOG.error("No se pudo leer el estado de %s: se parte de cero. Revisa tu página de Facebook antes de publicar a mano "
                  "para no duplicar lo de hoy.", self.path.name)
        return None, False

    def _from_legacy(self, legacy: Path) -> dict | None:
        """Migra el formato v1 (`autopiloto_estado.json`: dias -> tipo -> estado) conservando lo ya publicado."""
        try:
            old = json.loads(legacy.read_text("utf-8-sig"))
            days = old.get("dias", {})
        except (OSError, ValueError, AttributeError):
            LOG.warning("No se pudo migrar el estado antiguo %s (se ignora).", legacy.name)
            return None
        data, moved = {"version": VERSION, "dias": {}}, 0
        for iso, kinds in days.items():
            for kind, e in (kinds or {}).items():
                if kind not in PLURAL or not isinstance(e, dict) or e.get("estado") not in PUBLISHED:
                    continue
                day = data["dias"].setdefault(iso, _new_day())
                day["publicaciones"].append({"tipo": kind, "franja": "migrado", "hora": e.get("hora", ""),
                                             "archivo": e.get("archivo", ""), "id": e.get("id"), "estado": e["estado"]})
                moved += 1
        LOG.info("Estado antiguo %s migrado a %s: %d publicación(es) conservada(s).", legacy.name, self.path.name, moved)
        return data

    @staticmethod
    def _normalize(day) -> dict:
        day = day if isinstance(day, dict) else {}
        base = _new_day()
        base.update({k: v for k, v in day.items() if k in base})
        if not isinstance(base["publicaciones"], list):
            base["publicaciones"] = []
        if not isinstance(base["franjas"], dict):
            base["franjas"] = {}
        base["publicaciones"] = [p for p in base["publicaciones"] if isinstance(p, dict) and p.get("tipo") in PLURAL]
        return base

    def _recover_interrupted(self, data: dict) -> bool:
        """`en_curso` al arrancar = el programa murio publicando: pudo salir, se marca ambigua y no se repite."""
        if self.readonly:
            return False
        changed = False
        for iso, day in data["dias"].items():
            for key, slot in day["franjas"].items():
                if not isinstance(slot, dict) or slot.get("estado") != "en_curso":
                    continue
                kind, _, franja = key.partition("@")
                slot["estado"] = "ambigua"
                slot["error"] = "el programa se cerró mientras publicaba"
                day["publicaciones"].append({"tipo": kind, "franja": franja, "hora": slot.get("hora", ""),
                                             "archivo": slot.get("archivo", ""), "id": None, "estado": "ambiguo",
                                             "error": slot["error"]})
                LOG.warning("%s %s: el programa se cerró mientras publicaba %s. Puede haberse publicado: revisa tu página; "
                            "no se repite para no duplicar.", iso, key, slot.get("archivo") or "(sin archivo)")
                changed = True
        return changed

    # ------------------------------------------------------------------ guardado
    @staticmethod
    def _sync_counts(data: dict) -> None:
        for day in data["dias"].values():
            for kind, name in PLURAL.items():
                day[name] = sum(1 for p in day["publicaciones"] if p.get("tipo") == kind and p.get("estado") in PUBLISHED)

    def save(self) -> None:
        if self.readonly or not self._dirty:
            return
        keep = sorted(self.data["dias"])[-KEEP_DAYS:]
        self.data["dias"] = {k: self.data["dias"][k] for k in keep}
        self._sync_counts(self.data)
        atomic_write(self.path, json.dumps(self.data, ensure_ascii=False, indent=1))
        self._dirty = False

    def _changed(self) -> None:
        self._dirty = True
        if not self._defer:
            self.save()

    @contextmanager
    def batch(self):
        """Agrupa varios cambios en un solo guardado."""
        self._defer += 1
        try:
            yield self
        finally:
            self._defer -= 1
            if not self._defer:
                self.save()

    # ------------------------------------------------------------------ consultas
    def _get(self, day) -> dict | None:
        return self.data["dias"].get(_iso(day))

    def _day(self, day) -> dict:
        return self.data["dias"].setdefault(_iso(day), _new_day())

    def publications(self, day) -> list:
        return list((self._get(day) or {}).get("publicaciones", []))

    def count(self, day, kind: str | None = None) -> int:
        """Publicaciones del dia (ok o ambiguas), de un tipo o de todos."""
        return sum(1 for p in self.publications(day)
                   if p.get("estado") in PUBLISHED and (kind is None or p.get("tipo") == kind))

    def slot(self, day, kind: str, franja: str) -> dict | None:
        found = ((self._get(day) or {}).get("franjas", {})).get(slot_key(kind, franja))
        return dict(found) if found else None

    def uploaded(self, archivo: str) -> bool:
        """¿Este archivo ya se subio alguna vez (en los dias guardados)?"""
        return bool(archivo) and any(p.get("archivo") == archivo and p.get("estado") in PUBLISHED
                                     for d in self.data["dias"].values() for p in d["publicaciones"])

    def _now(self) -> str:
        return self.clock().strftime("%H:%M:%S")

    # ------------------------------------------------------------------ cambios
    def _set_slot(self, day, kind: str, franja: str, entry: dict) -> bool:
        slots = self._day(day)["franjas"]
        key = slot_key(kind, franja)
        if slots.get(key) == entry:
            return False
        slots[key] = entry
        self._changed()
        return True

    def schedule(self, day, kind: str, franja: str, prevista: str) -> None:
        """La franja tiene hora real prevista (hora base + retraso aleatorio): se recuerda por si se reinicia."""
        self._set_slot(day, kind, franja, {"estado": "programada", "prevista": prevista})

    def omit(self, day, kind: str, franja: str, motivo: str) -> None:
        old = self.slot(day, kind, franja)
        if old and old.get("estado") == "omitida" and old.get("motivo") == motivo:
            return
        self._set_slot(day, kind, franja, {"estado": "omitida", "hora": self._now(), "motivo": motivo})

    def begin(self, day, kind: str, franja: str, archivo: str) -> None:
        """Anotacion PREVIA a publicar: queda en disco antes de hablar con Meta (si el programa muere, no se repite)."""
        self._set_slot(day, kind, franja, {"estado": "en_curso", "hora": self._now(), "archivo": archivo})

    def finish(self, day, kind: str, franja: str, estado: str, archivo: str, post_id: str | None = None,
               error: str | None = None) -> None:
        """Resultado de la publicacion: `ok` (publicada) o `ambiguo` (pudo salir). Cuenta para el limite diario."""
        hora = self._now()
        pub = {"tipo": kind, "franja": franja, "hora": hora, "archivo": archivo, "id": post_id, "estado": estado}
        slot = {"estado": "ejecutada" if estado == "ok" else "ambigua", "hora": hora, "archivo": archivo, "id": post_id}
        if error:
            pub["error"] = slot["error"] = error[:300]
        with self.batch():
            self._day(day)["publicaciones"].append(pub)
            self._set_slot(day, kind, franja, slot)
            self._dirty = True

    def cover(self, day, kind: str, franja: str, pub: dict) -> None:
        """Una publicacion sin franja (manual o migrada) cubre esa franja: no se vuelve a lanzar. `pub` es la de `publications()`."""
        pub["cubre"] = franja
        with self.batch():
            self._set_slot(day, kind, franja, {"estado": "ejecutada", "hora": pub.get("hora", ""),
                                               "archivo": pub.get("archivo", ""), "id": pub.get("id"), "nota": cover_note(pub)})
            self._dirty = True

    def release(self, day, kind: str, franja: str) -> None:
        """Fallo temporal (nada llego a Meta): la franja vuelve a estar pendiente."""
        slots = self._day(day)["franjas"]
        if slots.pop(slot_key(kind, franja), None) is not None:
            self._changed()

    def fail(self, day, kind: str, franja: str, error: str, archivo: str | None = None) -> None:
        """Error definitivo (generacion o rechazo de la API): nada se publico. Se cuenta el intento."""
        old = self.slot(day, kind, franja) or {}
        entry = {"estado": "error", "hora": self._now(), "error": str(error)[:300], "intentos": int(old.get("intentos", 0)) + 1}
        if archivo:
            entry["archivo"] = archivo
        self._set_slot(day, kind, franja, entry)
