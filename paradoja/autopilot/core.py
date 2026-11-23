"""Orquestador: genera, publica y se programa solo. Nada de aqui detiene el programa: cada tarea se ejecuta protegida."""
from __future__ import annotations

import logging
import math
import os
import random
import subprocess
import time
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from datetime import time as dtime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import media
from .envfile import Config, redact
from .graph import GraphClient, GraphError
from .state import CONSUMED, MAX_ATTEMPTS, PLURAL, State

LOG = logging.getLogger("autopiloto")
KINDS = {"foto": "imagen del feed", "video": "Reel"}


# =========================================================================== registro
class _RedactingFormatter(logging.Formatter):
    """Borra el token de cualquier linea del log (incluidos los tracebacks)."""

    def __init__(self, fmt, secrets=()):
        super().__init__(fmt)
        self.secrets = tuple(secrets)

    def format(self, record) -> str:
        return redact(super().format(record), *self.secrets)


def setup_logging(path: Path, secrets=(), console: bool = True) -> logging.Logger:
    """`autopiloto.log` con rotacion (1 MB x 3) y, opcionalmente, la consola."""
    LOG.setLevel(logging.INFO)
    for h in list(LOG.handlers):
        LOG.removeHandler(h)
        h.close()
    fmt = _RedactingFormatter("%(asctime)s [%(levelname)s] %(message)s", secrets)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fh = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    LOG.addHandler(fh)
    if console:
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        LOG.addHandler(ch)
    LOG.propagate = False
    return LOG


# =========================================================================== bloqueo
class SingleInstance:
    """Impide dos autopilotos a la vez (publicarian por duplicado). El bloqueo se libera solo si el proceso muere."""

    def __init__(self, path: Path):
        self.path, self.fh = Path(path), None

    def acquire(self) -> bool:
        self.fh = open(self.path, "a+")
        try:
            self.fh.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            self.fh.close()
            self.fh = None
            return False

    def release(self) -> None:
        if not self.fh:
            return
        try:
            if os.name == "nt":
                import msvcrt
                self.fh.seek(0)
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        self.fh.close()
        self.fh = None




# =========================================================================== orquestador
@dataclass
class Outcome:
    kind: str
    status: str                       # ok | dry | skipped | error | ambiguous | retry
    detail: str = ""
    artifact: media.Artifact | None = None
    post_id: str | None = None
    attempt: int = 1
    retry_in: int = 0                 # segundos
    slot: str = ""                    # franja ("11:30") o "manual-HHMMSS"
    day: date | None = None


@dataclass
class Planned:
    """Una franja pendiente del dia con su hora real (hora base + retraso aleatorio)."""
    kind: str
    slot: str
    when: datetime
    catchup: bool = False             # la hora base ya habia pasado al arrancar (se recupera dentro de la tolerancia)


