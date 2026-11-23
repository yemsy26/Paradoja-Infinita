"""Paradoja Infinita - generador procedural de videos para Facebook Reels / In-Stream.

Sin argumentos abre el menu interactivo.
Automatizacion (sin menu):  python main.py --mode random --count 5
"""
import argparse
import secrets
import shutil
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

from paradoja.audio import build_bed
from paradoja.catalog import append_history, choose, entry_for, load_history, pick_mode, recent_posts, recent_titles, stats
from paradoja.clipboard import copy_file_to_clipboard
from paradoja.config import VideoSpec
from paradoja.encoder import FfmpegEncoder, pick_codec
from paradoja.metadata import AI_LABEL_NOTE, MODE_LABEL, video_slug, write_metadata
from paradoja.renderer import GpuRenderer
from paradoja.scene import MODES, TYPES, build_scene
from paradoja.script_es import build_script
from paradoja.subtitles import build_ass
from paradoja.timeline import Timeline
from paradoja.tts import synthesize_all

ROOT = Path(__file__).parent

MENU = """
==================================================================
   PARADOJA INFINITA  -  generador de videos procedurales
==================================================================
  [1] Aleatorio inteligente   (RECOMENDADO) elige el reto menos
                              usado recientemente y evita repetir
  [2] Video mixto             5-7 mini-retos distintos en 1 video
  [3] Elegir un reto concreto ({n_types} retos + bucle)
  [4] Estadisticas y ultimos videos
  [0] Salir
------------------------------------------------------------------"""


def generate(mode: str, seed: int, args) -> int:
    """Genera un video (y su .txt) en output/<fecha>/<slug>/ y lo registra en el historial."""
    mode = pick_mode(mode, seed)
    spec = VideoSpec(duration=args.duration)
    scene = build_scene(seed, mode, spec)
    tl = Timeline(spec, scene)
    slug = video_slug(scene)
    folder = args.out / date.today().isoformat() / slug
    out = folder / f"{slug}.mp4"
    work = folder / "work"
    work.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    print(f"\nFormato: {MODE_LABEL[mode]} | semilla: {seed} | paleta: {scene.palette.name}")
    if scene.acts:
        print("  Retos: " + ", ".join(TYPES[a.type].menu for a in scene.acts))
    print("[1/4] Voz (edge-tts)...")
    clips = synthesize_all(build_script(scene, tl), args.voice, ROOT / ".cache" / "tts", spec.duration)

    print("[2/4] Audio procedural + subtitulos...")
    bed = build_bed(work / "bed.wav", spec.duration, tl.sfx(), seed, loop=tl.is_loop)
    build_ass(work / "subs.ass", clips, tl, spec)

    print("[3/4] Render GPU + codificacion...")
    codec = pick_codec(args.codec)
    renderer = GpuRenderer(spec, scene)
    print(f"  GPU de render: {renderer.gpu_name} | codec: {codec}")
    if "nvidia" not in renderer.gpu_name.lower():
        print("  AVISO: OpenGL no usa la RTX 4060 (ver README, 'Forzar la RTX'). Funciona, pero mas lento.")
    enc = FfmpegEncoder(spec, codec, clips, bed, "subs.ass", out, work)
    try:
        for frame in renderer.frames(tl):
            enc.write(frame)
    finally:
        rc = enc.close()
    if rc != 0:
        print(f"FFmpeg fallo (codigo {rc}). Log: {work / 'ffmpeg.log'}")
        return rc

    # portada: el fotograma con el gancho a pantalla completa (sube esta imagen como miniatura del Reel)
    cover = out.with_name(f"{slug}_portada.jpg")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1.0", "-i", str(out), "-frames:v", "1", "-q:v", "2", str(cover)],
                   capture_output=True)

    history = load_history(args.out)
    meta, title, digest = write_metadata(out.with_suffix(".txt"), scene, tl, out.name, recent_titles(history),
                                         recent_posts(history))
    append_history(args.out, entry_for(scene, slug, title, digest))

    print("[4/4] Verificando...")
    info = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=codec_name,width,height,r_frame_rate:format=duration", "-of", "default=nw=1", str(out)],
        capture_output=True, text=True).stdout.split()
    print("  " + " | ".join(info))
    if not args.keep_work:
        shutil.rmtree(work, ignore_errors=True)
    post_file = meta.with_name(f"{meta.stem}_publicar.txt")
    copied = (not getattr(args, "no_copy", False)) and copy_file_to_clipboard(post_file)
    print(f"Listo en {time.perf_counter() - t0:.1f}s -> {out}\n  Metadata -> {meta}"
          + (f"\n  Portada  -> {cover}" if cover.exists() else "")
          + f"\n  Publicar -> {post_file}"
          + ("\n  El texto para publicar ya esta en el portapapeles: pegalo (Ctrl+V) en la publicacion." if copied else "")
          + f"\n  Antes de publicar: {AI_LABEL_NOTE}")
    return 0


