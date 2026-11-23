"""Logica de los 4 retos de imagen (sin Pillow): se generan por semilla con respuesta comprobada y respuesta tramposa.

Cada generador devuelve un `Puzzle` con todo lo que necesitan el dibujo (``data``) y el texto de publicacion
(``answer``, ``trap``, ``explanation``). Con `avoid` (firmas ya usadas, ver historial) se vuelve a sortear.
"""
from __future__ import annotations

import difflib
import math
import random
from dataclasses import dataclass, field
from fractions import Fraction

import numpy as np

MODES = ("pemdas", "cubos", "fracciones", "opciones")
LETTERS = "ABCD"


@dataclass(frozen=True)
class Puzzle:
    kind: str                 # pemdas | cubos | fracciones | opciones
    key: str                  # firma para no repetir el mismo reto (historial)
    detail: str               # trozo del nombre de archivo
    data: dict                # lo que necesita el dibujo
    answer: str               # respuesta correcta (control interno)
    explanation: str          # por que
    trap: str | None = None   # respuesta equivocada tipica
    alt: str = ""             # texto alternativo (accesibilidad)
    extra: dict = field(default_factory=dict)


# =========================================================================== 1. ecuacion de la discordia (PEMDAS)
OPS = "+−×÷"


class _NotInteger(Exception):
    pass


def _apply(op: str, a: Fraction, b: Fraction) -> Fraction:
    if op == "+":
        return a + b
    if op == "−":
        return a - b
    if op == "×":
        return a * b
    if b == 0:
        raise ZeroDivisionError
    q = a / b
    if q.denominator != 1:
        raise _NotInteger
    return q


def evaluate(tokens, ltr: bool = False) -> Fraction:
    """Valor de la expresion. `ltr=True` = de izquierda a derecha ignorando la prioridad (el error mas comun);
    los parentesis se respetan siempre. Las divisiones deben ser exactas."""
    pos = 0

    def atom() -> Fraction:
        nonlocal pos
        tok = tokens[pos]
        pos += 1
        if tok == "(":
            v = expr()
            pos += 1                                            # ')'
            return v
        return Fraction(tok)

    def term() -> Fraction:
        nonlocal pos
        v = atom()
        while pos < len(tokens) and tokens[pos] in "×÷":
            op = tokens[pos]
            pos += 1
            v = _apply(op, v, atom())
        return v

    def expr() -> Fraction:
        nonlocal pos
        if ltr:
            v = atom()
            while pos < len(tokens) and tokens[pos] in OPS:
                op = tokens[pos]
                pos += 1
                v = _apply(op, v, atom())
            return v
        v = term()
        while pos < len(tokens) and tokens[pos] in "+−":
            op = tokens[pos]
            pos += 1
            v = _apply(op, v, term())
        return v

    return expr()


def fmt_tokens(tokens) -> str:
    return " ".join(str(t) for t in tokens).replace("( ", "(").replace(" )", ")")


def steps(tokens) -> str:
    """Resolucion paso a paso con la prioridad correcta: «7 ÷ 7 − 7 × 7 = 1 − 7 × 7 = 1 − 49 = −48»."""
    toks = list(tokens)
    out = [fmt_tokens(toks)]
    while len(toks) > 1:
        lo, hi = 0, len(toks)
        if "(" in toks:
            lo = max(i for i, t in enumerate(toks) if t == "(") + 1
            hi = toks.index(")", lo)
        seg = toks[lo:hi]
        if len(seg) == 1:                                       # «(5)» -> «5»
            toks[lo - 1:hi + 1] = seg
        else:
            idx = next((i for i, t in enumerate(seg) if isinstance(t, str) and t in "×÷"), None)
            if idx is None:
                idx = next(i for i, t in enumerate(seg) if isinstance(t, str) and t in "+−")
            v = _apply(seg[idx], Fraction(seg[idx - 1]), Fraction(seg[idx + 1]))
            toks[lo + idx - 1:lo + idx + 2] = [int(v)]
        out.append(fmt_tokens(toks).replace("-", "−"))
    return " = ".join(out)


