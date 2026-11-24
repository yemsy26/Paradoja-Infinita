"""Compara las vistas de los Reels que publica el autopiloto con las de los demas (SOLO LECTURA: unicamente peticiones GET).

Sirve para responder, con datos, a «¿los Reels subidos por la API se distribuyen igual que los subidos a mano?»:

* lista los Reels de la pagina con sus vistas, su edad y su origen (autopiloto = esta en `estado_autopiloto.json`);
* resume por grupo (mediana, media, minimo y maximo) usando solo Reels con una edad minima, para comparar lo comparable;
* guarda una *foto* de las vistas en cada ejecucion (`diagnostico_reels.json`, en `.gitignore`) y, con varias, calcula las
  vistas a +1 h y a +24 h de cada Reel, que es lo que hace falta para una prueba A/B limpia;
* no imprime nunca el token: todo lo que sale pasa por `limpiar()` y `GraphClient.get()` elimina los `paging`.

Con el permiso actual (`pages_read_engagement`) Meta solo deja leer el campo `views`; las reproducciones, el tiempo medio visto
y la retencion piden `read_insights` o mirarlos a mano en Meta Business Suite.
"""
from __future__ import annotations

import json
import re
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .envfile import ROOT, redact
from .state import atomic_write

SNAPSHOT_FILE = ROOT / "diagnostico_reels.json"
KEEP_SNAPSHOTS = 400
TIME_FMT = "%Y-%m-%dT%H:%M:%S%z"
CHECKLIST = (
    "Si el autopiloto se queda muy por debajo, comprueba en este orden:",
    "  1. developers.facebook.com > tu app > interruptor «Modo»: ¿está «En desarrollo»? Según la documentación de Meta, solo "
    "los usuarios con rol ven lo que publica una app en ese modo.",
    "  2. Abre el enlace de un Reel del autopiloto en una ventana de incógnito o con una cuenta sin rol: ¿sale «no disponible»?",
    "  3. Pasa la app a modo activo y publica uno por la API: sus vistas deberían crecer como las de los manuales.",
)


def limpiar(text, *secrets) -> str:
    """Texto seguro para imprimir: sin token ni parametros `access_token=`."""
    s = redact(str(text), *secrets)
    s = re.sub(r"access_token=[^&\"'\s]+", "access_token=***", s)
    return re.sub(r"(EAA[A-Za-z0-9]{12})[A-Za-z0-9]+", r"\1***", s)


def parse_time(value: str) -> datetime:
    """`2026-11-24T19:25:11+0000` -> datetime con zona horaria (UTC)."""
    return datetime.strptime(value, TIME_FMT).astimezone(timezone.utc)


# =========================================================================== lectura
@dataclass
class Reel:
    id: str
    created: datetime                         # UTC
    length: float
    views: int | None
    comments: int | None
    origin: str                               # "autopiloto" | "manual" (marcado a mano) | "otro" (anterior o manual)
    archivo: str = ""

    def age_hours(self, now: datetime) -> float:
        return max(0.0, (now - self.created).total_seconds() / 3600)

    @property
    def group(self) -> str:
        return "autopiloto" if self.origin == "autopiloto" else "resto"


def origins_from_state(path: Path) -> dict:
    """{id_de_video: archivo} de lo que publico el autopiloto. Lee el JSON sin tocarlo (ni migrar ni recuperar nada)."""
    try:
        days = json.loads(Path(path).read_text("utf-8-sig")).get("dias", {})
    except (OSError, ValueError, AttributeError):
        return {}
    return {str(p["id"]): p.get("archivo", "") for d in days.values() for p in d.get("publicaciones", [])
            if p.get("tipo") == "video" and p.get("id")}


def collect(client, origins: dict, manual=(), limit: int = 40) -> list:
    """Reels de la pagina (los mas recientes primero) con sus vistas, en una sola lectura. Solo GET.
    (La lectura multiple por `ids` esta obsoleta desde la v26.0; la lista de Reels ya trae `views` y los comentarios.)"""
    items = client.get(f"{client.page_id}/video_reels", limit=limit,
                       fields="id,created_time,length,views,comments.summary(total_count).limit(0)").get("data", [])
    manual = {str(m) for m in manual}
    reels = []
    for it in items:
        vid = str(it["id"])
        c = it.get("comments")
        comments = c.get("summary", {}).get("total_count") if isinstance(c, dict) else None
        origin = "autopiloto" if vid in origins else "manual" if vid in manual else "otro"
        reels.append(Reel(vid, parse_time(it["created_time"]), float(it.get("length") or 0), it.get("views"), comments, origin,
                          origins.get(vid, "")))
    return sorted(reels, key=lambda r: r.created, reverse=True)


# =========================================================================== fotos (snapshots) para medir a +1 h y +24 h
def load_snapshots(path: Path | None = None) -> list:
    try:
        data = json.loads(Path(path or SNAPSHOT_FILE).read_text("utf-8"))
        return data.get("snapshots", []) if isinstance(data, dict) else []
    except (OSError, ValueError):
        return []


