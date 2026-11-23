"""Paradoja Infinita - autopiloto: genera y publica solo en tu pagina de Facebook (imagen por la mañana, Reel por la tarde).

    python autopiloto.py                 queda en marcha en segundo plano y publica a sus horas (Ctrl+C para parar)
    python autopiloto.py --check         comprueba el token y el acceso a la pagina (no publica nada)
    python autopiloto.py --dry-run       genera con normalidad pero NO publica (ensayo completo)
    python autopiloto.py --ahora foto    genera y publica una imagen ya, sin esperar (tambien: --ahora video)

Necesita un archivo .env con PAGE_ID y PAGE_ACCESS_TOKEN (copia .env.example). Cada tarea usa un retraso aleatorio de 1 a 15
minutos sobre su hora; los errores se anotan en autopiloto.log y el programa sigue vivo.
"""
import argparse
import dataclasses
import sys
from pathlib import Path

from paradoja.autopilot import core
from paradoja.autopilot.envfile import ROOT, Config, load_env
from paradoja.autopilot.graph import GraphClient, GraphError

LOCK_FILE = ROOT / "autopiloto.lock"


def build_config(args) -> Config:
    cfg = Config.from_sources(load_env(args.env))
    changes = {}
    if args.foto:
        changes["photo_time"] = args.foto
    if args.video:
        changes["video_time"] = args.video
    if args.jitter:
        try:
            lo, hi = (int(x) for x in args.jitter.split("-"))
            changes.update(jitter_min=lo, jitter_max=hi)
        except ValueError:
            raise SystemExit("--jitter debe tener la forma MIN-MAX en minutos (por ejemplo 1-15).")
    if args.dry_run:
        changes["dry_run"] = True
    return dataclasses.replace(cfg, **changes)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", type=Path, default=ROOT / ".env", help="archivo .env (por defecto el de la carpeta del proyecto)")
    ap.add_argument("--foto", metavar="HH:MM", help="hora de la imagen (por defecto 11:30)")
    ap.add_argument("--video", metavar="HH:MM", help="hora del Reel (por defecto 18:00)")
    ap.add_argument("--jitter", metavar="MIN-MAX", help="retraso aleatorio en minutos (por defecto 1-15)")
    ap.add_argument("--dry-run", action="store_true", help="genera pero no publica")
    ap.add_argument("--check", action="store_true", help="comprueba el token y la pagina, y sale")
    ap.add_argument("--ahora", choices=["foto", "video"], help="genera y publica ya (sin jitter) y sale")
    ap.add_argument("--silencioso", action="store_true", help="no escribe en la consola (solo en autopiloto.log)")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):                  # tildes y emojis correctos en la consola de Windows
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    cfg = build_config(args)
    log = core.setup_logging(cfg.log_file, secrets=(cfg.token,), console=not args.silencioso)
    problems = cfg.problems(need_credentials=args.check or not cfg.dry_run)
    if problems:
        for p in problems:
            log.error("Configuración: %s", p)
        log.error("Corrige %s (hay un modelo en .env.example) y vuelve a ejecutar.", args.env.name)
        return 2
    client = GraphClient(cfg.page_id, cfg.token, cfg.version, log=log) if cfg.page_id and cfg.token else None

    if args.check:
        try:
            info = client.check()
        except GraphError as e:
            log.error("No se pudo comprobar la página: %s", e)
            return 1
        log.info("Conexión correcta: página «%s» (id %s), Graph API %s.", info.get("name"), info.get("id"), cfg.version)
        return 0

    auto = core.Autopilot(cfg, client, core.State(cfg.state_file))
    lock = core.SingleInstance(LOCK_FILE)
    if not lock.acquire():
        log.error("Ya hay un autopiloto en marcha (archivo %s en uso). No se inicia otro para no publicar por duplicado.",
                  LOCK_FILE.name)
        return 3
    try:
        if args.ahora:
            out = auto.run_now(args.ahora)
            log.info("Resultado: %s %s", out.status, out.detail)
            return 0 if out.status in ("ok", "dry") else 1
        try:
            sch = core.build_scheduler(cfg, auto)
        except ImportError:
            log.error("Falta la librería «schedule»: ejecuta  pip install -r requirements.txt")
            return 2
        mode = "PRUEBA (no publica)" if cfg.dry_run else f"REAL en la página {cfg.page_id}"
        log.info("Autopiloto en marcha | modo %s | imagen %s y Reel %s (+%d a %d min al azar) | máx. %d/día | Graph API %s",
                 mode, cfg.photo_time, cfg.video_time, cfg.jitter_min, cfg.jitter_max, cfg.max_per_day, cfg.version)
        for line in core.describe_schedule(sch):
            log.info(line)
        log.info("Déjalo abierto (el PC encendido y sin suspender). Ctrl+C para detenerlo.")
        try:
            core.run_forever(sch)
        except KeyboardInterrupt:
            log.info("Detenido por el usuario.")
        return 0
    finally:
        lock.release()


if __name__ == "__main__":
    sys.exit(main())