def gen_pemdas(rng: random.Random, avoid=frozenset()) -> Puzzle:
    for _ in range(6000):
        n_ops = rng.choice((2, 3, 3, 3, 4))
        if rng.random() < 0.35:                                 # el estilo viral «7 ÷ 7 − 7 × 7»
            base = rng.randint(2, 9)
            nums = [base] * (n_ops + 1)
        else:
            nums = [rng.randint(1, 12) for _ in range(n_ops + 1)]
        ops = [rng.choice(OPS) for _ in range(n_ops)]
        if not (set(ops) & set("×÷") and set(ops) & set("+−")):  # la prioridad tiene que importar
            continue
        tokens = [nums[0]]
        for op, n in zip(ops, nums[1:]):
            tokens += [op, n]
        if n_ops >= 3 and rng.random() < 0.3:                   # parentesis alrededor de un par consecutivo
            i = 2 * rng.randrange(n_ops)
            tokens[i:i + 3] = ["(", *tokens[i:i + 3], ")"]
        try:
            right, naive = evaluate(tokens), evaluate(tokens, ltr=True)
        except (ZeroDivisionError, _NotInteger):
            continue
        if right == naive or abs(right) > 999 or abs(naive) > 9999 or right == 0:
            continue
        eq = fmt_tokens(tokens)
        if eq in avoid:
            continue
        r, nv = int(right), int(naive)
        sign = ("n" if r < 0 else "") + str(abs(r))
        return Puzzle("pemdas", eq, sign, dict(eq=eq, right=r, naive=nv, tokens=tokens),
                      answer=str(r).replace("-", "−"),
                      explanation=f"Primero los paréntesis, luego × y ÷ (de izquierda a derecha) y al final + y −: "
                                  f"{steps(tokens)}.",
                      trap=str(nv).replace("-", "−"),
                      alt=f"Ecuación matemática: {eq} igual a interrogación.")
    raise RuntimeError("no se pudo generar la ecuación")


# =========================================================================== 2. cubos isometricos
C30 = math.sqrt(3) / 2


def proj(x: float, y: float, z: float) -> tuple:
    """Proyeccion isometrica (unidad = arista; y de pantalla hacia abajo, z hacia arriba)."""
    return ((x - y) * C30, (x + y) * 0.5 - z)


def cube_faces(x: int, y: int, z: int) -> dict:
    """Poligonos de pantalla de las 3 caras visibles de un cubo: top, right (cara +x) y left (cara +y)."""
    p = proj
    return {
        "top": [p(x, y, z + 1), p(x + 1, y, z + 1), p(x + 1, y + 1, z + 1), p(x, y + 1, z + 1)],
        "right": [p(x + 1, y, z), p(x + 1, y + 1, z), p(x + 1, y + 1, z + 1), p(x + 1, y, z + 1)],
        "left": [p(x, y + 1, z), p(x + 1, y + 1, z), p(x + 1, y + 1, z + 1), p(x, y + 1, z + 1)],
    }


def painter_order(heights) -> list:
    """Cubos (x, y, z) de atras hacia adelante (el espectador mira desde +x, +y, +z)."""
    cubes = [(x, y, z) for y, row in enumerate(heights) for x, h in enumerate(row) for z in range(h)]
    return sorted(cubes, key=lambda c: (c[0] + c[1] + c[2], c[2]))


def _fill(buf, pts, val, ox, oy, res):
    xs = [(px - ox) * res for px, _ in pts]
    ys = [(py - oy) * res for _, py in pts]
    x0, x1 = max(0, int(math.floor(min(xs)))), min(buf.shape[1], int(math.ceil(max(xs))) + 1)
    y0, y1 = max(0, int(math.floor(min(ys)))), min(buf.shape[0], int(math.ceil(max(ys))) + 1)
    if x0 >= x1 or y0 >= y1:
        return
    gx, gy = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
    signs = []
    for i in range(4):
        ax, ay, bx, by = xs[i], ys[i], xs[(i + 1) % 4], ys[(i + 1) % 4]
        signs.append((bx - ax) * (gy - ay) - (by - ay) * (gx - ax))
    inside = np.all([s >= 0 for s in signs], axis=0) | np.all([s <= 0 for s in signs], axis=0)
    buf[y0:y1, x0:x1][inside] = val