class Autopilot:
    def __init__(self, cfg: Config, client: GraphClient | None, state: State, *, runner=subprocess.run,
                 probe=media.probe_video, now=datetime.now, rng: random.Random | None = None, sleep=time.sleep,
                 sched=None, cancel=None):
        self.cfg, self.client, self.state = cfg, client, state
        self.runner, self.probe, self.now, self.rng, self.sleep = runner, probe, now, rng or random.Random(), sleep
        self.sched, self.cancel = sched, cancel
        self.state.clock = self.now                     # una sola hora para todo (y relojes simulados en las pruebas)
        self.planned_day: date | None = None

    # ------------------------------------------------------------------ generar
    def generate(self, kind: str) -> media.Artifact:
        cfg = self.cfg
        cmd, out_dir = ((media.image_command(cfg), cfg.image_out) if kind == "foto"
                        else (media.video_command(cfg), cfg.video_out))
        missing = media.missing_modules(cmd[0], media.REQUIRED_MODULES[kind], self.runner)
        if missing:                                     # p. ej. lanzado desde conda: falta moderngl para los Reels
            raise media.GenerationError(
                f"al Python de los generadores ({cmd[0]}) le faltan módulos: {', '.join(missing)}. Instálalos con "
                f'"{cmd[0]}" -m pip install -r requirements.txt  (o usa iniciar_autopiloto.bat, que prepara el entorno).')
        LOG.info("Generando %s (%s)...", KINDS[kind], Path(cmd[1]).name)
        since, t0 = time.time() - 5, time.monotonic()
        media.run_generator(cmd, cfg.gen_timeout_min * 60, self.runner)
        art = media.find_artifact(out_dir, kind, since)
        errors, warns = media.check_photo(art.media) if kind == "foto" else media.check_reel(self.probe(art.media))
        for w in warns:
            LOG.warning("%s: %s", art.media.name, w)
        if errors:
            raise media.GenerationError(f"{art.media.name} no cumple los requisitos de Meta: " + "; ".join(errors))
        LOG.info("Listo: %s (%.0f s)", art.media, time.monotonic() - t0)
        return art

    # ------------------------------------------------------------------ publicar
    def _manual_slot(self) -> str:
        return f"manual-{self.now():%H%M%S}"

    def _record(self, what: str, fn, *args, **kw) -> None:
        """Guarda en el estado un resultado ya consumado en Meta: si el disco falla, se avisa pero no se pierde el flujo."""
        try:
            fn(*args, **kw)
        except OSError as e:
            LOG.error("No se pudo guardar en el estado %s (%s). Revisa tu página: lo publicado ya está en Facebook.", what, e)

    def publish(self, art: media.Artifact, slot: str | None = None, day: date | None = None, attempt: int = 1) -> Outcome:
        cfg, kind, name = self.cfg, art.kind, art.media.name
        day, slot = day or self.now().date(), slot or self._manual_slot()
        base = dict(artifact=art, slot=slot, day=day)
        if cfg.dry_run:
            LOG.info("[PRUEBA] No se publica %s: %s | copy: «%s…»", KINDS[kind], name, art.copy.splitlines()[0][:90])
            return Outcome(kind, "dry", name, **base)
        if self.state.uploaded(name):
            LOG.error("%s: %s ya se subió antes; no se vuelve a publicar.", KINDS[kind], name)
            return Outcome(kind, "error", "ese archivo ya se subió antes", **base)
        try:
            self.state.begin(day, kind, slot, name)       # ANOTACION PREVIA: si el programa muere publicando, no se repite
        except OSError as e:
            LOG.error("No se pudo guardar el estado (%s): no se publica para no arriesgar un duplicado.", e)
            return Outcome(kind, "error", f"no se pudo guardar el estado: {e}", **base)
        try:
            if kind == "foto":
                res = self.client.post_photo(art.media, art.copy, art.alt)
                post_id = str(res.get("post_id") or res.get("id"))
            else:
                res = self.client.post_reel(art.media, art.copy, ai_generated=cfg.ai_label)
                post_id = str(res["video_id"])
                if res["status"].get("timeout"):
                    LOG.warning("Meta aún estaba procesando el Reel %s al terminar la espera: revísalo en tu página.", post_id)
        except GraphError as e:
            if e.ambiguous:
                LOG.warning("%s: resultado AMBIGUO (%s). Puede haberse publicado: revisa tu página; no se reintenta "
                            "para no duplicar.", KINDS[kind], e)
                self._record("el resultado ambiguo", self.state.finish, day, kind, slot, "ambiguo", name, error=str(e))
                return Outcome(kind, "ambiguous", str(e), attempt=attempt, **base)
            if e.retry and attempt <= cfg.retries:
                LOG.warning("%s: fallo temporal de la API (%s). Reintento %d/%d en %d min.", KINDS[kind], e, attempt,
                            cfg.retries, cfg.retry_minutes)
                self._record("el reintento", self.state.release, day, kind, slot)
                return Outcome(kind, "retry", str(e), attempt=attempt + 1, retry_in=cfg.retry_minutes * 60, **base)
            LOG.error("%s: la API rechazó la publicación: %s", KINDS[kind], e)
            self._record("el error", self.state.fail, day, kind, slot, str(e), archivo=name)
            return Outcome(kind, "error", str(e), attempt=attempt, **base)
        except Exception as e:                          # inesperado a mitad de la publicacion: pudo salir -> no se repite
            LOG.exception("%s: error inesperado al publicar: %s", KINDS[kind], redact(e, cfg.token))
            self._record("el resultado ambiguo", self.state.finish, day, kind, slot, "ambiguo", name,
                         error=redact(e, cfg.token))
            return Outcome(kind, "ambiguous", str(e), attempt=attempt, **base)
        LOG.info("PUBLICADO %s: %s (id %s)", KINDS[kind], name, post_id)
        self._record("la publicación", self.state.finish, day, kind, slot, "ok", name, post_id)
        return Outcome(kind, "ok", name, post_id=post_id, **base)

    # ------------------------------------------------------------------ una tarea completa
    def _skip_reason(self, kind: str, slot: str, manual: bool, day: date, now: datetime) -> str | None:
        """Por que NO hay que publicar esta franja ahora (None = adelante). Anota las omisiones en el estado."""
        cfg, st = self.cfg, self.state
        if not manual:
            if day != now.date():
                return "otro día"
            if (st.slot(day, kind, slot) or {}).get("estado") in CONSUMED:
                return "ya ejecutada"
        if st.count(day, kind) >= cfg.limit(kind):
            if not manual:
                st.omit(day, kind, slot, f"límite diario de {PLURAL[kind]} cubierto ({cfg.limit(kind)})")
            return "límite diario"
        if not manual:
            h, m = map(int, slot.split(":"))
            late = (now - datetime.combine(day, dtime(h, m))).total_seconds()
            if late > cfg.tolerance_hours * 3600:
                st.omit(day, kind, slot, f"la hora ({slot}) pasó hace {late / 3600:.1f} h (PC apagado o dormido)")
                return "hora pasada"
        return None

    def execute(self, kind: str, slot: str | None = None, day: date | None = None, force: bool = False) -> Outcome:
        """Genera y publica una franja (`slot`="HH:MM"). Sin franja es una publicacion manual. `force` ignora los limites."""
        now = self.now()
        day, manual = day or now.date(), slot is None
        slot = slot or self._manual_slot()
        if not force:
            reason = self._skip_reason(kind, slot, manual, day, now)
            if reason:
                msg = {"ya ejecutada": "ya se ejecutó hoy", "límite diario": f"límite diario alcanzado ({self.cfg.limit(kind)})",
                       "hora pasada": "la hora ya pasó (se omite)", "otro día": "era de otro día"}[reason]
                LOG.warning("%s %s: %s; se omite.", KINDS[kind].capitalize(), slot, msg)
                return Outcome(kind, "skipped", reason, slot=slot, day=day)
        try:
            art = self.generate(kind)
        except Exception as e:                          # render o generador caidos: se registra y se sigue vivo
            LOG.error("No se pudo generar %s: %s", KINDS[kind], redact(e, self.cfg.token))
            if not self.cfg.dry_run and not manual:
                self.state.fail(day, kind, slot, redact(e, self.cfg.token))
            return Outcome(kind, "error", f"generación: {e}", slot=slot, day=day)
        return self.publish(art, slot, day)

    def run_now(self, kind: str) -> Outcome:
        """Ejecucion inmediata y bloqueante (sin jitter ni limites), con los reintentos de publicacion."""
        out = self.execute(kind, force=True)
        while out.status == "retry":
            self.sleep(out.retry_in)
            out = self.publish(out.artifact, out.slot, out.day, out.attempt)
        return out

    # ------------------------------------------------------------------ plan del dia
    def _when(self, day: date, base: datetime, entry: dict, now: datetime) -> tuple:
        """Hora real de una franja: la que ya estaba prevista (si se reinicio) o hora base + retraso aleatorio."""
        prev = entry.get("prevista") if entry.get("estado") == "programada" else None
        if prev:
            try:
                t = datetime.combine(day, datetime.strptime(prev, "%H:%M:%S").time())
            except ValueError:
                t = None
            if t is not None:
                return (t, False) if t > now else (now + timedelta(seconds=self.rng.randint(5, 60)), True)
        jitter = self.rng.randint(self.cfg.jitter_min * 60, self.cfg.jitter_max * 60)
        return max(base, now) + timedelta(seconds=jitter), base < now

    def plan(self, day: date | None = None, persist: bool = True) -> tuple:
        """-> (pendientes, omitidas). Solo se planifican las franjas aun no ejecutadas y mientras quede cupo del dia:
        cada tipo tiene su propio limite y se reparte por orden de hora. Las que pasaron hace mas de la tolerancia o no
        caben en el limite se anotan como omitidas (con su motivo)."""
        cfg, st, now = self.cfg, self.state, self.now()
        day = day or now.date()
        planned, omitted = [], []
        with (st.batch() if persist else nullcontext()):
            for kind in KINDS:
                if not cfg.limit(kind):
                    continue                                         # tipo desactivado
                remaining = cfg.limit(kind) - st.count(day, kind)    # lo ya publicado (tambien a mano) gasta cupo
                for franja in cfg.times(kind):
                    entry = st.slot(day, kind, franja) or {}
                    if entry.get("estado") in CONSUMED:
                        continue
                    if entry.get("estado") == "error" and entry.get("intentos", 1) >= MAX_ATTEMPTS:
                        continue
                    h, m = map(int, franja.split(":"))
                    base = datetime.combine(day, dtime(h, m))
                    late = (now - base).total_seconds()
                    if late > cfg.tolerance_hours * 3600:
                        motivo = f"la hora ({franja}) pasó hace {late / 3600:.1f} h (PC apagado o programa cerrado)"
                    elif remaining <= 0:
                        motivo = f"límite diario de {PLURAL[kind]} cubierto ({cfg.limit(kind)})"
                    else:
                        remaining -= 1
                        when, catchup = self._when(day, base, entry, now)
                        planned.append(Planned(kind, franja, when, catchup))
                        if persist:
                            st.schedule(day, kind, franja, when.strftime("%H:%M:%S"))
                        continue
                    omitted.append((kind, franja, motivo))
                    if persist:
                        st.omit(day, kind, franja, motivo)
        planned.sort(key=lambda p: p.when)
        return planned, omitted

    def _slot_text(self, e: dict | None) -> str:
        if not e:
            return "pendiente"
        s = e.get("estado")
        if s == "ejecutada":
            return f"ejecutada a las {e.get('hora', '?')}"
        if s == "ambigua":
            return f"AMBIGUA a las {e.get('hora', '?')}: puede estar publicada, revisa tu página"
        if s == "en_curso":
            return f"en curso desde las {e.get('hora', '?')}"
        if s == "omitida":
            return f"omitida: {e.get('motivo', '')}"
        if s == "error":
            return f"con error (intento {e.get('intentos', 1)}/{MAX_ATTEMPTS}): {e.get('error', '')}"
        if s == "programada":
            return f"pendiente, prevista a las {e.get('prevista', '?')}"
        return str(s)

    def status_lines(self, day: date | None = None, preview: dict | None = None) -> list:
        """Resumen legible del dia: contadores, lo publicado (archivo e id) y el estado de cada franja.
        `preview` {(tipo, franja): texto} describe lo que haria el plan con las franjas aun sin ejecutar (`--estado`)."""
        cfg, st = self.cfg, self.state
        day = day or self.now().date()
        counts = " | ".join(f"{PLURAL[k]} {st.count(day, k)}/{cfg.limit(k)}" + ("" if cfg.limit(k) else " (desactivado)")
                            for k in KINDS)
        lines = [f"Resumen de hoy ({day.isoformat()}): {counts}"]
        pubs = sorted(st.publications(day), key=lambda p: p.get("hora", ""))
        if pubs:
            lines.append("  Publicado:")
            for p in pubs:
                flag = "  <- AMBIGUA, revisa la página" if p.get("estado") == "ambiguo" else ""
                lines.append(f"    {p.get('hora') or '--:--:--'}  {p.get('tipo'):<5}  {p.get('archivo') or '(sin archivo)'}  "
                             f"id {p.get('id') or '-'}{flag}")
        else:
            lines.append("  Todavía no se ha publicado nada hoy.")
        for kind in KINDS:
            if cfg.limit(kind):
                for franja in cfg.times(kind):
                    entry = st.slot(day, kind, franja)
                    text = (preview or {}).get((kind, franja)) if (entry or {}).get("estado") not in CONSUMED else None
                    lines.append(f"  Franja {kind:<5} {franja}: {text or self._slot_text(entry)}")
        return lines

    def start_day(self, day: date | None = None) -> list:
        """Lee el estado, enseña el resumen y programa SOLO las franjas pendientes que caben en el limite de cada tipo."""
        now = self.now()
        day = day or now.date()
        self.planned_day = day
        planned, _omitted = self.plan(day)
        for line in self.status_lines(day):
            LOG.info(line)
        for p in planned:
            delay = max(1, math.ceil((p.when - now).total_seconds()))
            if self.sched is not None:
                self.sched.every(delay).seconds.do(self._run_slot, p.kind, p.slot, day)
        LOG.info("Pendiente por publicar hoy: %d franja(s)%s.", len(planned),
                 "" if planned else " (nada más que hacer hasta mañana)")
        return planned

    def ensure_plan(self) -> None:
        """Gancho del bucle principal: al cambiar de dia (medianoche) se vuelve a planificar con el estado del dia nuevo."""
        today = self.now().date()
        if self.planned_day == today:
            return
        try:
            self.start_day(today)
        except Exception as e:
            LOG.exception("Error al planificar el día %s: %s", today, redact(e, self.cfg.token))

    # ------------------------------------------------------------------ ejecucion programada
    def _guard(self, fn, *args) -> Outcome:
        try:
            return fn(*args)
        except Exception as e:                          # nada detiene el programa
            LOG.exception("Error inesperado en la tarea: %s", redact(e, self.cfg.token))
            return Outcome(args[0] if args and isinstance(args[0], str) else "?", "error", str(e))

    def _after(self, out: Outcome) -> None:
        if out.status == "retry" and self.sched is not None:
            self.sched.every(max(1, out.retry_in)).seconds.do(self._retry_job, out)

    def _run_slot(self, kind: str, slot: str, day: date):
        self._after(self._guard(self.execute, kind, slot, day))
        return self.cancel                              # tarea de una sola vez

    def _retry_job(self, out: Outcome):
        self._after(self._guard(lambda: self.publish(out.artifact, out.slot, out.day, out.attempt)))
        return self.cancel


def build_scheduler(cfg: Config, auto: Autopilot):
    """Un `schedule.Scheduler` vacio enlazado al autopiloto: `Autopilot.start_day()` le añade las franjas pendientes."""
    import schedule
    sch = schedule.Scheduler()
    auto.sched, auto.cancel = sch, schedule.CancelJob
    return sch


def run_forever(sch, stop=lambda: False, tick: float = 1.0, sleep=time.sleep, hook=None) -> None:
    """Bucle principal: una excepcion nunca lo detiene (solo Ctrl+C). `hook` se llama en cada vuelta (cambio de dia)."""
    while not stop():
        try:
            if hook:
                hook()
            sch.run_pending()
        except Exception as e:
            LOG.exception("Error en el planificador (se sigue): %s", e)
        sleep(tick)
