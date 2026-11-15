"""Paradoja Infinita - generador procedural de videos para Facebook Reels / In-Stream.

Sin argumentos abre el menu interactivo.
Automatizacion (sin menu):  python main.py --mode random --count 5
"""
import argparse
import random
import secrets
import shutil
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

from paradoja.audio import build_bed
from paradoja.config import VideoSpec
from paradoja.encoder import FfmpegEncoder, pick_codec
from paradoja.metadata import video_slug, write_metadata
from paradoja.renderer import GpuRenderer
from paradoja.scene import MODES, build_scene
from paradoja.script_es import build_script
from paradoja.subtitles import build_ass
from paradoja.timeline import Timeline
from paradoja.tts import synthesize_all

ROOT = Path(__file__).parent
MODE_NAMES = {
    "anomaly": "Reto de anomalia", "illusion": "Ilusion optica de movimiento", "loop": "Bucle infinito",
    "sync": "Reto de sincronizacion (pause game)", "ishihara": "Test de vision (Ishihara)",
    "swarm": "Seguimiento de enjambre", "magiceye": "Ojo magico (autostereograma)",
    "contrast": "Ilusion de contraste simultaneo",
}

MENU = """
==================================================================
   PARADOJA INFINITA  -  generador de videos procedurales
==================================================================
  [1] Reto de anomalia      (encuentra la figura distinta)
  [2] Ilusion optica        (patrones geometricos enganosos)
  [3] Bucle infinito        (perfect loop geometrico)
  [4] Sincronizacion        (pausa justo cuando la figura encaja)
  [5] Test de vision        (Ishihara: numero/figura oculta)
  [6] Seguimiento enjambre  (sigue el punto rojo)
  [7] Ojo magico            (figura 3D oculta al desenfocar)
  [8] Contraste simultaneo  (el bloque que nunca cambio)
  [9] 100% aleatorio        (el sistema elige entre los 8 tipos)
  [0] Salir
------------------------------------------------------------------"""
CHOICES = {"1": "anomaly", "2": "illusion", "3": "loop", "4": "sync", "5": "ishihara", "6": "swarm",
           "7": "magiceye", "8": "contrast", "9": "random"}


def pick_mode(mode: str, seed: int) -> str:
    """'random' -> el modo lo decide la semilla (reproducible)."""
    return random.Random(seed ^ 0xA5A5).choice(MODES) if mode == "random" else mode


def generate(mode: str, seed: int, args) -> int:
    mode = pick_mode(mode, seed)
    spec = VideoSpec(duration=args.duration)
    scene = build_scene(seed, mode, spec)
    tl = Timeline(spec, scene)
    slug = video_slug(scene)
    # output/<AAAA-MM-DD>/<slug>/<slug>.mp4 + .txt  (la fecha es la del dia en que se genera)
    folder = args.out / date.today().isoformat() / slug
    out = folder / f"{slug}.mp4"
    work = folder / "work"
    work.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    print(f"\nModo: {MODE_NAMES[mode]} | semilla: {seed} | paleta: {scene.palette.name}")
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

    meta = write_metadata(out.with_suffix(".txt"), scene, tl, out.name)

    print("[4/4] Verificando...")
    info = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=codec_name,width,height,r_frame_rate:format=duration", "-of", "default=nw=1", str(out)],
        capture_output=True, text=True).stdout.split()
    print("  " + " | ".join(info))
    if not args.keep_work:
        shutil.rmtree(work, ignore_errors=True)
    print(f"Listo en {time.perf_counter() - t0:.1f}s -> {out}\n  Metadata -> {meta}")
    return 0


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return "0"


def interactive(args) -> int:
    while True:
        print(MENU)
        choice = ask("Elige una opcion [0-9]: ")
        if choice == "0":
            print("Hasta luego.")
            return 0
        if choice not in CHOICES:
            print("Opcion no valida.")
            continue

        raw = ask("Semilla (Enter = aleatoria): ")
        count_raw = ask("Cantidad de videos [1]: ") or "1"
        if not count_raw.isdigit() or int(count_raw) < 1:
            print("Cantidad no valida.")
            continue
        count = int(count_raw)
        if raw and not raw.lstrip("-").isdigit():
            print("Semilla no valida.")
            continue
        for i in range(count):
            seed = int(raw) + i if raw else secrets.randbits(32)
            try:
                generate(CHOICES[choice], seed, args)
            except Exception as e:  # el menu sigue vivo si falla un video
                print(f"ERROR: {e}")
                break
        print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=[*MODES, "random"], help="salta el menu y genera directamente")
    ap.add_argument("--count", type=int, default=1, help="videos a generar con --mode")
    ap.add_argument("--seed", type=int, default=None, help="semilla (por defecto aleatoria)")
    ap.add_argument("--duration", type=float, default=63.0, help="segundos (61.5-65)")
    ap.add_argument("--voice", default="es-MX-JorgeNeural")
    ap.add_argument("--codec", default="auto", choices=["auto", "h264_nvenc", "hevc_nvenc", "libx264"])
    ap.add_argument("--out", type=Path, default=ROOT / "output")
    ap.add_argument("--keep-work", action="store_true", help="conserva audio/subtitulos/log intermedios")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if not args.mode:
        return interactive(args)
    rc = 0
    for i in range(args.count):
        seed = (args.seed + i) if args.seed is not None else secrets.randbits(32)
        rc = generate(args.mode, seed, args) or rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
