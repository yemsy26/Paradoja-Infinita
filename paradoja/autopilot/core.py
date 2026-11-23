"""Orquestador: genera, publica y se programa solo. Nada de aqui detiene el programa: cada tarea se ejecuta protegida."""
from __future__ import annotations

import json
import logging
import os
import random
import subprocess
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from datetime import time as dtime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import media
from .envfile import Config, redact
from .graph import GraphClient, GraphError

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


# =========================================================================== estado y bloqueo
class State:
    """`autopiloto_estado.json`: que se publico cada dia (evita duplicados al reiniciar y limita las publicaciones por dia)."""

    DONE = ("ok", "ambiguo")

    def __init__(self, path: Path):
        self.path = Path(path)
        try:
            self.data = json.loads(self.path.read_text("utf-8"))
        except (OSError, ValueError):
            self.data = {}
        self.data.setdefault("dias", {})

    def _day(self, d: date) -> dict:
        return self.data["dias"].setdefault(d.isoformat(), {})

    def done(self, d: date, kind: str) -> bool:
        return self._day(d).get(kind, {}).get("estado") in self.DONE

    def count(self, d: date) -> int:
        return sum(1 for v in self._day(d).values() if v.get("estado") in self.DONE)

    def mark(self, d: date, kind: str, estado: str, **info) -> None:
        self._day(d)[kind] = {"estado": estado, "hora": datetime.now().strftime("%H:%M:%S"), **info}
        keep = sorted(self.data["dias"])[-45:]
        self.data["dias"] = {k: self.data["dias"][k] for k in keep}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), "utf-8")
        os.replace(tmp, self.path)


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


