"""Busqueda de fuentes TrueType gruesas para las imagenes del feed.

Orden de busqueda: carpeta ``fonts/`` del proyecto (pon aqui Montserrat, Poppins, Comic Neue... en .ttf/.otf), carpetas del
usuario y del sistema. Solo se aceptan fuentes que tengan los signos que usan los retos (× ÷ − ¿ ¡ ñ tildes). Si no hay
ninguna, se usa la fuente por defecto de Pillow (se ve, pero sin gracia): el programa avisa.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from PIL import ImageFont

ROOT = Path(__file__).resolve().parent.parent.parent
FONT_DIRS = (
    ROOT / "fonts",
    Path.home() / ".fonts",
    Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts",
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
    Path("/usr/share/fonts"), Path("/usr/local/share/fonts"),
    Path("/Library/Fonts"), Path("/System/Library/Fonts"), Path.home() / "Library" / "Fonts",
)
REQUIRED = "×÷−¿¡ñáéíóúÁÉÍÓÚ%?+=()"         # caracteres que dibujan los retos
_EXT = {".ttf", ".otf"}

# Preferencias por estilo y por rol: «black» = titulares (lo mas grueso), «bold» = textos de apoyo.
STYLES = {
    "montserrat": {"black": ("Montserrat-Black", "Montserrat-ExtraBold", "Montserrat-Bold"),
                   "bold": ("Montserrat-ExtraBold", "Montserrat-Bold", "Montserrat-SemiBold")},
    "poppins": {"black": ("Poppins-Black", "Poppins-ExtraBold", "Poppins-Bold"),
                "bold": ("Poppins-ExtraBold", "Poppins-Bold", "Poppins-SemiBold")},
    "comic": {"black": ("ComicNeue-Bold", "ComicRelief-Bold", "comicbd", "ComicSansMS-Bold"),
              "bold": ("ComicNeue-Bold", "ComicRelief-Bold", "comicbd", "ComicSansMS-Bold")},
    "impacto": {"black": ("Anton-Regular", "Impact", "impact"), "bold": ("Anton-Regular", "Impact", "impact", "arialbd")},
}
UNIVERSAL = {
    "black": ("Montserrat-Black", "Poppins-Black", "Anton-Regular", "ariblk", "seguibl", "Impact", "arialbd",
              "DejaVuSans-Bold", "LiberationSans-Bold"),
    "bold": ("Montserrat-ExtraBold", "Montserrat-Bold", "Poppins-Bold", "arialbd", "segoeuib", "DejaVuSans-Bold",
             "LiberationSans-Bold"),
}
STYLE_NAMES = ("auto", *STYLES)


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _index() -> dict:
    """{nombre normalizado sin extension: ruta}; la primera carpeta de FONT_DIRS que tenga la fuente gana."""
    found: dict = {}
    for base in FONT_DIRS:
        if not base.is_dir():
            continue
        try:
            for path in base.rglob("*"):
                if path.suffix.lower() in _EXT:
                    found.setdefault(_norm(path.stem), path)
        except OSError:
            continue
    return found


def covers(path: Path, chars: str = REQUIRED) -> bool:
    """True si la fuente dibuja todos los `chars` (compara con el glifo «no definido» de la propia fuente)."""
    try:
        font = ImageFont.truetype(str(path), 40)
        missing = font.getmask("\uffff")
        for ch in chars:
            mask = font.getmask(ch)
            if mask.size == (0, 0) or (mask.size == missing.size and mask.tobytes() == missing.tobytes()):
                return False
        return True
    except OSError:
        return False


def resolve(style: str = "auto", forced: str | None = None, index: dict | None = None) -> dict:
    """{'black': Path|None, 'bold': Path|None}. `forced` = ruta a un .ttf o nombre de fuente instalada."""
    index = _index() if index is None else index
    if forced:
        p = Path(forced).expanduser()
        path = p if p.is_file() else index.get(_norm(Path(forced).stem))
        if path is None:
            raise FileNotFoundError(f"No encuentro la fuente «{forced}» (ponla en {ROOT / 'fonts'} o indica su ruta).")
        return {"black": path, "bold": path}
    out = {}
    for role in ("black", "bold"):
        names = (*STYLES.get(style, {}).get(role, ()), *UNIVERSAL[role])
        out[role] = next((index[_norm(n)] for n in names if _norm(n) in index and covers(index[_norm(n)])), None)
    return out


class FontKit:
    """Entrega fuentes por rol y tamaño (con cache). Sin fuentes TrueType usa la de Pillow."""

    def __init__(self, style: str = "auto", forced: str | None = None, index: dict | None = None):
        self.style, self.paths = style, resolve(style, forced, index)
        self._cache: dict = {}

    def get(self, role: str, size: int) -> ImageFont.FreeTypeFont:
        size = max(8, int(size))
        key = (role, size)
        if key not in self._cache:
            path = self.paths.get(role)
            try:
                self._cache[key] = ImageFont.truetype(str(path), size) if path else ImageFont.load_default(size)
            except OSError:
                self._cache[key] = ImageFont.load_default(size)
        return self._cache[key]

    @property
    def found(self) -> bool:
        return all(self.paths.values())

    def describe(self) -> str:
        names = {role: (p.stem if p else "fuente por defecto de Pillow") for role, p in self.paths.items()}
        return f"titulares: {names['black']} | textos: {names['bold']}"
