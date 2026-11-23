"""Generacion con los scripts del proyecto (subprocess), busqueda de lo ultimo generado y comprobaciones previas."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .envfile import ROOT, Config

IMAGE_EXT = (".png", ".jpg", ".jpeg")
VIDEO_EXT = (".mp4",)
PUBLISH_SUFFIX = "_publicar.txt"


class GenerationError(Exception):
    """El script generador fallo, agoto el tiempo o no dejo archivos."""


@dataclass(frozen=True)
class Artifact:
    kind: str                  # "foto" | "video"
    media: Path
    copy: str                  # texto de publicacion (el de `_publicar.txt`)
    alt: str | None            # texto alternativo (solo imagenes)
    source: Path               # `_publicar.txt` de donde salio el copy


# --------------------------------------------------------------------------- entorno de los generadores
# Modulos que necesita cada generador (el video usa la GPU y la voz; la imagen solo Pillow y NumPy)
REQUIRED_MODULES = {"foto": ("PIL", "numpy"), "video": ("moderngl", "edge_tts", "numpy")}


def _text(x) -> str:
    return x.decode("utf-8", "replace") if isinstance(x, bytes) else (x or "")


def project_python(root: Path = ROOT) -> str:
    """Python con el que se lanzan los generadores: el del `.venv` del proyecto si existe (alli estan moderngl,
    edge-tts y Pillow), aunque el autopiloto se haya ejecutado desde otro entorno (conda, Python del sistema...)."""
    for rel in ((".venv", "Scripts", "python.exe"), (".venv", "bin", "python")):
        candidate = Path(root).joinpath(*rel)
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def missing_modules(python: str, modules, runner=subprocess.run) -> list:
    """Modulos de `modules` que ese Python no puede importar (lista vacia = todo en orden)."""
    code = "import importlib.util as u,sys;print('MISSING:'+','.join(m for m in sys.argv[1:] if u.find_spec(m) is None))"
    try:
        proc = runner([python, "-c", code, *modules], capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as e:
        raise GenerationError(f"no se pudo ejecutar {python}: {e}") from None
    for line in _text(proc.stdout).splitlines():
        if line.startswith("MISSING:"):
            return [m for m in line[len("MISSING:"):].split(",") if m]
    if proc.returncode != 0:
        tail = " ".join(_text(proc.stderr).strip().splitlines()[-2:])
        raise GenerationError(f"{python} no funciona: {tail}")
    return []


def ensure_ffmpeg_on_path() -> bool:
    """True si ffmpeg y ffprobe estan en el PATH. Si no, prueba la carpeta donde winget instala FFmpeg (lo mismo que hace
    iniciar.bat) y la añade al PATH de este proceso, para que el autopiloto funcione aunque no se lance con el .bat."""
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return True
    base = os.environ.get("LOCALAPPDATA")
    if base:
        for pkg in sorted(Path(base, "Microsoft", "WinGet", "Packages").glob("Gyan.FFmpeg*")):
            for bindir in sorted(pkg.glob("ffmpeg-*/bin")):
                if (bindir / "ffmpeg.exe").exists():
                    os.environ["PATH"] = f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"
                    return True
    return False


# --------------------------------------------------------------------------- comandos y ejecucion
def image_command(cfg: Config, python: str | None = None) -> list:
    """generador_imagenes.py en modo aleatorio inteligente: una imagen, sin tocar el portapapeles."""
    return [python or project_python(), str(ROOT / "generador_imagenes.py"), "--modo", "aleatorio", "--count", "1",
            "--no-copy", "--out", str(cfg.image_out)]


def video_command(cfg: Config, python: str | None = None) -> list:
    """main.py en modo aleatorio inteligente: un video, sin tocar el portapapeles."""
    return [python or project_python(), str(ROOT / "main.py"), "--mode", "random", "--count", "1", "--no-copy",
            "--out", str(cfg.video_out)]


def run_generator(cmd: list, timeout_s: float, runner=subprocess.run, cwd: Path = ROOT) -> str:
    """Ejecuta el generador. Devuelve su salida; lanza GenerationError si falla o se pasa del tiempo."""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    try:
        proc = runner(cmd, cwd=str(cwd), capture_output=True, timeout=timeout_s, env=env)
    except subprocess.TimeoutExpired:
        raise GenerationError(f"el generador tardó más de {timeout_s / 60:.0f} min y se canceló") from None
    except OSError as e:
        raise GenerationError(f"no se pudo ejecutar el generador: {e}") from None
    text = _text(proc.stdout) + _text(proc.stderr)
    if proc.returncode != 0:
        tail = "\n".join(text.strip().splitlines()[-8:])
        raise GenerationError(f"el generador terminó con código {proc.returncode}:\n{tail}")
    return text


# --------------------------------------------------------------------------- lo generado
def read_copy(publish_txt: Path) -> str:
    text = Path(publish_txt).read_text("utf-8-sig").strip()
    if not text:
        raise ValueError(f"{publish_txt.name} está vacío")
    return text


def read_alt(full_txt: Path) -> str | None:
    """Texto alternativo del `.txt` completo (seccion «TEXTO ALTERNATIVO»), si existe."""
    try:
        text = Path(full_txt).read_text("utf-8-sig")
    except OSError:
        return None
    m = re.search(r"TEXTO ALTERNATIVO[^\n]*\n(.+?)\n\s*\n", text, re.S)
    return m.group(1).strip() if m else None


def fallback_copy(full_txt: Path) -> str | None:
    """Bloque «COPIAR Y PEGAR» del `.txt` completo (por si faltara `_publicar.txt`)."""
    try:
        text = Path(full_txt).read_text("utf-8-sig")
    except OSError:
        return None
    m = re.search(r"=== COPIAR Y PEGAR[^\n]*===\n(.+?)\n=== FIN", text, re.S)
    return m.group(1).strip() if m else None


def find_artifact(out_dir: Path, kind: str, since: float) -> Artifact:
    """El `_publicar.txt` mas reciente (modificado desde `since`) con su imagen o video y su texto alternativo."""
    exts = IMAGE_EXT if kind == "foto" else VIDEO_EXT
    out_dir = Path(out_dir)
    found = sorted((p for p in out_dir.rglob("*" + PUBLISH_SUFFIX) if p.stat().st_mtime >= since),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    for txt in found:
        stem = txt.name[:-len(PUBLISH_SUFFIX)]
        media = next((txt.with_name(stem + e) for e in exts if txt.with_name(stem + e).exists()), None)
        if media:
            return Artifact(kind, media, read_copy(txt), read_alt(txt.with_name(stem + ".txt")) if kind == "foto" else None, txt)
    raise GenerationError(f"no encuentro un archivo nuevo ({'/'.join(exts)} + {PUBLISH_SUFFIX}) en {out_dir}")


# --------------------------------------------------------------------------- comprobaciones previas
def probe_video(path: Path, runner=subprocess.run) -> dict | None:
    """Datos del video con ffprobe (None si ffprobe no esta disponible)."""
    try:
        p = runner(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
                   capture_output=True, text=True, timeout=60)
        return json.loads(p.stdout) if p.returncode == 0 and p.stdout else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def check_reel(info: dict | None) -> tuple:
    """(errores, avisos) segun las especificaciones de Reels de Meta: 9:16, minimo 540x960, 24-60 fps, 3-90 s, AAC 48 kHz."""
    if not info:
        return [], ["ffprobe no disponible: no se comprobaron las especificaciones del video."]
    errors, warns = [], []
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not v:
        return ["el archivo no tiene pista de video"], []
    w, h = int(v.get("width", 0)), int(v.get("height", 0))
    num, _, den = str(v.get("r_frame_rate", "0/1")).partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    dur = float(info.get("format", {}).get("duration", 0) or 0)
    if w < 540 or h < 960:
        errors.append(f"resolución {w}x{h} menor que el mínimo 540x960")
    if h and abs(w / h - 9 / 16) > 0.01:
        warns.append(f"relación {w}x{h} distinta de 9:16 (no se verá como Reel a pantalla completa)")
    if not 24 <= fps <= 60:
        errors.append(f"{fps:.0f} fps fuera del rango 24-60")
    if not 3 <= dur <= 90:
        errors.append(f"duración {dur:.1f} s fuera del rango 3-90 s")
    if v.get("codec_name") not in ("h264", "hevc", "vp9", "av1"):
        warns.append(f"códec de video {v.get('codec_name')} poco habitual")
    if a is None:
        warns.append("el video no tiene audio")
    else:
        if a.get("codec_name") != "aac":
            warns.append(f"audio {a.get('codec_name')} (Meta recomienda AAC)")
        if int(a.get("sample_rate", 48000)) != 48000 or int(a.get("channels", 2)) != 2:
            warns.append("el audio no es estéreo a 48 kHz")
    return errors, warns


def check_photo(path: Path) -> tuple:
    """(errores, avisos) para una foto: maximo 4 MB; los PNG grandes pueden verse pixelados."""
    size = Path(path).stat().st_size
    errors = [f"la imagen pesa {size / 1e6:.1f} MB (el máximo es 4 MB)"] if size > 4_000_000 else []
    warns = [f"PNG de {size / 1e6:.1f} MB: Meta recomienda 1 MB o menos o puede pixelarse"] \
        if size > 1_000_000 and Path(path).suffix.lower() == ".png" else []
    return errors, warns