class Autopilot:
    def __init__(self, cfg: Config, client: GraphClient | None, state: State, *, runner=subprocess.run,
                 probe=media.probe_video, now=datetime.now, rng: random.Random | None = None, sleep=time.sleep,
                 sched=None, cancel=None):
        self.cfg, self.client, self.state = cfg, client, state
        self.runner, self.probe, self.now, self.rng, self.sleep = runner, probe, now, rng or random.Random(), sleep
        self.sched, self.cancel = sched, cancel

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
    def publish(self, art: media.Artifact, attempt: int = 1) -> Outcome:
        cfg, today = self.cfg, self.now().date()
        preview = art.copy.splitlines()[0][:90]
        if cfg.dry_run:
            LOG.info("[PRUEBA] No se publica %s: %s | copy: «%s…»", KINDS[art.kind], art.media.name, preview)
            return Outcome(art.kind, "dry", art.media.name, art)
        try:
            if art.kind == "foto":
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
                            "para no duplicar.", KINDS[art.kind], e)
                self.state.mark(today, art.kind, "ambiguo", archivo=art.media.name, error=str(e))
                return Outcome(art.kind, "ambiguous", str(e), art, attempt=attempt)
            if e.retry and attempt <= cfg.retries:
                LOG.warning("%s: fallo temporal de la API (%s). Reintento %d/%d en %d min.", KINDS[art.kind], e, attempt,
                            cfg.retries, cfg.retry_minutes)
                return Outcome(art.kind, "retry", str(e), art, attempt=attempt + 1, retry_in=cfg.retry_minutes * 60)
            LOG.error("%s: la API rechazó la publicación: %s", KINDS[art.kind], e)
            self.state.mark(today, art.kind, "error", archivo=art.media.name, error=str(e))
            return Outcome(art.kind, "error", str(e), art, attempt=attempt)
        LOG.info("PUBLICADO %s: %s (id %s)", KINDS[art.kind], art.media.name, post_id)
        self.state.mark(today, art.kind, "ok", archivo=art.media.name, id=post_id)
        return Outcome(art.kind, "ok", art.media.name, art, post_id)

    # ------------------------------------------------------------------ una tarea completa
    def execute(self, kind: str, force: bool = False) -> Outcome:
        """Genera y publica. Con `force` ignora el estado del dia (uso manual con --ahora)."""
        today = self.now().date()
        if not force:
            if self.state.done(today, kind):
                LOG.info("%s: ya se publicó hoy; se omite.", KINDS[kind])
                return Outcome(kind, "skipped", "ya publicado hoy")
            if self.state.count(today) >= self.cfg.max_per_day:
                LOG.warning("Límite diario alcanzado (%d publicaciones): se omite %s.", self.cfg.max_per_day, KINDS[kind])
                return Outcome(kind, "skipped", "límite diario")
        try:
            art = self.generate(kind)
        except Exception as e:                          # render o generador caidos: se registra y se sigue vivo
            LOG.error("No se pudo generar %s: %s", KINDS[kind], redact(e, self.cfg.token))
            if not self.cfg.dry_run:
                self.state.mark(today, kind, "error", error=str(e)[:300])
            return Outcome(kind, "error", f"generación: {e}")
        return self.publish(art)

    def run_now(self, kind: str) -> Outcome:
        """Ejecucion inmediata y bloqueante (sin jitter), con los reintentos de publicacion."""
        out = self.execute(kind, force=True)
        while out.status == "retry":
            self.sleep(out.retry_in)
            out = self.publish(out.artifact, out.attempt)
        return out

    # ------------------------------------------------------------------ programacion
    def _guard(self, fn, *args) -> Outcome:
        try:
            return fn(*args)
        except Exception as e:                          # nada detiene el programa
            LOG.exception("Error inesperado en la tarea: %s", redact(e, self.cfg.token))
            return Outcome(args[0] if args and isinstance(args[0], str) else "?", "error", str(e))

    def _after(self, out: Outcome) -> None:
        if out.status == "retry" and self.sched is not None:
            self.sched.every(max(1, out.retry_in)).seconds.do(self._retry_job, out.artifact, out.attempt)

    def _run_once(self, kind: str):
        self._after(self._guard(self.execute, kind))
        return self.cancel                              # tarea de una sola vez

    def _retry_job(self, art: media.Artifact, attempt: int):
        self._after(self._guard(lambda: self.publish(art, attempt)))
        return self.cancel

    def trigger(self, kind: str) -> None:
        """Hora base del dia: elige el retraso aleatorio (jitter) y programa la publicacion real para despues."""
        base_str = self.cfg.photo_time if kind == "foto" else self.cfg.video_time
        now = self.now()
        h, m = map(int, base_str.split(":"))
        late = (now - datetime.combine(now.date(), dtime(h, m))).total_seconds()
        if late > self.cfg.tolerance_hours * 3600:
            LOG.warning("%s: la hora base (%s) pasó hace %.1f h (¿el PC estaba apagado o dormido?). Se omite hoy.",
                        KINDS[kind], base_str, late / 3600)
            return
        jitter = self.rng.randint(self.cfg.jitter_min * 60, self.cfg.jitter_max * 60)
        when = now + timedelta(seconds=jitter)
        LOG.info("%s: hora base %s + retraso aleatorio de %d min %02d s -> se publicará a las %s.", KINDS[kind].capitalize(),
                 base_str, jitter // 60, jitter % 60, when.strftime("%H:%M:%S"))
        if jitter <= 0:
            self._run_once(kind)
        else:
            self.sched.every(jitter).seconds.do(self._run_once, kind)

    def safe_trigger(self, kind: str) -> None:
        try:
            self.trigger(kind)
        except Exception as e:
            LOG.exception("Error al programar %s: %s", KINDS[kind], redact(e, self.cfg.token))


def build_scheduler(cfg: Config, auto: Autopilot):
    """Un `schedule.Scheduler` con las dos tareas diarias (hora local del PC)."""
    import schedule
    sch = schedule.Scheduler()
    auto.sched, auto.cancel = sch, schedule.CancelJob
    sch.every().day.at(cfg.photo_time).do(auto.safe_trigger, "foto")
    sch.every().day.at(cfg.video_time).do(auto.safe_trigger, "video")
    return sch


def run_forever(sch, stop=lambda: False, tick: float = 1.0, sleep=time.sleep) -> None:
    """Bucle principal: una excepcion nunca lo detiene (solo Ctrl+C)."""
    while not stop():
        try:
            sch.run_pending()
        except Exception as e:
            LOG.exception("Error en el planificador (se sigue): %s", e)
        sleep(tick)


def describe_schedule(sch) -> list:
    return [f"  próxima ejecución base: {j.next_run:%Y-%m-%d %H:%M}" for j in sorted(sch.get_jobs(), key=lambda j: j.next_run)]