def analyse(heights, res: int = 16) -> dict:
    """Rasteriza la vista isometrica con el algoritmo del pintor y mide cuanto se ve de cada cubo."""
    order = painter_order(heights)
    pts = [q for c in order for f in cube_faces(*c).values() for q in f]
    ox, oy = min(p[0] for p in pts), min(p[1] for p in pts)
    w = int(math.ceil((max(p[0] for p in pts) - ox) * res)) + 2
    h = int(math.ceil((max(p[1] for p in pts) - oy) * res)) + 2
    buf = np.full((h, w), -1, "i4")
    for i, c in enumerate(order):
        for f in cube_faces(*c).values():
            _fill(buf, f, i, ox, oy, res)
    seen = np.bincount(buf[buf >= 0], minlength=len(order))
    area = {c: int(seen[i]) for i, c in enumerate(order)}
    full = C30 * res * res                                      # area de una cara en pixeles
    return dict(order=order, area=area, face=full)


def gen_cubes(rng: random.Random, avoid=frozenset()) -> Puzzle:
    for _ in range(4000):
        cols, rows = rng.choice(((3, 3), (3, 3), (4, 3), (4, 4)))
        weights = (0.14, 0.27, 0.25, 0.2, 0.14)
        heights = tuple(tuple(rng.choices(range(5), weights)[0] for _ in range(cols)) for _ in range(rows))
        total = sum(map(sum, heights))
        if not (8 <= total <= (18 if cols * rows == 9 else 26)) or max(map(max, heights)) < 3:
            continue
        key = repr(heights)
        if key in avoid:
            continue
        info = analyse(heights)
        area, face = info["area"], info["face"]
        visible = [c for c, a in area.items() if a >= 0.12 * face]
        hidden = len(area) - len(visible)
        tops = [(x, y, h - 1) for y, row in enumerate(heights) for x, h in enumerate(row) if h]
        if hidden < 1 or any(area[t] < 0.55 * face for t in tops):      # algun oculto, y cada columna se ve por arriba
            continue
        return Puzzle("cubos", key, f"{total}", dict(heights=heights, cols=cols, rows=rows, order=info["order"]),
                      answer=str(total),
                      explanation=f"Hay {total} cubos: los {len(visible)} que se ven más {hidden} escondidos detrás o "
                                  f"debajo de otros (se suman por columnas: "
                                  f"{' + '.join(str(sum(r[x] for r in heights)) for x in range(cols))}).",
                      trap=str(len(visible)),
                      alt=f"Apilamiento isométrico de cubos de {cols}×{rows} con algunos cubos ocultos.",
                      extra=dict(hidden=hidden, visible=len(visible)))
    raise RuntimeError("no se pudo generar el apilamiento")


# =========================================================================== 3. fracciones enganosas
def gen_fraction(rng: random.Random, avoid=frozenset()) -> Puzzle:
    """Poligono regular partido en n triangulos grandes; cada uno es blanco, gris o se parte en 4 triangulos iguales."""
    for _ in range(4000):
        n = rng.choice((6, 6, 6, 4, 8))
        states = []
        for _i in range(n):
            r = rng.random()
            if r < 0.22:
                states.append("W")
            elif r < 0.52:
                states.append("G")
            else:
                bits = tuple(rng.random() < 0.5 for _ in range(4))
                while not 0 < sum(bits) < 4:                    # el triangulo partido mezcla gris y blanco
                    bits = tuple(rng.random() < 0.5 for _ in range(4))
                states.append(bits)
        subs = [s for s in states if isinstance(s, tuple)]
        wholes = [s for s in states if not isinstance(s, tuple)]
        if not subs or not wholes or "G" not in states and not any(any(b) for b in subs):
            continue
        gray_small = sum(4 if s == "G" else (sum(s) if isinstance(s, tuple) else 0) for s in states)
        total = 4 * n
        pieces = len(wholes) + 4 * len(subs)
        gray_pieces = states.count("G") + sum(sum(s) for s in subs)
        right, naive = Fraction(gray_small, total), Fraction(gray_pieces, pieces)
        if not 0 < gray_small < total or right == naive or right.denominator == 1:
            continue
        key = f"{n}:{states}"
        if key in avoid:
            continue
        rot = rng.choice((0, 1))                                # punta arriba o lado plano arriba
        names = {4: "cuadrado", 6: "hexágono", 8: "octógono"}
        return Puzzle("fracciones", key, f"{right.numerator}-{right.denominator}",
                      dict(n=n, states=states, rot=rot, shape=names[n]),
                      answer=f"{right.numerator}/{right.denominator}",
                      explanation=f"Cada triángulo grande equivale a 4 pequeños, así que el {names[n]} tiene {total} "
                                  f"triángulos iguales. La región gris ocupa {gray_small} de {total} = "
                                  f"{right.numerator}/{right.denominator}.",
                      trap=f"{naive.numerator}/{naive.denominator}",
                      alt=f"Un {names[n]} dividido en triángulos, con algunas regiones grises y otras blancas.",
                      extra=dict(total=total, gray=gray_small, pieces=pieces, gray_pieces=gray_pieces))
    raise RuntimeError("no se pudo generar la fracción")


