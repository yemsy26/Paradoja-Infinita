"""Paradoja Infinita - generador de imagenes estaticas para el feed de Facebook (1080x1350).

Sin argumentos abre el menu interactivo.
Automatizacion (sin menu):  python generador_imagenes.py --modo aleatorio --count 5

Cada imagen se dibuja con Pillow (sin IA generativa) y se guarda en output_imagenes/AAAA-MM-DD/ junto a un .txt con el
copy para pegar, la respuesta correcta (control interno) y el comentario para revelarla.
"""
import argparse
import random
import secrets
import sys
from pathlib import Path

from paradoja.clipboard import copy_file_to_clipboard
from paradoja.feed import history as hist
from paradoja.feed.fonts import FONT_DIRS, STYLE_NAMES, FontKit
from paradoja.feed.puzzles import MODES
from paradoja.feed.studio import DEFAULT_OUT, MODE_LABEL, choose_mode, generate_one

MENU = """
==================================================================
   PARADOJA INFINITA  -  imagenes para el feed de Facebook
==================================================================
  [1] La Ecuacion de la Discordia   (PEMDAS: el orden de las operaciones)
  [2] El Reto de los Cubos Isometricos (cuantos cubos hay, con ocultos)
  [3] Fracciones Enganosas          (que fraccion es la region gris)
  [4] Opcion Multiple Tramposa      (numeros romanos, secuencias, trampas)
  [5] Aleatorio inteligente         (mezcla los 4 y evita repetir)
  [6] Estilo de letra               (actual: {font})
  [7] Estadisticas
  [0] Salir
------------------------------------------------------------------"""
CHOICES = {"1": "pemdas", "2": "cubos", "3": "fracciones", "4": "opciones", "5": "aleatorio"}


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return "0"


def make_kit(style: str, font: str | None) -> FontKit:
    kit = FontKit(style, font)
    if not kit.found:
        print(f"AVISO: no encuentro una fuente gruesa con todos los signos ({kit.describe()}).\n"
              f"       Descarga Montserrat (o Comic Neue, Poppins, Anton...) y copia los .ttf a: {FONT_DIRS[0]}")
    return kit


def generate(mode: str, seed: int, args, kit: FontKit) -> None:
    res = generate_one(mode, seed, kit, args.out, args.formato)
    print(f"  {res.image.name}  |  respuesta: {res.puzzle.answer}  |  paleta: {res.palette}")
    print(f"    Imagen   -> {res.image}\n    Copy     -> {res.txt}")
    if not args.no_copy and copy_file_to_clipboard(res.paste):
        print("    El texto para publicar ya esta en el portapapeles: pegalo (Ctrl+V) junto a la imagen.")


def run(mode: str, count: int, seed: int | None, args, kit: FontKit) -> int:
    rng = random.Random(seed)
    for i in range(count):
        chosen = choose_mode(mode, args.out, rng)
        s = seed + i if seed is not None else secrets.randbits(32)
        try:
            generate(chosen, s, args, kit)
        except Exception as e:           # el menu sigue vivo si falla una imagen
            print(f"ERROR: {e}")
            return 1
    return 0


def pick_style(args, kit: FontKit) -> FontKit:
    print("\nEstilos: " + ", ".join(STYLE_NAMES) + "  (o la ruta de un .ttf / el nombre de una fuente instalada)")
    raw = ask("Estilo [Enter = dejar el actual]: ")
    if not raw or raw == "0":
        return kit
    try:
        if raw in STYLE_NAMES:
            args.estilo, args.fuente = raw, None
        else:
            args.fuente = raw
        new = make_kit(args.estilo, args.fuente)
    except FileNotFoundError as e:
        print(e)
        return kit
    print("Fuentes:", new.describe())
    return new


def interactive(args) -> int:
    kit = make_kit(args.estilo, args.fuente)
    while True:
        print(MENU.format(font=kit.describe()))
        choice = ask("Elige una opcion [0-7]: ")
        if choice == "0":
            print("Hasta luego.")
            return 0
        if choice == "6":
            kit = pick_style(args, kit)
            continue
        if choice == "7":
            print("\n" + "\n".join(hist.stats(hist.load(args.out))))
            continue
        if choice not in CHOICES:
            print("Opcion no valida.")
            continue
        raw = ask("Cantidad de imagenes [1]: ") or "1"
        if not raw.isdigit() or int(raw) < 1:
            print("Cantidad no valida.")
            continue
        seed_raw = ask("Semilla (Enter = aleatoria): ")
        if seed_raw and not seed_raw.lstrip("-").isdigit():
            print("Semilla no valida.")
            continue
        run(CHOICES[choice], int(raw), int(seed_raw) if seed_raw else None, args, kit)
        print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modo", choices=[*MODES, "aleatorio"], help="salta el menu y genera directamente")
    ap.add_argument("--count", type=int, default=1, help="imagenes a generar con --modo")
    ap.add_argument("--seed", type=int, default=None, help="semilla (por defecto: aleatoria)")
    ap.add_argument("--estilo", choices=STYLE_NAMES, default="auto", help="familia de letra preferida")
    ap.add_argument("--fuente", default=None, help="ruta de un .ttf/.otf o nombre de una fuente instalada")
    ap.add_argument("--formato", choices=["png", "jpg"], default="png")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="carpeta de salida (por defecto output_imagenes)")
    ap.add_argument("--no-copy", action="store_true", help="no copiar el texto de publicacion al portapapeles")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not args.modo:
        return interactive(args)
    try:
        kit = make_kit(args.estilo, args.fuente)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return 1
    print(f"Fuentes: {kit.describe()}")
    return run(args.modo, args.count, args.seed, args, kit)


if __name__ == "__main__":
    sys.exit(main())
