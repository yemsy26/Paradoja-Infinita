"""Paradoja Infinita - compara las vistas de los Reels del autopiloto con las de los subidos a mano (SOLO LECTURA).

    python comparar_reels.py                 informe: vistas por Reel y resumen autopiloto frente al resto
    python comparar_reels.py --detalle 30    mas filas en la tabla
    python comparar_reels.py --manual 123 456   marca esos ids de video como subidos a mano
    python comparar_reels.py --no-guardar    no guarda la foto de vistas de esta ejecucion

Solo hace peticiones GET a la Graph API (no publica, no edita, no borra). Cada ejecucion guarda una foto de las vistas en
diagnostico_reels.json (esta en .gitignore): con varias fotos el informe calcula las vistas a +1 h y +24 h de cada Reel, que es
lo que hace falta para comparar dos vias de subida con justicia. No imprime nunca el token. Mas informacion: docs/AUTOPILOTO.md.
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from paradoja.autopilot import diagnostico as dg
from paradoja.autopilot.envfile import ROOT, Config, load_env
from paradoja.autopilot.graph import GraphClient, GraphError


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", type=Path, default=ROOT / ".env", help="archivo .env (por defecto el del proyecto)")
    ap.add_argument("--limite", type=int, default=40, help="cuantos Reels leer (los mas recientes; maximo 100)")
    ap.add_argument("--detalle", type=int, default=15, help="filas de la tabla")
    ap.add_argument("--edad-min", type=float, default=6.0, metavar="HORAS", help="edad minima de un Reel para entrar en el resumen")
    ap.add_argument("--manual", nargs="*", default=[], metavar="ID", help="ids de video subidos a mano (el resto «otro»)")
    ap.add_argument("--no-guardar", action="store_true", help="no guarda la foto de vistas en diagnostico_reels.json")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    cfg = Config.from_sources(load_env(args.env))
    problems = [p for p in cfg.problems(need_credentials=True) if "PAGE_" in p or "GRAPH" in p]
    if problems:
        for p in problems:
            print(f"Configuración: {dg.limpiar(p, cfg.token)}")
        return 2
    client = GraphClient(cfg.page_id, cfg.token, cfg.version)
    now = datetime.now(timezone.utc)
    try:
        reels = dg.collect(client, dg.origins_from_state(cfg.state_file), args.manual, max(1, min(args.limite, 100)))
    except GraphError as e:
        print(f"No se pudieron leer los Reels: {dg.limpiar(e, cfg.token)}")
        return 1
    snapshots = dg.load_snapshots()
    print("\n".join(dg.limpiar(line, cfg.token) for line in dg.render(reels, now, snapshots, args.detalle, args.edad_min)))
    if not args.no_guardar:
        total = dg.save_snapshot(reels, now)
        print(f"\nFoto de vistas guardada ({total} en total). Vuelve a ejecutarlo en 1 h y en 24 h para ver las columnas «a +1 h» y «a +24 h».")
    return 0


if __name__ == "__main__":
    sys.exit(main())
