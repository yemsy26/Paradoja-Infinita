"""Paradoja Infinita - autopiloto: genera y publica solo en tu pagina de Facebook (imagen por la mañana, Reel por la tarde).

    python autopiloto.py                 queda en marcha en segundo plano y publica a sus horas (Ctrl+C para parar)
    python autopiloto.py --check         comprueba el token y el acceso a la pagina (no publica nada)
    python autopiloto.py --dry-run       genera con normalidad pero NO publica (ensayo completo)
    python autopiloto.py --ahora foto    genera y publica una imagen ya, sin esperar (tambien: --ahora video)
    python autopiloto.py --estado        muestra lo publicado hoy y las franjas pendientes (no publica ni modifica nada)

Necesita un archivo .env con PAGE_ID y PAGE_ACCESS_TOKEN (copia .env.example). Los horarios son listas separadas por comas
(HORARIOS_FOTOS=11:30,17:00 y HORARIOS_VIDEOS=18:00) con limites propios (MAX_FOTOS_DIA y MAX_VIDEOS_DIA). Cada franja usa un
retraso aleatorio de 1 a 15 minutos sobre su hora. Lo publicado cada dia se guarda en estado_autopiloto.json: si cierras el
programa o reinicias el PC, al volver solo se programan las franjas que faltan. Los errores van a autopiloto.log.
"""
import argparse
import dataclasses
import os
import sys
from pathlib import Path

from paradoja.autopilot import core, media
from paradoja.autopilot.envfile import ROOT, Config, load_env
from paradoja.autopilot.graph import GraphClient, GraphError
from paradoja.autopilot.state import State

LOCK_FILE = ROOT / "autopiloto.lock"


def build_config(args) -> Config:
    """.env + entorno + opciones de la linea de comandos (estas ganan)."""
    cli = {}
    for attr, key in (("fotos", "HORARIOS_FOTOS"), ("videos", "HORARIOS_VIDEOS"), ("max_fotos", "MAX_FOTOS_DIA"),
                      ("max_videos", "MAX_VIDEOS_DIA")):
        if getattr(args, attr) is not None:
            cli[key] = str(getattr(args, attr))
    cfg = Config.from_sources(load_env(args.env), {**os.environ, **cli})
    changes = {}
    if args.jitter:
        try:
            lo, hi = (int(x) for x in args.jitter.split("-"))
            changes.update(jitter_min=lo, jitter_max=hi)
        except ValueError:
            raise SystemExit("--jitter debe tener la forma MIN-MAX en minutos (por ejemplo 1-15).")
    if args.dry_run:
        changes["dry_run"] = True
    return dataclasses.replace(cfg, **changes)


def open_state(cfg: Config, readonly: bool = False) -> State:
    """`estado_autopiloto.json` (y, la primera vez, migra el `autopiloto_estado.json` del formato antiguo)."""
    return State(cfg.state_file, legacy=cfg.state_file.with_name("autopiloto_estado.json"), readonly=readonly)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", type=Path, default=ROOT / ".env", help="archivo .env (por defecto el de la carpeta del proyecto)")
    ap.add_argument("--fotos", "--foto", metavar="HH:MM,HH:MM", help="horarios de las imagenes (por defecto 11:30)")
    ap.add_argument("--videos", "--video", metavar="HH:MM,HH:MM", help="horarios de los Reels (por defecto 18:00)")
    ap.add_argument("--max-fotos", type=int, metavar="N", help="maximo de imagenes por dia")
    ap.add_argument("--max-videos", type=int, metavar="N", help="maximo de Reels por dia")
    ap.add_argument("--jitter", metavar="MIN-MAX", help="retraso aleatorio en minutos (por defecto 1-15)")
    ap.add_argument("--dry-run", action="store_true", help="genera pero no publica")
    ap.add_argument("--check", action="store_true", help="comprueba el token y la pagina, y sale")
    ap.add_argument("--ahora", choices=["foto", "video"], help="genera y publica ya (sin jitter) y sale")
    ap.add_argument("--estado", action="store_true", help="muestra lo publicado hoy y lo pendiente, y sale (solo lee)")
    ap.add_argument("--silencioso", action="store_true", help="no escribe en la consola (solo en autopiloto.log)")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):                  # tildes y emojis correctos en la consola de Windows
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    cfg = build_config(args)
    log = core.setup_logging(cfg.log_file, secrets=(cfg.token,), console=not args.silencioso)
    problems = cfg.problems(need_credentials=args.check or not (cfg.dry_run or args.estado))
    if problems:
        for p in problems:
            log.error("Configuración: %s", p)
        log.error("Corrige %s (hay un modelo en .env.example) y vuelve a ejecutar.", args.env.name)
        return 2
    for note in cfg.notes:
        log.warning("Configuración: %s", note)
    client = GraphClient(cfg.page_id, cfg.token, cfg.version, log=log) if cfg.page_id and cfg.token else None
    if not args.check:                                       # entorno de los generadores (imagen y Reel)
        log.info("Los generadores se ejecutan con: %s", media.project_python())
        if not media.ensure_ffmpeg_on_path():
            log.warning("FFmpeg/ffprobe no están en el PATH: los Reels no se podrán generar (las imágenes sí). "
                        "Ejecuta iniciar.bat una vez para instalarlo.")

    if args.check:
        try:
            info = client.check()
        except GraphError as e:
            log.error("No se pudo comprobar la página: %s", e)
            return 1
        log.info("Conexión correcta: página «%s» (id %s), Graph API %s.", info.get("name"), info.get("id"), cfg.version)
        return 0

    if args.estado:                                          # solo lectura: no toma el candado ni toca el archivo
        auto = core.Autopilot(cfg, client, open_state(cfg, readonly=True))
        planned, omitted = auto.plan(persist=False)
        preview = {(p.kind, p.slot): f"pendiente: se programaría hacia las {p.when:%H:%M}" + (" (recuperación)" if p.catchup else "")
                   for p in planned}
        preview.update({(k, f): f"no se programaría: {motivo}" for k, f, motivo in omitted})
        for line in auto.status_lines(preview=preview):
            log.info(line)
        return 0

    lock = core.SingleInstance(LOCK_FILE)
    if not lock.acquire():
        log.error("Ya hay un autopiloto en marcha (archivo %s en uso). No se inicia otro para no publicar por duplicado.",
                  LOCK_FILE.name)
        return 3
    try:
        auto = core.Autopilot(cfg, client, open_state(cfg))   # con el candado ya tomado: aqui se recupera lo interrumpido
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
        log.info("Autopiloto en marcha | modo %s | imágenes %s (máx. %d/día) y Reels %s (máx. %d/día) | +%d a %d min al azar "
                 "| Graph API %s", mode, ",".join(cfg.photo_times) or "-", cfg.limit("foto"), ",".join(cfg.video_times) or "-",
                 cfg.limit("video"), cfg.jitter_min, cfg.jitter_max, cfg.version)
        auto.start_day()                                      # resumen de hoy + solo las franjas pendientes
        log.info("Déjalo abierto (el PC encendido y sin suspender). Ctrl+C para detenerlo.")
        try:
            core.run_forever(sch, hook=auto.ensure_plan)
        except KeyboardInterrupt:
            log.info("Detenido por el usuario.")
        return 0
    finally:
        lock.release()


if __name__ == "__main__":
    sys.exit(main())
