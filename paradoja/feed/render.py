"""Dibujo de las 4 imagenes del feed (1080x1350) con Pillow: formas, texto y colores, sin IA generativa."""
from __future__ import annotations

import math
import random

from PIL import ImageDraw

from . import puzzles as P
from .canvas import ART_TOP, MARGIN, PALETTES, W, Canvas, S, darken, lighten
from .fonts import FontKit

YELLOW = (255, 214, 10)
WHITE = (255, 255, 255)
CREAM = (255, 250, 236)
HEAD_Y, HEAD_W, HEAD_H = 215, 930, 170          # titular: centro y caja

PEMDAS_HEADS = ("¡La respuesta NO es {n}!", "¡Cuidado! La respuesta NO es {n}", "¿{n}? ¡Esa NO es la respuesta!",
                "¡{n} es incorrecto!")
CUBE_SUBS = ("El 90% falla.", "Solo 1 de cada 10 acierta.", "Casi nadie lo logra.", "El 95% se equivoca.")
OPTION_HEADS = ("¡Cuidado con la trampa!", "No te dejes engañar", "Piénsalo bien antes de responder",
                "Solo una es correcta")
OPTION_COLORS = ((255, 64, 129), (0, 184, 212), (255, 171, 0), (76, 217, 100))


# =========================================================================== 1. ecuacion
def _balanced(cv: Canvas, eq: str) -> str:
    """Ecuacion en una sola linea si cabe en letra grande; si no, en dos lineas de largo parecido (cortando tras un
    operador y nunca dentro de un parentesis)."""
    if cv.fit(eq, "black", 900, 200, 190, max_lines=1)[2] >= 104:
        return eq
    toks, best = eq.split(" "), None
    depth, cut = 0, []
    for i, t in enumerate(toks[:-1]):
        depth += t.count("(") - t.count(")")
        if depth == 0 and t in P.OPS:
            cut.append(i + 1)
    for i in cut or range(1, len(toks)):
        gap = abs(len(" ".join(toks[:i])) - len(" ".join(toks[i:])))
        if best is None or gap < best[0]:
            best = (gap, i)
    return " ".join(toks[:best[1]]) + chr(10) + " ".join(toks[best[1]:])


def draw_pemdas(cv: Canvas, puz: P.Puzzle) -> None:
    rng, pal = cv.rng, cv.pal
    n = puz.trap
    cv.text(rng.choice(PEMDAS_HEADS).format(n=n), W / 2, HEAD_Y, HEAD_W, HEAD_H, "black", 112, fill=YELLOW)
    cv.face(W / 2, 372, 58, "shock")
    cv.card((MARGIN - 4, 470, W - MARGIN + 4, 900), radius=54, fill=(*pal.ink, 226), outline=YELLOW, outline_w=8)
    eq = _balanced(cv, puz.data["eq"])
    two = chr(10) in eq
    cv.text(eq, W / 2, 614 if two else 622, 900, 240 if two else 200, "black", 190, fill=WHITE, max_lines=2)
    cv.text("= ?", W / 2, 800, 500, 150, "black", 150, fill=YELLOW)
    cv.text("Resuélvelo sin calculadora", W / 2, 985, 900, 70, "bold", 52, fill=WHITE, stroke_ratio=0.06)
    cv.text("¿Cuál es el resultado?", W / 2, 1075, 900, 66, "black", 56, fill=YELLOW, stroke_ratio=0.06)