def next_target(mode: str, seed, args) -> tuple:
    """(semilla, formato). Sin semilla explicita, `choose` elige la opcion mas novedosa segun el historial."""
    if seed is not None:
        return seed, pick_mode(mode, seed)
    if mode in ("random", "mix"):
        return choose(mode, load_history(args.out), VideoSpec(duration=args.duration))
    return secrets.randbits(32), mode


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return "0"


def ask_count(default: int = 1) -> int:
    raw = ask(f"Cantidad de videos [{default}]: ") or str(default)
    return int(raw) if raw.isdigit() and int(raw) >= 1 else 0


def concrete_menu() -> str:
    """Lista de retos por categoria. Devuelve el nombre del formato elegido o '' si se cancela."""
    order = []
    print("\n--- Elegir un reto concreto " + "-" * 38)
    for cat in dict.fromkeys(t.category for t in TYPES.values()):
        print(f"  {cat.upper()}")
        for t in TYPES.values():
            if t.category == cat:
                order.append(t.name)
                print(f"    [{len(order):>2}] {t.menu:<16} {t.desc}")
    order.append("loop")
    print(f"  ESPECIAL\n    [{len(order):>2}] {'Bucle infinito':<16} Perfect loop geometrico hipnotico")
    print("    [ 0] Volver")
    raw = ask("Elige un reto: ")
    return order[int(raw) - 1] if raw.isdigit() and 1 <= int(raw) <= len(order) else ""


def interactive(args) -> int:
    while True:
        print(MENU.format(n_types=len(TYPES)))
        choice = ask("Elige una opcion [0-4]: ")
        if choice == "0":
            print("Hasta luego.")
            return 0
        if choice == "4":
            print("\n" + "\n".join(stats(load_history(args.out))))
            continue
        if choice not in ("1", "2", "3"):
            print("Opcion no valida.")
            continue

        mode, seed_raw = {"1": "random", "2": "mix"}.get(choice), ""
        if choice == "3":
            mode = concrete_menu()
            if not mode:
                continue
            seed_raw = ask("Semilla (Enter = aleatoria): ")
            if seed_raw and not seed_raw.lstrip("-").isdigit():
                print("Semilla no valida.")
                continue
        count = ask_count()
        if not count:
            print("Cantidad no valida.")
            continue
        for i in range(count):
            seed, fmt = next_target(mode, int(seed_raw) + i if seed_raw else None, args)
            try:
                generate(fmt, seed, args)
            except Exception as e:  # el menu sigue vivo si falla un video
                print(f"ERROR: {e}")
                break
        print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=[*MODES, "random"], help="salta el menu y genera directamente")
    ap.add_argument("--count", type=int, default=1, help="videos a generar con --mode")
    ap.add_argument("--seed", type=int, default=None, help="semilla (por defecto: la mas novedosa segun el historial)")
    ap.add_argument("--duration", type=float, default=63.0, help="segundos (61.5-65)")
    ap.add_argument("--voice", default="es-MX-JorgeNeural")
    ap.add_argument("--codec", default="auto", choices=["auto", "h264_nvenc", "hevc_nvenc", "libx264"])
    ap.add_argument("--out", type=Path, default=ROOT / "output")
    ap.add_argument("--keep-work", action="store_true", help="conserva audio/subtitulos/log intermedios")
    ap.add_argument("--no-copy", action="store_true", help="no copiar el texto de publicacion al portapapeles")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if not args.mode:
        return interactive(args)
    rc = 0
    for i in range(args.count):
        seed, fmt = next_target(args.mode, (args.seed + i) if args.seed is not None else None, args)
        rc = generate(fmt, seed, args) or rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
