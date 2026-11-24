"""Genera una imagen del feed con su .txt de publicacion: reto + dibujo + copy + historial."""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import copy_feed, history as hist, puzzles as P
from .canvas import H, W
from .fonts import FontKit
from .render import render

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUT = ROOT / "output_imagenes"
MODE_LABEL = {
    "pemdas": "La Ecuación de la Discordia (PEMDAS)", "cubos": "El Reto de los Cubos Isométricos",
    "fracciones": "Fracciones Engañosas", "opciones": "Opción Múltiple Tramposa",
}
BAIT_NOTE = ("El copy pide la respuesta con una pregunta, que es lo permitido. Evita añadir «comenta SÍ o NO», «etiqueta a 3 "
             "amigos» o «comparte para ganar»: Meta lo trata como cebo de interacción y reduce el alcance.")


@dataclass
class Result:
    mode: str
    seed: int
    slug: str
    image: Path
    txt: Path
    paste: Path
    puzzle: P.Puzzle
    post: dict
    palette: str


def make_slug(mode: str, puz: P.Puzzle, seed: int) -> str:
    return f"{mode}_{puz.detail}_{seed}"


def _txt(res_name: str, mode: str, puz: P.Puzzle, post: dict, seed: int, palette: str, kit: FontKit) -> str:
    variables = [f"Semilla: {seed}", f"Paleta: {palette}", f"Fuentes: {kit.describe()}", f"Reto: {puz.key}"]
    if puz.kind == "cubos":
        variables.append(f"Cubos visibles: {puz.extra['visible']} | ocultos: {puz.extra['hidden']}")
    return (
        "=== COPIAR Y PEGAR EN LA PUBLICACIÓN (texto + hashtags) ===\n"
        f"{post['paste']}\n"
        "=== FIN DEL TEXTO A PEGAR ===\n\n"
        f"ARCHIVO: {res_name} ({W}x{H})\n"
        f"TIPO DE IMAGEN: {MODE_LABEL[mode]}\n\n"
        f"RESPUESTA CORRECTA (CONTROL INTERNO, NO PUBLICAR): {puz.answer}\n"
        f"EXPLICACIÓN: {puz.explanation}\n"
        f"RESPUESTA EQUIVOCADA MÁS COMÚN: {puz.trap or '—'}\n\n"
        "COMENTARIO PARA REVELAR LA RESPUESTA (publícalo unas horas después, no antes):\n"
        f"{post['reveal']}\n\n"
        "TEXTO ALTERNATIVO (accesibilidad: pégalo en «Editar texto alternativo»):\n"
        f"{post['alt']}\n\n"
        f"AVISO: {BAIT_NOTE}\n\n"
        "VARIABLES (control interno):\n" + "\n".join(f"  - {v}" for v in variables) + "\n\n"
        f"HASHTAGS:\n{' '.join(post['tags'])}\n"
    )


def generate_one(mode: str, seed: int, kit: FontKit, out_root: Path = DEFAULT_OUT, fmt: str = "png",
                 record: bool = True) -> Result:
    """Crea `<out_root>/<AAAA-MM-DD>/<slug>.png|jpg` + `<slug>.txt` + `<slug>_publicar.txt` y anota el historial."""
    history = hist.load(out_root)
    puz = P.generate(mode, seed, hist.recent_keys(history))
    img, palette = render(puz, kit, seed)
    post = copy_feed.build_post(puz, seed, hist.recent_posts(history))
    base = make_slug(mode, puz, seed)
    day = Path(out_root) / date.today().isoformat()
    day.mkdir(parents=True, exist_ok=True)
    ext = "jpg" if fmt == "jpg" else "png"
    slug, n = base, 2
    while (day / f"{slug}.{ext}").exists():                      # mismo nombre (misma semilla y detalle): no pisar la imagen
        slug, n = f"{base}_{n}", n + 1
    image = day / f"{slug}.{ext}"
    if ext == "jpg":
        img.save(image, quality=95, subsampling=0, optimize=True)
    else:
        img.save(image, optimize=True)
    txt, paste = day / f"{slug}.txt", day / f"{slug}_publicar.txt"
    txt.write_text(_txt(image.name, mode, puz, post, seed, palette, kit), encoding="utf-8-sig")
    paste.write_text(post["paste"] + "\n", encoding="utf-8-sig")
    if record:
        hist.append(out_root, {"date": date.today().isoformat(), "seed": seed, "mode": mode, "slug": slug,
                               "key": puz.key, "post": post["hash"], "palette": palette})
    return Result(mode, seed, slug, image, txt, paste, puz, post, palette)


def choose_mode(requested: str, out_root: Path, rng: random.Random, avoid=()) -> str:
    """`aleatorio` elige el tipo menos usado recientemente (sin los de `avoid` si hay otros); cualquier otro valor se devuelve tal cual."""
    return hist.pick_mode(hist.load(out_root), rng, avoid=avoid) if requested == "aleatorio" else requested