# =========================================================================== 2. cubos
def draw_cubes(cv: Canvas, puz: P.Puzzle) -> None:
    rng, pal = cv.rng, cv.pal
    cv.text("¿Cuántos cubos hay en total?", W / 2, HEAD_Y, HEAD_W, HEAD_H, "black", 104, fill=YELLOW)
    cv.text(rng.choice(CUBE_SUBS), W / 2, 372, 900, 66, "black", 60, fill=WHITE, stroke_ratio=0.06)
    heights, order = puz.data["heights"], puz.data["order"]
    cols, rows = puz.data["cols"], puz.data["rows"]
    floor = [P.proj(0, 0, 0), P.proj(cols, 0, 0), P.proj(cols, rows, 0), P.proj(0, rows, 0)]
    pts = floor + [q for c in order for f in P.cube_faces(*c).values() for q in f]
    minx, maxx = min(p[0] for p in pts), max(p[0] for p in pts)
    miny, maxy = min(p[1] for p in pts), max(p[1] for p in pts)
    box_w, box_h, cy = W - 2 * 70, 1125 - 470, (470 + 1125) / 2
    k = min(box_w / (maxx - minx), box_h / (maxy - miny), 150)
    ox, oy = W / 2 - (minx + maxx) / 2 * k, cy - (miny + maxy) / 2 * k

    def T(p, dx=0.0, dy=0.0):
        return (S(ox + p[0] * k + dx), S(oy + p[1] * k + dy))

    base = rng.choice(((255, 214, 10), (0, 229, 255), (255, 255, 255), (150, 255, 100), (255, 150, 30)))
    tone = {"top": lighten(base, 0.38), "right": base, "left": darken(base, 0.38)}
    ink, lw = pal.ink, max(3, S(k * 0.05))
    lay, d = cv.layer(), None
    d = ImageDraw.Draw(lay)
    d.polygon([T(p, 9, 15) for p in floor], fill=(0, 0, 0, 95))                        # sombra de la plataforma
    d.polygon([T(p) for p in floor], fill=(255, 255, 255, 60), outline=(255, 255, 255, 150), width=S(3))
    for i in range(1, cols):
        d.line([T(P.proj(i, 0, 0)), T(P.proj(i, rows, 0))], fill=(255, 255, 255, 90), width=S(2))
    for j in range(1, rows):
        d.line([T(P.proj(0, j, 0)), T(P.proj(cols, j, 0))], fill=(255, 255, 255, 90), width=S(2))
    for c in order:                                                                    # de atras hacia adelante
        for name in ("left", "right", "top"):
            poly = [T(p) for p in P.cube_faces(*c)[name]]
            d.polygon(poly, fill=tone[name])
            d.line(poly + [poly[0]], fill=ink, width=lw, joint="curve")
    cv.put(lay)


# =========================================================================== 3. fracciones
def _ngon(n: int, rot: int, cx: float, cy: float, width: float, height: float) -> list:
    """Vertices del poligono regular escalado para caber en width x height."""
    a0 = -math.pi / 2 + (math.pi / n if rot else 0.0)
    unit = [(math.cos(a0 + 2 * math.pi * i / n), math.sin(a0 + 2 * math.pi * i / n)) for i in range(n)]
    w = max(p[0] for p in unit) - min(p[0] for p in unit)
    h = max(p[1] for p in unit) - min(p[1] for p in unit)
    r = min(width / w, height / h)
    mx, my = (max(p[0] for p in unit) + min(p[0] for p in unit)) / 2, (max(p[1] for p in unit) + min(p[1] for p in unit)) / 2
    return [(cx + (p[0] - mx) * r, cy + (p[1] - my) * r) for p in unit]