# =========================================================================== 4. opcion multiple tramposa
_ROMAN = ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"),
          (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))


def to_roman(n: int) -> str:
    out = ""
    for v, s in _ROMAN:
        while n >= v:
            out += s
            n -= v
    return out


def from_roman(s: str) -> int | None:
    """Valor de un numero romano; None si no esta escrito en la forma canonica (p. ej. «IIX» o «XXXX»)."""
    vals = dict(I=1, V=5, X=10, L=50, C=100, D=500, M=1000)
    if not s or any(ch not in vals for ch in s):
        return None
    total = 0
    for i, ch in enumerate(s):
        total += -vals[ch] if i + 1 < len(s) and vals[ch] < vals[s[i + 1]] else vals[ch]
    return total if to_roman(total) == s else None


def roman_distractors(rng: random.Random, n: int) -> list:
    """Tres numeros romanos validos que se parecen mucho al correcto (cambian una cifra, un signo o una resta)."""
    digits = [int(c) for c in f"{n:03d}"]
    cands = {n + d for d in (-100, -50, -40, -10, -5, -2, -1, 1, 2, 5, 10, 40, 50, 100)}
    for i, j in ((0, 1), (1, 2), (0, 2)):                        # cifras intercambiadas
        d = digits[:]
        d[i], d[j] = d[j], d[i]
        cands.add(int("".join(map(str, d))))
    right = to_roman(n)
    ranked = sorted(((difflib.SequenceMatcher(None, to_roman(c), right).ratio(), c) for c in cands if 0 < c < 4000 and c != n),
                    reverse=True)
    pool = [c for _, c in ranked[:7]]
    return rng.sample(pool, 3)


_CLASSIC = (
    ("¿Cuántos meses del año tienen 28 días?", "Los 12", ("Solo 1", "2", "6"), "Todos los meses tienen al menos 28 días."),
    ("Tienes 3 manzanas y te llevas 2. ¿Cuántas tienes?", "2", ("1", "3", "5"), "Tienes las 2 que te llevaste."),
    ("¿Cuánto es la mitad de 2 + 2?", "3", ("2", "4", "1"), "La mitad de 2 es 1, y 1 + 2 = 3."),
    ("Un bate y una pelota cuestan 1,10 €. El bate cuesta 1 € más que la pelota. ¿Cuánto cuesta la pelota?",
     "5 céntimos", ("10 céntimos", "15 céntimos", "1 €"), "Pelota 0,05 € + bate 1,05 € = 1,10 €."),
    ("¿Cuántas veces puedes restar 5 de 25?", "1 vez", ("5 veces", "20 veces", "Ninguna"),
     "Solo una: después ya no tienes 25."),
    ("¿Cuántos animales de cada especie metió Moisés en el arca?", "Ninguno", ("2", "1", "7"),
     "Fue Noé, no Moisés."),
    ("Un reloj da 6 campanadas en 5 segundos. ¿Cuánto tarda en dar 12?", "11 segundos", ("10 segundos", "12 segundos",
                                                                                   "13 segundos"),
     "Hay 5 pausas en 5 s (1 s cada una); 12 campanadas tienen 11 pausas."),
    ("¿Cuánto es 1000 + 40 + 1000 + 30 + 1000 + 20 + 1000 + 10?", "4100", ("5000", "4000", "4010"),
     "Los miles suman 4000 y los demás 100."),
    ("5 máquinas hacen 5 piezas en 5 minutos. ¿Cuánto tardan 100 máquinas en hacer 100 piezas?", "5 minutos",
     ("100 minutos", "20 minutos", "1 minuto"), "Cada máquina hace una pieza cada 5 minutos."),
    ("Un nenúfar duplica su tamaño cada día y cubre el lago en 48 días. ¿Cuándo cubre la mitad?", "El día 47",
     ("El día 24", "El día 12", "El día 46"), "Un día antes de cubrirlo todo, cubre la mitad."),
    ("Si 3 gallinas ponen 3 huevos en 3 días, ¿cuántos huevos ponen 6 gallinas en 6 días?", "12", ("6", "9", "18"),
     "Cada gallina pone 1 huevo cada 3 días: 6 gallinas × 2 huevos."),
    ("Un granjero tiene 17 ovejas y todas menos 9 se escapan. ¿Cuántas le quedan?", "9", ("8", "17", "0"),
     "«Todas menos 9» son las que no se escapan."),
)