def save_snapshot(reels: list, now: datetime, path: Path | None = None) -> int:
    """Anade una foto de las vistas actuales (atomico). Devuelve cuantas fotos hay guardadas."""
    path = Path(path or SNAPSHOT_FILE)
    snaps = load_snapshots(path)
    snaps.append({"ts": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
                  "views": {r.id: r.views for r in reels if r.views is not None}})
    snaps = snaps[-KEEP_SNAPSHOTS:]
    atomic_write(path, json.dumps({"version": 1, "snapshots": snaps}, ensure_ascii=False, indent=1), backup=False)
    return len(snaps)


def views_at(snapshots: list, reel: Reel, hours: float, tolerance_hours: float):
    """Vistas del Reel en la foto mas cercana a `creado + hours` (dentro de la tolerancia), o None si no hay ninguna."""
    target, best = reel.created + timedelta(hours=hours), None
    for s in snapshots:
        value = s.get("views", {}).get(reel.id)
        if value is None:
            continue
        gap = abs((datetime.fromisoformat(s["ts"]) - target).total_seconds()) / 3600
        if gap <= tolerance_hours and (best is None or gap < best[0]):
            best = (gap, value)
    return best[1] if best else None


# =========================================================================== estadisticas
def summarize(reels: list, now: datetime, min_age_hours: float = 6.0) -> dict:
    """Por grupo («autopiloto» y «resto»): Reels totales, recientes (aun sin edad) y estadisticas de los maduros."""
    out = {}
    for group in ("autopiloto", "resto"):
        rs = [r for r in reels if r.group == group and r.views is not None]
        mature = [r.views for r in rs if r.age_hours(now) >= min_age_hours]
        out[group] = {"n": len(mature), "recientes": len(rs) - len(mature), "total": len(rs),
                      "mediana": statistics.median(mature) if mature else None,
                      "media": round(statistics.mean(mature), 1) if mature else None,
                      "min": min(mature) if mature else None, "max": max(mature) if mature else None}
    return out


def verdict(summary: dict, min_age_hours: float = 6.0) -> list:
    """Lectura prudente de la comparacion. No afirma causas: solo cuantifica la diferencia."""
    a, b = summary["autopiloto"], summary["resto"]
    if a["n"] < 2 or b["n"] < 3:
        return [f"Todavía hay pocos Reels con más de {min_age_hours:g} h para concluir (hacen falta ≥2 del autopiloto y ≥3 del resto: "
                f"hay {a['n']} y {b['n']})."]
    ratio = (a["mediana"] or 0) / max(b["mediana"] or 0, 1)
    head = f"Mediana de vistas: autopiloto {a['mediana']:g} frente a {b['mediana']:g} del resto ({ratio:.0%})."
    if ratio < 0.10:
        return [head, "Diferencia muy grande. El archivo no parece el motivo (se genera y codifica igual); lo más probable es la visibilidad "
                      "de lo que publica la API.", *CHECKLIST]
    if ratio < 0.50:
        return [head, "Diferencia apreciable: repite la medición con más Reels antes de cambiar nada.", *CHECKLIST[:1]]
    return [head, "Sin diferencia relevante entre las dos vías."]


# =========================================================================== informe
def _fmt_age(hours: float) -> str:
    return f"{hours * 60:.0f} min" if hours < 1 else f"{hours:.1f} h" if hours < 48 else f"{hours / 24:.1f} d"


def render(reels: list, now: datetime, snapshots: list, detail: int = 15, min_age_hours: float = 6.0) -> list:
    lines = [f"Reels de la página: {len(reels)} | ahora: {now.astimezone():%Y-%m-%d %H:%M} (hora local) | "
             f"edad mínima para comparar: {min_age_hours:g} h", ""]
    lines.append(f"{'id':<9}{'creado (local)':<16}{'edad':>8}  {'origen':<11}{'vistas':>7}{'vistas/h':>9}{'a +1 h':>8}{'a +24 h':>9}{'coment.':>8}")
    for r in reels[:detail]:
        age = r.age_hours(now)
        per_hour = f"{(r.views or 0) / max(age, 1 / 6):.1f}" if r.views is not None else "?"
        h1, h24 = views_at(snapshots, r, 1, 0.4), views_at(snapshots, r, 24, 3)
        lines.append(f"…{r.id[-6:]:<8}{r.created.astimezone():%d/%m %H:%M}{'':<5}{_fmt_age(age):>8}  {r.origin:<11}"
                     f"{r.views if r.views is not None else '?':>7}{per_hour:>9}{h1 if h1 is not None else '-':>8}"
                     f"{h24 if h24 is not None else '-':>9}{r.comments if r.comments is not None else '-':>8}")
    if len(reels) > detail:
        lines.append(f"  (… y {len(reels) - detail} más antiguos; usa --detalle para ver más)")
    summary = summarize(reels, now, min_age_hours)
    lines += ["", "Resumen (solo Reels con la edad mínima):"]
    for group, label in (("autopiloto", "autopiloto"), ("resto", "resto (manuales y anteriores)")):
        s = summary[group]
        stats = (f"mediana {s['mediana']:g} | media {s['media']:g} | mín {s['min']} | máx {s['max']}" if s["n"] else "sin Reels maduros")
        lines.append(f"  {label:<30} {s['n']:>3} Reels ({s['recientes']} recientes aparte) | {stats}")
    lines += ["", *verdict(summary, min_age_hours)]
    return lines
