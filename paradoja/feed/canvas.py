"""Lienzo para las imagenes del feed (1080x1350): fondo vibrante, patrones, texto con contorno y relieve, tarjetas.

Todo se dibuja al doble de resolucion (SS = 2) y se reduce al final con LANCZOS para que bordes y letras salgan suaves.
Las coordenadas publicas son «logicas» (1080x1350); `S()` las pasa a pixeles reales.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from ..config import BRAND

W, H, SS = 1080, 1350, 2
SIZE = (W * SS, H * SS)
MARGIN = 54
BAND_Y = (1165, 1315)           # franja inferior (pregunta sobre el reto)
ART_TOP, ART_BOTTOM = 400, 1140  # zona del dibujo central


def S(v: float) -> int:
    return int(round(v * SS))


@dataclass(frozen=True)
class Palette:
    name: str
    c1: tuple            # color superior del degradado
    c2: tuple            # color inferior
    accent: tuple = (255, 214, 10)
    ink: tuple = (20, 16, 44)


# Fondos vibrantes pero lo bastante oscuros para que el blanco y el amarillo destaquen
PALETTES = (
    Palette("fucsia", (222, 30, 124), (96, 26, 164)),
    Palette("fuego", (246, 92, 20), (196, 20, 86)),
    Palette("azul electrico", (22, 96, 244), (92, 40, 204)),
    Palette("esmeralda", (0, 150, 112), (12, 78, 146)),
    Palette("violeta", (140, 40, 232), (228, 50, 142)),
    Palette("cian", (0, 142, 204), (0, 70, 164)),
    Palette("rojo", (222, 30, 52), (142, 20, 122)),
)


def luminance(rgb) -> float:
    def f(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb[:3]
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def lighten(rgb, k: float) -> tuple:
    return tuple(int(c + (255 - c) * k) for c in rgb[:3])


def darken(rgb, k: float) -> tuple:
    return tuple(int(c * (1 - k)) for c in rgb[:3])


def gradient(c1, c2, angle_deg: float = 65) -> Image.Image:
    w, h = SIZE
    yy, xx = np.mgrid[0:h, 0:w].astype("f4")
    a = math.radians(angle_deg)
    t = xx * math.cos(a) + yy * math.sin(a)
    t = (t - t.min()) / (t.max() - t.min())
    arr = np.asarray(c1, "f4")[None, None] * (1 - t[..., None]) + np.asarray(c2, "f4")[None, None] * t[..., None]
    return Image.fromarray(arr.astype("u1"), "RGB")


class Canvas:
    def __init__(self, pal: Palette, kit, rng: random.Random):
        self.pal, self.kit, self.rng = pal, kit, rng
        self.img = gradient(pal.c1, pal.c2, rng.choice((55, 65, 75, 115))).convert("RGBA")

    # ------------------------------------------------------------------ capas
    def layer(self) -> Image.Image:
        return Image.new("RGBA", SIZE, (0, 0, 0, 0))

    def put(self, layer: Image.Image) -> None:
        self.img = Image.alpha_composite(self.img, layer)

    def finish(self) -> Image.Image:
        return self.img.convert("RGB").resize((W, H), Image.LANCZOS)

    # ------------------------------------------------------------------ decoracion de fondo
    def decorate(self) -> None:
        """Patron suave detras de todo: rayos, puntos o simbolos matematicos (elegido por la semilla)."""
        lay, d = self.layer(), None
        d = ImageDraw.Draw(lay)
        kind = self.rng.choice(("rays", "dots", "glyphs", "rays+glyphs"))
        if "rays" in kind:
            cx, cy, n = S(W / 2), S(H * 0.46), 20
            R = S(W * 1.6)
            for k in range(0, n, 2):
                a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
                d.polygon([(cx, cy), (cx + R * math.cos(a0), cy + R * math.sin(a0)),
                           (cx + R * math.cos(a1), cy + R * math.sin(a1))], fill=(255, 255, 255, 20))
        if kind == "dots":
            step = 60
            for j, y in enumerate(range(20, H, step)):
                for x in range(20 + (step // 2 if j % 2 else 0), W, step):
                    d.ellipse((S(x - 5), S(y - 5), S(x + 5), S(y + 5)), fill=(255, 255, 255, 34))
        if "glyphs" in kind:
            for _ in range(16):
                ch = self.rng.choice("?×÷+−=?%")
                size = self.rng.randint(110, 230)
                x, y = self.rng.randint(-20, W - 80), self.rng.randint(120, H - 260)
                d.text((S(x), S(y)), ch, font=self.kit.get("black", S(size)), fill=(255, 255, 255, 26))
        self.put(lay)

    # ------------------------------------------------------------------ texto
    def _bbox(self, text, font, stroke=0):
        return ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=font, stroke_width=stroke)

    def _wrap(self, text, font, max_w, stroke):
        lines = []
        for para in text.split("\n"):
            cur = ""
            for word in para.split():
                trial = f"{cur} {word}".strip()
                b = self._bbox(trial, font, stroke)
                if b[2] - b[0] <= max_w or not cur:
                    cur = trial
                else:
                    lines.append(cur)
                    cur = word
            lines.append(cur)
        return lines

    def fit(self, text, role, box_w, box_h, max_size, min_size=22, spacing=1.12, stroke_ratio=0.07, max_lines=4):
        """Letra mas grande (<= max_size) con la que `text` cabe en la caja. -> (lineas, fuente, tamaño, contorno)."""
        for size in range(int(max_size), int(min_size) - 1, -2):
            font, stroke = self.kit.get(role, S(size)), round(S(size) * stroke_ratio)
            lines = self._wrap(text, font, S(box_w), stroke)
            widest = max(self._bbox(x, font, stroke)[2] - self._bbox(x, font, stroke)[0] for x in lines)
            if len(lines) <= max_lines and len(lines) * S(size) * spacing <= S(box_h) and widest <= S(box_w):
                break
        return lines, font, size, stroke

    def text(self, text, cx, cy, box_w, box_h, role="black", max_size=100, min_size=22, fill=(255, 255, 255),
             stroke_fill=None, stroke_ratio=0.07, extrude=True, spacing=1.12, max_lines=4) -> tuple:
        """Bloque de texto centrado en (cx, cy) con contorno oscuro y relieve. Devuelve su caja logica (x0, y0, x1, y1)."""
        stroke_fill = stroke_fill or self.pal.ink
        lines, font, size, stroke = self.fit(text, role, box_w, box_h, max_size, min_size, spacing, stroke_ratio, max_lines)
        lh = S(size) * spacing
        top = S(cy) - lh * len(lines) / 2
        lay = self.layer()
        d = ImageDraw.Draw(lay)
        depth = max(2, int(S(size) * 0.055)) if extrude else 0
        widest = 0
        for i, line in enumerate(lines):
            x, y = S(cx), top + lh * (i + 0.5)
            b = self._bbox(line, font, stroke)
            widest = max(widest, b[2] - b[0])
            for k in range(depth, 0, -1):                       # relieve: copias desplazadas hacia abajo-derecha
                d.text((x + k, y + k), line, font=font, fill=stroke_fill, anchor="mm", stroke_width=stroke,
                       stroke_fill=stroke_fill)
            d.text((x, y), line, font=font, fill=fill, anchor="mm", stroke_width=stroke, stroke_fill=stroke_fill)
        self.put(lay)
        return ((S(cx) - widest / 2) / SS, top / SS, (S(cx) + widest / 2) / SS, (top + lh * len(lines)) / SS)

    # ------------------------------------------------------------------ formas
    def card(self, box, radius=40, fill=(255, 255, 255, 255), outline=None, outline_w=0, shadow=(10, 16, 26, 110)) -> None:
        """Rectangulo redondeado con sombra suave. `box` y `radius` en pixeles logicos."""
        x0, y0, x1, y1 = (S(v) for v in box)
        if shadow:
            dx, dy, blur, alpha = shadow
            pad = S(blur * 3 + max(dx, dy))
            rx0, ry0 = max(0, x0 - pad), max(0, y0 - pad)
            rx1, ry1 = min(SIZE[0], x1 + pad), min(SIZE[1], y1 + pad)
            sh = Image.new("RGBA", (rx1 - rx0, ry1 - ry0), (0, 0, 0, 0))
            ImageDraw.Draw(sh).rounded_rectangle((x0 - rx0 + S(dx), y0 - ry0 + S(dy), x1 - rx0 + S(dx), y1 - ry0 + S(dy)),
                                                 radius=S(radius), fill=(0, 0, 0, alpha))
            self.img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(S(blur))), dest=(rx0, ry0))
        lay = self.layer()
        ImageDraw.Draw(lay).rounded_rectangle((x0, y0, x1, y1), radius=S(radius), fill=fill,
                                              outline=outline, width=S(outline_w) if outline else 0)
        self.put(lay)

    def face(self, cx, cy, r, kind="shock") -> None:
        """Carita estilo emoji dibujada con formas (no depende de ninguna fuente de emojis)."""
        lay = self.layer()
        d = ImageDraw.Draw(lay)
        X, Y, R = S(cx), S(cy), S(r)
        line = max(2, int(R * 0.07))
        brown, dark = (122, 70, 0, 255), (40, 20, 10, 255)
        d.ellipse((X - R + S(4), Y - R + S(9), X + R + S(4), Y + R + S(9)), fill=(0, 0, 0, 90))
        d.ellipse((X - R, Y - R, X + R, Y + R), fill=(255, 205, 40, 255), outline=brown, width=line)
        d.ellipse((X - R * 0.52, Y - R * 0.80, X - R * 0.02, Y - R * 0.50), fill=(255, 236, 120, 255))
        if kind == "shock":
            for sx in (-1, 1):
                ex, ey = X + sx * R * 0.38, Y - R * 0.10
                d.ellipse((ex - R * 0.22, ey - R * 0.27, ex + R * 0.22, ey + R * 0.27), fill=(255, 255, 255, 255),
                          outline=brown, width=line)
                d.ellipse((ex - R * 0.08, ey - R * 0.08, ex + R * 0.08, ey + R * 0.08), fill=dark)
                d.arc((ex - R * 0.28, ey - R * 0.62, ex + R * 0.28, ey - R * 0.18), 200, 340, fill=brown, width=line)
            d.ellipse((X - R * 0.17, Y + R * 0.26, X + R * 0.17, Y + R * 0.70), fill=dark)
            d.ellipse((X - R * 0.10, Y + R * 0.48, X + R * 0.10, Y + R * 0.68), fill=(230, 90, 90, 255))
        else:                                              # «think»: ceja levantada y boca torcida
            for sx in (-1, 1):
                ex, ey = X + sx * R * 0.36, Y - R * 0.06
                d.ellipse((ex - R * 0.16, ey - R * 0.2, ex + R * 0.16, ey + R * 0.2), fill=(255, 255, 255, 255),
                          outline=brown, width=line)
                d.ellipse((ex - R * 0.06 + sx * R * 0.04, ey - R * 0.16, ex + R * 0.06 + sx * R * 0.04, ey - R * 0.04),
                          fill=dark)
            d.line((X - R * 0.56, Y - R * 0.34, X - R * 0.18, Y - R * 0.38), fill=brown, width=line)
            d.line((X + R * 0.16, Y - R * 0.56, X + R * 0.56, Y - R * 0.40), fill=brown, width=line)
            d.line((X - R * 0.30, Y + R * 0.46, X + R * 0.30, Y + R * 0.36), fill=brown, width=line + 1)
        self.put(lay)

    def arrow_down(self, cx, cy, w=62, h=74, fill=(255, 214, 10)) -> None:
        """Flecha hacia abajo (sustituye al emoji 👇 en la imagen)."""
        lay = self.layer()
        d = ImageDraw.Draw(lay)
        X, Y, a, b = S(cx), S(cy), S(w) / 2, S(h) / 2
        pts = [(X - a * 0.38, Y - b), (X + a * 0.38, Y - b), (X + a * 0.38, Y), (X + a, Y), (X, Y + b), (X - a, Y),
               (X - a * 0.38, Y)]
        d.polygon([(px + S(3), py + S(4)) for px, py in pts], fill=(0, 0, 0, 110))
        d.polygon(pts, fill=fill, outline=self.pal.ink, width=max(2, S(3)))
        self.put(lay)

    # ------------------------------------------------------------------ marco comun
    def frame(self, cta="¿CUÁL ES TU RESPUESTA?", sub="PIÉNSALO ANTES DE VER LA SOLUCIÓN") -> None:
        """Marca arriba y franja inferior con una pregunta sobre el reto (sin pedir comentar, compartir ni seguir)."""
        font = self.kit.get("black", S(34))
        b = self._bbox(BRAND, font)
        pw = (b[2] - b[0]) / SS + 70
        self.card((W / 2 - pw / 2, 34, W / 2 + pw / 2, 100), radius=33, fill=(*self.pal.ink, 215), shadow=(4, 8, 8, 90))
        lay = self.layer()
        ImageDraw.Draw(lay).text((S(W / 2), S(67)), BRAND, font=font, fill=(255, 255, 255, 255), anchor="mm")
        self.put(lay)
        x0, y0, x1, y1 = 40, BAND_Y[0], W - 40, BAND_Y[1]
        self.card((x0, y0, x1, y1), radius=44, fill=(*self.pal.ink, 235), outline=self.pal.accent, outline_w=5)
        self.arrow_down(112, (y0 + y1) / 2, fill=self.pal.accent)
        self.arrow_down(W - 112, (y0 + y1) / 2, fill=self.pal.accent)
        self.text(cta, W / 2, y0 + 50, 700, 66, "black", 56, fill=self.pal.accent, stroke_fill=(0, 0, 0), stroke_ratio=0.04,
                  extrude=False)
        self.text(sub, W / 2, y0 + 112, 700, 40, "bold", 34, fill=(255, 255, 255), stroke_fill=(0, 0, 0),
                  stroke_ratio=0.04, extrude=False)