def _options(rng: random.Random, correct: str, wrong) -> tuple:
    """(lista de 4 opciones barajadas, indice de la correcta)."""
    opts = [correct, *wrong]
    rng.shuffle(opts)
    return opts, opts.index(correct)


def gen_options(rng: random.Random, avoid=frozenset()) -> Puzzle:
    from ..acts import _gen_seq                                  # familias de secuencias ya probadas en los videos
    for _ in range(4000):
        sub = rng.choices(("roman", "sequence", "classic"), (4, 3, 3))[0]
        if sub == "roman":
            n = rng.choice([v for v in range(100, 1000) if v % 10 not in (0,) and (v // 10) % 10 != 0])
            wrong = [to_roman(c) for c in roman_distractors(rng, n)]
            opts, ok = _options(rng, to_roman(n), wrong)
            q = rng.choice((f"¿Dónde está el número {n}?", f"¿Cuál de estas es el {n} en números romanos?",
                            f"¿Cuál de estas opciones escribe bien el {n}?"))
            data = dict(sub=sub, question=q, display="", options=opts, correct=ok)
            key, detail = f"roman:{n}", "romanos"
            h, t, u = n // 100 * 100, n // 10 % 10 * 10, n % 10
            expl = (f"{n} = {h} + {t} + {u} → {to_roman(h)} + {to_roman(t)} + {to_roman(u)} = {to_roman(n)}. Las otras "
                    f"opciones valen {', '.join(str(from_roman(o)) for i, o in enumerate(opts) if i != ok)}.")
            trap = None
        elif sub == "sequence":
            shown, nxt, rule = _gen_seq(rng, rng.choices((0, 1, 2), (3, 4, 3))[0])
            linear = shown[-1] + (shown[-1] - shown[-2])
            pool = [linear, nxt + 1, nxt - 1, nxt + 2, nxt - 2, nxt + 10, shown[-1] * 2, shown[-1] + shown[0]]
            wrong = []
            for v in pool:
                if v > 0 and v != nxt and v not in wrong:
                    wrong.append(v)
            if len(wrong) < 3:
                continue
            first_is_linear = wrong[0] == linear
            wrong = wrong[:1] + rng.sample(wrong[1:], 2) if first_is_linear else rng.sample(wrong, 3)
            opts, ok = _options(rng, str(nxt), [str(w) for w in wrong])
            display = ", ".join(map(str, shown)) + ", ?"
            data = dict(sub=sub, question="¿Qué número sigue?", display=display, options=opts, correct=ok)
            key, detail = f"seq:{display}", "secuencia"
            expl = f"{rule.rstrip('.')}: sigue el {nxt}."
            trap = str(linear) if first_is_linear else None
        else:
            q, right, wrong, why = rng.choice(_CLASSIC)
            opts, ok = _options(rng, right, wrong)
            data = dict(sub=sub, question=q, display="", options=opts, correct=ok)
            key, detail = f"classic:{q}", "trampa"
            expl, trap = why, wrong[0]
        if key in avoid:
            continue
        letter = LETTERS[data["correct"]]
        return Puzzle("opciones", key, detail, data, answer=f"{letter}) {data['options'][data['correct']]}",
                      explanation=expl, trap=trap,
                      alt=f"Pregunta de opción múltiple: {data['question']} {data['display']}".strip())
    raise RuntimeError("no se pudo generar la pregunta")


GENERATORS = {"pemdas": gen_pemdas, "cubos": gen_cubes, "fracciones": gen_fraction, "opciones": gen_options}


def generate(kind: str, seed: int, avoid=frozenset()) -> Puzzle:
    """Reto determinista por (tipo, semilla)."""
    return GENERATORS[kind](random.Random(seed), frozenset(avoid))