def draw_fraction(cv: Canvas, puz: P.Puzzle) -> None:
    pal = cv.pal
    cv.text("¿Qué fracción representa la región gris?", W / 2, HEAD_Y, HEAD_W, HEAD_H + 10, "black", 96, fill=YELLOW,
            max_lines=3)
    cv.text("Escribe la fracción simplificada", W / 2, 396, 900, 52, "bold", 46, fill=WHITE, stroke_ratio=0.06)
    n, states = puz.data["n"], puz.data["states"]
    cy = (ART_TOP + 60 + 1130) / 2
    verts = _ngon(n, puz.data["rot"], W / 2, cy, 780, 640)
    center = (W / 2, sum(v[1] for v in verts) / n)
    center = (sum(v[0] for v in verts) / n, center[1])
    gray, white, ink = (142, 148, 163), (255, 255, 255), pal.ink
    big, small = max(4, S(8)), max(3, S(4))
    lay = cv.layer()
    d = ImageDraw.Draw(lay)

    def pt(p, dx=0.0, dy=0.0):
        return (S(p[0] + dx), S(p[1] + dy))

    d.polygon([pt(v, 10, 16) for v in verts], fill=(0, 0, 0, 100))                      # sombra
    for i, st in enumerate(states):
        b, c = verts[i], verts[(i + 1) % n]
        if isinstance(st, tuple):                                                       # triangulo grande partido en 4
            m = ((center[0] + b[0]) / 2, (center[1] + b[1]) / 2)
            q = ((center[0] + c[0]) / 2, (center[1] + c[1]) / 2)
            e = ((b[0] + c[0]) / 2, (b[1] + c[1]) / 2)
            for bit, tri in zip(st, ((center, m, q), (m, b, e), (q, e, c), (m, e, q))):
                poly = [pt(p) for p in tri]
                d.polygon(poly, fill=gray if bit else white)
                d.line(poly + [poly[0]], fill=ink, width=small, joint="curve")
        else:
            d.polygon([pt(center), pt(b), pt(c)], fill=gray if st == "G" else white)
    for i in range(n):                                                                  # lados de los triangulos grandes
        b, c = verts[i], verts[(i + 1) % n]
        d.line([pt(center), pt(b), pt(c), pt(center)], fill=ink, width=big, joint="curve")
    d.line([pt(v) for v in verts + [verts[0]]], fill=ink, width=big + S(3), joint="curve")
    cv.put(lay)


# =========================================================================== 4. opcion multiple
def draw_options(cv: Canvas, puz: P.Puzzle) -> None:
    rng, pal = cv.rng, cv.pal
    data = puz.data
    cv.text(rng.choice(OPTION_HEADS), W / 2, 190, HEAD_W, 150, "black", 96, fill=YELLOW, max_lines=2)
    top, bottom = 340, 1140
    cv.card((MARGIN - 4, top, W - MARGIN + 4, bottom), radius=44, fill=CREAM, outline=pal.ink, outline_w=8,
            shadow=(14, 18, 4, 150))
    cv.face(W - 118, top - 6, 52, "think")
    dark = pal.ink
    if data["display"]:                                                                 # secuencia
        cv.text(data["question"], W / 2, 420, 860, 70, "bold", 58, fill=dark, stroke_ratio=0, extrude=False)
        cv.text(data["display"], W / 2, 540, 880, 150, "black", 118, fill=pal.c2, stroke_ratio=0, extrude=False)
    else:
        cv.text(data["question"], W / 2, 490, 880, 240, "black", 72, fill=dark, stroke_ratio=0, extrude=False,
                spacing=1.18, max_lines=4)
    y0, row_h, gap = 640, 104, 14
    for i, opt in enumerate(data["options"]):
        y = y0 + i * (row_h + gap)
        cv.card((96, y, W - 96, y + row_h), radius=30, fill=WHITE, outline=dark, outline_w=5, shadow=(5, 8, 5, 70))
        lay = cv.layer()
        d = ImageDraw.Draw(lay)
        cx, cy, r = 168, y + row_h / 2, 40
        d.ellipse((S(cx - r), S(cy - r), S(cx + r), S(cy + r)), fill=OPTION_COLORS[i], outline=dark, width=S(4))
        cv.put(lay)
        cv.text(P.LETTERS[i], cx, cy + 1, 70, 60, "black", 50, fill=WHITE, stroke_fill=dark, stroke_ratio=0.05, extrude=False)
        cv.text(opt, 590, cy, 720, row_h - 14, "black", 60, fill=dark, stroke_ratio=0, extrude=False, max_lines=2)


DRAWERS = {"pemdas": draw_pemdas, "cubos": draw_cubes, "fracciones": draw_fraction, "opciones": draw_options}


def render(puz: P.Puzzle, kit: FontKit, seed: int):
    """Imagen RGB 1080x1350 del reto. Determinista por (reto, semilla). -> (imagen, nombre de la paleta)."""
    rng = random.Random(seed ^ 0xF00D)
    pal = rng.choice(PALETTES)
    cv = Canvas(pal, kit, rng)
    cv.decorate()
    cv.frame()
    DRAWERS[puz.kind](cv, puz)
    return cv.finish(), pal.name
