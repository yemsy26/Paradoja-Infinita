"""Generacion de actos: cada tipo de reto crea sus parametros de shader, su narracion y su texto en pantalla."""
import json
import math
import textwrap
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import texts_es as T
from .config import CAPTION_Y, COUNT_TOP_Y, MEMORY_LAYOUTS, SAFE_Y, SWARM_MAX, VideoSpec
from .scene import (ILLUSIONS, SHAPES, TYPES, Act, Palette, _swarm_act, _swarm_positions, blocked_rows, swarm_clock)

RIDDLES_PATH = Path(__file__).resolve().parent.parent / "content" / "acertijos.json"
FULL_REVEAL_LAST = ("Ese era. ¿Cuántos acertaste?", "Ese era. ¿Los acertaste todos?")
# retos cuya pregunta se muestra fija arriba (los de texto ya la tienen en el centro)
CAPTION_TYPES = {"anomaly", "illusion", "ishihara", "magiceye", "contrast", "sync", "swarm", "count", "flicker", "memory",
                 "cups", "simon", "digits"}
MIN_DELTA_RANGE = 0.55          # dificultad: de 1.0 (facil) a 0.45 (dificil), nunca imposible


@dataclass(frozen=True)
class Ctx:
    pal: Palette
    shape: int
    cols: int
    rows: int
    cell: int
    hex_layout: bool
    hue_off: int
    hue_jit: float
    spec: VideoSpec
    avail: float          # segundos disponibles para los actos (duracion - cierre)


def load_riddles() -> list:
    return json.loads(RIDDLES_PATH.read_text("utf-8"))


def _bgr(rgb) -> str:
    r, g, b = (round(max(0.0, min(1.0, c)) * 255) for c in rgb)
    return f"{b:02X}{g:02X}{r:02X}"


# --------------------------------------------------------------------------- planificacion
def _plan(rng, mode: str, avail: float) -> list:
    """[(tipo, inicio, duracion, busqueda)] que rellena exactamente `avail` segundos."""
    if mode == "mix":
        pool = list(TYPES)
        while True:
            types = rng.sample(pool, rng.choice((5, 6, 7)))
            if 0.92 <= avail / sum(TYPES[t].base_len for t in types) <= 1.30:
                break
    else:
        types = [mode] * max(3, round(avail / TYPES[mode].base_len))
    f = avail / sum(TYPES[t].base_len for t in types)
    plan, t = [], 0.0
    for ty in types:
        length = TYPES[ty].base_len * f
        plan.append((ty, t, length, length - TYPES[ty].reveal))
        t += length
    return plan


# --------------------------------------------------------------------------- utilidades de narracion
def _voice(rng, i, ty, S, instr, mid_pool=None, reveal="", countdown=True):
    """Narracion estandar. Reglas de hueco (la voz de cada linea debe terminar antes de la siguiente):
    gancho solo si S >= 8.2; linea intermedia solo si S >= 8.2; cuenta atras 'Tres, dos, uno' desde S-3."""
    v = []
    if i == 0 and S >= 8.2:
        v += [(0.15, rng.choice(T.HOOK_SHORT)), (1.8, instr)]
        mid_t = max(3.9, 1.8 + 0.6 * len(instr.split()) + 0.3)       # ~0.6 s por palabra de la instruccion
    else:
        text = f"{T.SPOKEN_LABEL[ty]} {T.NUMS[i]}. {instr}"
        v.append((0.30, text))
        mid_t = max(3.9, 0.30 + 0.6 * len(text.split()) + 0.3)
    if mid_pool and S >= 8.2 and mid_t + 1.3 <= S - 3.0:
        v.append((mid_t, rng.choice(mid_pool)))
    if countdown and S >= 7.0:
        v.append((S - 3.0, "Tres, dos, uno."))
    v.append((S + 0.25, reveal))
    return tuple(v)


def _first(rng, i, ty, S, instr):
    """Inicio de narracion para tipos sin cuenta atras (gancho + instruccion, o etiqueta + instruccion)."""
    if i == 0 and S >= 8.2:
        return [(0.15, rng.choice(T.HOOK_SHORT)), (1.8, instr)]
    return [(0.30, f"{T.SPOKEN_LABEL[ty]} {T.NUMS[i]}. {instr}")]


def _reveal(rng, last: bool) -> str:
    return rng.choice(FULL_REVEAL_LAST if last else T.REVEAL)


def _big(text: str) -> int:
    """Tamaño de fuente (px) para que `text` quepa en ~980 px de ancho."""
    longest = max(len(line) for line in text.split("\\N"))
    return int(min(170, 980 / (0.56 * max(longest, 1))))


HOOK_END = 2.2          # el gancho ocupa el primer fotograma y los primeros 2.2 s del video


def _hook_item(rng, plan, accent: str) -> tuple:
    """Gancho en pantalla (0 - HOOK_END s) para que el primer fotograma ya tenga texto: (t0, t1, texto, tamaño, bgr, y)."""
    pool = T.HOOK_TEXT[TYPES[plan[0][0]].category]
    text = rng.choice(pool).format(N=len(plan))
    lines = textwrap.wrap(text, 22)
    size = int(min(72, 940 / (0.66 * max(len(x) for x in lines))))
    return (0.0, HOOK_END, "\\N".join(lines), size, accent, CAPTION_Y)


def _caption(text: str, S: float, length: float, rcap: str, accent: str, t0: float = 0.25) -> tuple:
    """Pregunta fija arriba durante la busqueda y respuesta corta durante la revelacion."""
    def fit(t):
        """Una sola linea (el HUD ocupa la esquina y la barra de tiempo queda justo debajo); solo se parte si es muy larga."""
        lines = textwrap.wrap(t, 38) if len(t) > 50 else [t]
        return "\\N".join(lines), int(max(34, min(50, 940 / (0.62 * max(len(x) for x in lines)))))
    q, qs = fit(text)
    items = [(t0, S, q, qs, "", CAPTION_Y)]
    if rcap:
        r, rs = fit(rcap)
        items.append((S, length - 0.1, r, rs, accent, CAPTION_Y))
    return tuple(items)


def _pick(rng, pool, seen: list):
    """Elige sin repetir dentro del video mientras queden opciones."""
    fresh = [x for x in pool if x not in seen] or list(pool)
    x = rng.choice(fresh)
    seen.append(x)
    return x


# --------------------------------------------------------------------------- constructores por tipo
def _anomaly(rng, ctx, a, st):
    gr = T.g(ctx.shape)
    allowed = [1, 2, 3] + ([] if ctx.pal.mono else [0]) + ([4] if ctx.shape != 0 else [])
    kind = _pick(rng, [k for k in allowed if k != st.get("last_kind")] or allowed, st.setdefault("kinds", []))
    st["last_kind"] = kind
    blocked = set(blocked_rows(ctx.rows, ctx.cell))
    cells = [(c, r) for c in range(ctx.cols) for r in range(ctx.rows) if r not in blocked and (c, r) != st.get("prev")]
    target = rng.choice(cells)
    st["prev"] = target
    instr = rng.choice(T.anomaly_instr(kind, gr))
    return dict(kind=kind, target=target, p=(rng.random(), rng.random()), question=instr, rcap="AHÍ ESTABA",
                answer=f"fila {target[1] + 1}, columna {target[0] + 1} ({T.ANOMALY_DESC[kind]})",
                voice=_voice(rng, a["i"], "anomaly", a["S"], instr, T.MID, _reveal(rng, a["last"])))


def _illusion(rng, ctx, a, st):
    iid = _pick(rng, range(len(ILLUSIONS)), st.setdefault("ill", []))
    instr_pool, mid_pool, rev_pool = T.ILL_TEXT[iid]
    instr, reveal = rng.choice(instr_pool), rng.choice(rev_pool)
    return dict(kind=iid, p=(rng.random(), rng.random()), question=instr, rcap=reveal.upper(),
                answer=f"{T.ILL_NAME[iid]}: {reveal}",
                voice=_voice(rng, a["i"], "illusion", a["S"], instr, mid_pool, reveal))


def _sync(rng, ctx, a, st):
    gr, S = T.g(ctx.shape), a["S"]
    rt_hit = rng.uniform(S - 4.5, S - 0.9)               # dentro de la cuenta atras visible
    hit = round((a["start"] + rt_hit) * ctx.spec.fps) / ctx.spec.fps
    digit = int(S - (hit - a["start"])) + 1
    instr = f"Pausa cuando {gr['el']} {gr['noun']} encaje."
    reveal = f"Encajó en el {T.NUMS[digit - 1]}. " + ("¿Cuántas acertaste?" if a["last"] else "¿Pausaste a tiempo?")
    return dict(p=(rng.random(), rng.random()), hit=hit, question=instr, rcap=f"ENCAJÓ EN EL {digit}",
                answer=f"encaja cuando el contador marca {digit} (segundo {hit:.2f} del video)",
                voice=_voice(rng, a["i"], "sync", S, instr, T.SYNC_MID, reveal))


def _ishihara(rng, ctx, a, st):
    used = st.setdefault("numbers", [])
    if rng.random() < 0.65:
        sym = _pick(rng, range(10, 100), used)
        shape = rng.randrange(len(SHAPES))
        instr, answer, rcap = "¿Qué número hay escondido?", str(sym), f"ERA EL {sym}"
        reveal = f"Era el {T.num_es(sym)}. ¿Lo viste?"
    else:
        sym, shape = -1, _pick(rng, range(len(SHAPES)), st.setdefault("shapes", []))
        gr = T.g(shape)
        instr, answer = "¿Qué figura hay escondida?", gr["noun"]
        rcap = f"ERA {gr['el']} {gr['noun']}".upper()
        reveal = f"Era {gr['el']} {gr['noun']}. ¿Lo viste?"
    return dict(sym=sym, shape=shape, p=(rng.random(), rng.random()), question=instr, answer=answer, rcap=rcap,
                delta=1.0 - 0.30 * a["prog"],               # el test de tono necesita un contraste minimo legible
                voice=_voice(rng, a["i"], "ishihara", a["S"], instr, T.ISHI_MID, reveal))


def _quadrant(x, y):
    return ("arriba" if y < 0 else "abajo") + "-" + ("izquierda" if x < 0 else "derecha")  # y<0 = parte alta


def _swarm(rng, ctx, a, st):
    i, S, prog = a["i"], a["S"], a["prog"]
    n_part = min(SWARM_MAX, 18 + int(20 * prog))
    vmax = 3.0 + 3.6 * prog
    arrays = _swarm_act(rng, n_part, vmax, S)
    pa = np.frombuffer(arrays["u_pa"], "f4").reshape(-1, 4)
    pb = np.frombuffer(arrays["u_pb"], "f4").reshape(-1, 4)
    x, y = _swarm_positions(pa, pb, n_part, swarm_clock(S, S, vmax))[0]
    quad = _quadrant(x, y)
    reveal = rng.choice(("Ahí estaba. ¿Lo seguiste?", "Ese era. ¿Acertaste?"))
    voice = [(0.30, f"{T.SPOKEN_LABEL['swarm']} {T.NUMS[i]}. Sigue el punto rojo.")] if i else \
        [(0.15, rng.choice(T.HOOK_SHORT)), (1.7, "Sigue el punto rojo.")]
    voice += [(3.3, "Ahora es igual a todos."), (5.2, "No lo pierdas."), (S - 1.25, "¿Dónde quedó?"), (S + 0.25, reveal)]
    return dict(n=n_part, q=(vmax, 0.0), arrays=arrays, p=(rng.random(), rng.random()),
                question="Sigue el punto rojo", rcap=f"ESTABA {quad.upper()}",
                answer=f"queda {quad} ({n_part} partículas)", voice=tuple(voice))


def _magiceye(rng, ctx, a, st):
    if rng.random() < 0.45:                     # numero de dos cifras en 3D (90 posibles; las figuras son 7)
        n = _pick(rng, range(10, 100), st.setdefault("nums", []))
        return dict(sym=n, shape=rng.randrange(len(SHAPES)), p=(rng.random(), rng.random()),
                    q=(rng.random(), rng.random()), question="Desenfoca la vista y espera", rcap=f"ERA EL {n}",
                    answer=str(n), voice=_voice(rng, a["i"], "magiceye", a["S"], "Desenfoca la vista y espera.",
                                                T.MAGIC_MID, f"Era el {T.num_es(n)}. ¿Lo viste en 3D?"))
    shape = _pick(rng, range(len(SHAPES)), st.setdefault("shapes", []))
    gr = T.g(shape)
    reveal = f"Era {gr['el']} {gr['noun']}. ¿La viste en 3D?"
    return dict(shape=shape, p=(rng.random(), rng.random()), q=(rng.random(), rng.random()),
                question="Desenfoca la vista y espera", rcap=f"ERA {gr['el']} {gr['noun']}".upper(), answer=gr["noun"],
                voice=_voice(rng, a["i"], "magiceye", a["S"], "Desenfoca la vista y espera.", T.MAGIC_MID, reveal))


def _contrast(rng, ctx, a, st):
    queue = st.setdefault("queue", [])
    if not queue:
        queue.extend(rng.sample(range(4), 4))
    kind = queue.pop(0)
    p = (rng.random(), rng.random())
    dark_left = p[0] < 0.5
    if kind == 0:
        instr, reveal, ans = "¿Cambia de color la figura del centro?", "Nunca cambió. Es el mismo color.", "nunca cambió"
    elif kind == 1:
        lighter = p[1] >= 0.5                       # p[1]>=0.5: la figura se aclara de verdad
        instr = "¿La figura del centro se aclara o se oscurece?"
        reveal = ("Se aclaró" if lighter else "Se oscureció") + ", aunque no lo parezca."
        ans = "se aclara" if lighter else "se oscurece"
    elif kind == 2:
        instr, reveal, ans = "¿Cuál es más oscuro, el izquierdo o el derecho?", "Son idénticos. El mismo color.", "idénticos"
    else:
        side = "derecha" if dark_left else "izquierda"
        instr, reveal, ans = "¿Cuál bloque es más claro?", f"El de la {side}. Parecía al revés.", f"el de la {side}"
    return dict(kind=kind, p=p, question=instr, answer=ans, rcap=ans.upper(),
                voice=_voice(rng, a["i"], "contrast", a["S"], instr, T.CONTRAST_MID, reveal))


def _count(rng, ctx, a, st):
    """Conteo justo: pocas figuras, se mueven despacio, se detienen 2 s antes de revelar y las que hay que contar
    quedan fuera de la franja de subtitulos y sin tocarse."""
    prog, S = a["prog"], a["S"]
    mono = ctx.pal.mono
    shapes = rng.sample(range(len(SHAPES)), 3)
    colors = rng.sample(range(len(T.NAMED_COLORS)), 3)
    mode = "shape" if mono else rng.choice(("shape", "color") if prog < 0.5 else ("shape", "color", "both", "both"))
    sT, cT = rng.choice(shapes), rng.choice(colors)
    total = 10 + int(8 * prog)
    m = rng.randint(3, min(6, total - 5))

    def ok(sh, co):
        return (mode == "color" or sh == sT) and (mode == "shape" or co == cT)

    items = [(sT if mode != "color" else rng.choice(shapes), cT if mode != "shape" else rng.choice(colors))
             for _ in range(m)]
    while len(items) < total:
        sh, co = rng.choice(shapes), rng.choice(colors)
        if not ok(sh, co):
            items.append((sh, co))
    rng.shuffle(items)
    match = np.array([ok(*it) for it in items])
    assert match.sum() == m
    cspd = 0.35 + 0.15 * (1.0 - (1.0 - MIN_DELTA_RANGE * prog))     # igual que el shader
    s_end = (S - 2.0) * cspd
    pa = np.zeros((SWARM_MAX, 4), "f4")
    pb = np.zeros((SWARM_MAX, 4), "f4")
    for _attempt in range(40):
        placed = {}                                # posiciones finales (figuras detenidas) ya aceptadas
        for k in sorted(range(total), key=lambda j: not match[j]):      # primero las que se cuentan: son las exigentes
            for _ in range(500):
                pa[k] = (rng.uniform(.18, .44), rng.uniform(.18, .50), rng.uniform(.5, 1.4), rng.uniform(.5, 1.4))
                pb[k, 0], pb[k, 1] = rng.uniform(0, math.tau), rng.uniform(0, math.tau)
                pos = _swarm_positions(pa[k:k + 1], pb[k:k + 1], 1, s_end)[0]
                y = pos[1]
                # fuera de la franja de subtitulos; las contadas, ademas sobre la pregunta fija / zona de la app y con
                # su numero (que sale encima de la figura) fuera de los subtitulos
                where = (COUNT_TOP_Y <= y <= -0.10 or 0.17 <= y <= SAFE_Y[1]) if match[k] else abs(y) > 0.09
                if where and all(math.dist(pos, q) > (0.12 if match[k] or match[j] else 0.085) for j, q in placed.items()):
                    break
            else:
                break                              # no cabe: se reintenta todo
            placed[k] = tuple(pos)
        else:
            break
    else:
        raise RuntimeError("conteo: no hay hueco para colocar las figuras")
    for k, (sh, co) in enumerate(items):
        pb[k, 2], pb[k, 3] = sh, T.NAMED_COLORS[co][2]
    gr = T.g(sT)
    cu = "Cuántas" if gr["fem"] else "Cuántos"
    if mode == "shape":
        instr = f"¿{cu} {gr['pl']} hay?"
    elif mode == "color":
        instr = f"¿Cuántas figuras {T.adj_plural(T.NAMED_COLORS[cT][1])} hay?"
    else:
        instr = f"¿{cu} {gr['pl']} {T.adj_plural(T.NAMED_COLORS[cT][1 if gr['fem'] else 0])} hay?"
    reveal = f"Había {T.num_es(m)}. ¿Cuántos contaste?"
    q = (float(sT) if mode != "color" else -1.0, T.NAMED_COLORS[cT][2] if mode != "shape" else -1.0)
    return dict(n=total, q=q, arrays={"u_pa": pa.tobytes(), "u_pb": pb.tobytes()}, p=(rng.random(), rng.random()),
                question=instr, rcap=f"HABÍA {m}", answer=f"{m} (de {total} figuras)",
                voice=_voice(rng, a["i"], "count", S, instr, T.COUNT_MID, reveal))


def _grid_target(rng, cols, rows, cell, st):
    blocked = set(blocked_rows(rows, cell))
    cells = [(c, r) for c in range(cols) for r in range(rows) if r not in blocked and (c, r) != st.get("prev")]
    st["prev"] = rng.choice(cells)
    return st["prev"]


def _flicker(rng, ctx, a, st):
    prog, S = a["prog"], a["S"]
    allowed = [1, 2, 5] + ([] if ctx.pal.mono else [0]) + ([4] if ctx.shape != 0 else [])   # sin 'punto': casi invisible
    kind = _pick(rng, [k for k in allowed if k != st.get("last_kind")] or allowed, st.setdefault("kinds", []))
    st["last_kind"] = kind
    target = _grid_target(rng, ctx.cols, ctx.rows, ctx.cell, st)
    instr = "¿Qué cambia entre las dos imágenes?" if a["i"] else "¿Qué cambia?"
    reveal = T.KIND_REVEAL[kind] + " ¿Lo viste?"
    return dict(kind=kind, delta=1.0 - 0.4 * prog, target=target, p=(rng.random(), rng.random()), question=instr,
                rcap=T.KIND_REVEAL[kind].upper(),
                answer=f"fila {target[1] + 1}, columna {target[0] + 1}: {T.KIND_REVEAL[kind].rstrip('.').lower()}",
                voice=_voice(rng, a["i"], "flicker", S, instr, T.FLICKER_MID, reveal))


def _memory(rng, ctx, a, st):
    prog, S, i = a["prog"], a["S"], a["i"]
    cols, rows, cell = rng.choice(MEMORY_LAYOUTS)
    allowed = [1, 5, 5, 5] + ([] if ctx.pal.mono else [0]) + ([4] if ctx.shape != 0 else [])
    kind = rng.choice(allowed)
    target = _grid_target(rng, cols, rows, cell, st)
    reveal = rng.choice(("Ese cambió. ¿Lo recordabas?", "Ese era. ¿Lo recordaste?")) if not a["last"] else \
        "Ese era. ¿Cuántos acertaste?"
    first = [(0.15, rng.choice(T.HOOK_SHORT)), (1.55, "Memoriza las figuras.")] if (i == 0 and S >= 8.2) else \
        [(0.30, f"{T.SPOKEN_LABEL['memory']} {T.NUMS[i]}. Memoriza las figuras.")]
    return dict(kind=kind, delta=1.0 - 0.4 * prog, target=target, p=(rng.random(), rng.random()),
                grid=(cols, rows, cell, 0), question="Memoriza y encuentra el cambio",
                rcap=T.KIND_REVEAL[kind].upper(),
                answer=f"fila {target[1] + 1}, columna {target[0] + 1}: {T.KIND_REVEAL[kind].rstrip('.').lower()}",
                voice=tuple(first + [(3.1, "Ahora, ¿cuál cambió?"), (S + 0.25, reveal)]))


def _stroop(rng, ctx, a, st):
    S, i = a["S"], a["i"]
    nw = max(3, min(5, int((S - 1.4) / 1.0)))
    step = (S - 1.2) / nw
    inks, items = [], []
    last = None
    for j in range(nw):
        word = rng.choice(T.STROOP_COLORS)
        ink = rng.choice([c for c in T.STROOP_COLORS if c[0] != word[0] and c[0] != last])
        last = ink[0]
        inks.append(ink[0])
        t0 = 0.8 + j * step
        items.append((t0, t0 + step * 0.94, word[0].upper(), 170, ink[1], 640))
    answer = ", ".join(inks)
    items.append((S, a["length"] - 0.1, "TINTAS\\N" + "  ".join(c.upper() for c in inks), 70, "", 640))
    instr = "Di el color de la tinta, no lo que dice."
    voice = _first(rng, i, "stroop", S, instr) + [(S + 0.25, answer.capitalize() + ".")]
    return dict(p=(rng.random(), rng.random()), items=tuple(items), question=instr, answer=answer, voice=tuple(voice),
                kind=1, q=(0.16, (640 - 960) / 1080))


# --- cálculo
_OPS = {"+": "más", "-": "menos", "×": "por"}


def _gen_math(rng, level: int):
    for _ in range(500):
        if level == 0:
            a, b, c = rng.randint(2, 20), rng.randint(2, 9), rng.randint(2, 9)
            toks, value, wrong = [a, "+", b, "×", c], a + b * c, (a + b) * c
        elif level == 1:
            if rng.random() < 0.5:
                a, b, c = rng.randint(2, 15), rng.randint(2, 15), rng.randint(2, 9)
                toks, value, wrong = ["(", a, "+", b, ")", "×", c], (a + b) * c, a + b * c
            else:
                a, b, c, d = (rng.randint(2, 9) for _ in range(4))
                toks, value, wrong = [a, "×", b, "-", c, "×", d], a * b - c * d, ((a * b) - c) * d
        else:
            a, b, c, d = rng.randint(5, 30), rng.randint(2, 9), rng.randint(2, 9), rng.randint(2, 12)
            if rng.random() < 0.5:
                toks, value, wrong = [a, "+", b, "×", c, "-", d], a + b * c - d, (a + b) * c - d
            else:
                toks, value, wrong = [a, "-", b, "+", c, "×", d], a - b + c * d, (a - b + c) * d
        if 0 < value < 1000 and wrong != value and wrong > 0:
            text = " ".join(str(t) for t in toks).replace("( ", "(").replace(" )", ")")
            spoken = " ".join(
                {"(": "abre paréntesis", ")": "cierra paréntesis"}.get(t) or _OPS.get(t) or T.num_es(t) for t in toks)
            return text, spoken, value, wrong
    raise RuntimeError("no se pudo generar una operacion")


def _math(rng, ctx, a, st):
    S, i, prog = a["S"], a["i"], a["prog"]
    level = 0 if prog < 0.34 else 1 if prog < 0.67 else 2
    text, spoken, value, wrong = _gen_math(rng, level)
    q = f"{text} = ?"
    items = ((0.2, S, q, _big(q), "", 640), (S, a["length"] - 0.1, f"{text} = {value}", _big(f"{text} = {value}"), "", 640))
    voice = _first(rng, i, "math", S, f"¿Cuánto es {spoken}?") + [(S + 0.25, f"Es {T.num_es(value)}. ¿Dijiste {T.num_es(wrong)}?")]
    return dict(p=(rng.random(), rng.random()), items=items, question=f"¿Cuánto es {text}?",
                answer=f"{text} = {value} (trampa: {wrong})", voice=tuple(voice), kind=2, q=(0.15, (640 - 960) / 1080))


# --- secuencia
_PRIMES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41)


def _terms(first, step, n=6):
    """Genera n terminos aplicando step(anterior, indice)."""
    seq = [first]
    for j in range(n - 1):
        seq.append(step(seq[-1], j))
    return seq


def _sq_arith_up(rng):
    a, d = rng.randint(1, 30), rng.randint(2, 12)
    return [a + d * j for j in range(6)], f"Suma {T.num_es(d)}."


def _sq_arith_down(rng):
    a, d = rng.randint(40, 99), rng.randint(3, 12)
    return [a - d * j for j in range(6)], f"Resta {T.num_es(d)}."


def _sq_arith_big(rng):
    a, d = rng.randint(50, 200), rng.choice((15, 20, 25, 30, 35, 40, 45))
    return [a + d * j for j in range(6)], f"Suma {T.num_es(d)}."


def _sq_squares(rng):
    s = rng.randint(1, 8)
    return [(s + j) ** 2 for j in range(6)], "Son cuadrados."


def _sq_double(rng):
    a = rng.randint(1, 9)
    return [a * 2 ** j for j in range(6)], "Multiplica por dos."


def _sq_geom3(rng):
    a = rng.randint(1, 4)
    return [a * 3 ** j for j in range(6)], "Multiplica por tres."


def _sq_tri(rng):
    s = rng.randint(1, 6)
    return [(s + j) * (s + j + 1) // 2 for j in range(6)], "Números triangulares."


def _sq_alt(rng):
    a, u, v = rng.randint(1, 20), rng.randint(3, 9), rng.randint(1, 2)
    return _terms(a, lambda x, j: x + (u if j % 2 == 0 else -v)), f"Suma {T.num_es(u)}, resta {T.num_es(v)}."


def _sq_diffinc(rng):
    a, d0, k = rng.randint(1, 10), rng.randint(1, 4), rng.randint(1, 3)
    return _terms(a, lambda x, j: x + d0 + k * j), f"Cada vez se suma {T.num_es(k)} más."


def _sq_sqpm(rng):
    s, sign = rng.randint(2, 8), rng.choice((1, -1))
    return [(s + j) ** 2 + sign for j in range(6)], "Cuadrados más uno." if sign > 0 else "Cuadrados menos uno."


def _sq_fib(rng):
    a, b = rng.randint(1, 9), rng.randint(1, 9)
    seq = [a, b]
    for _ in range(4):
        seq.append(seq[-1] + seq[-2])
    return seq, "Suma los dos anteriores."


def _sq_muladd(rng):
    m, k = rng.choice(((2, 1), (2, -1), (2, 2), (2, 3), (3, 1), (3, -1), (3, -2)))
    a = rng.randint(1, 4)
    verb = f"suma {T.num_es(k)}" if k > 0 else f"resta {T.num_es(-k)}"
    return _terms(a, lambda x, j: m * x + k), f"Multiplica por {T.num_es(m)} y {verb}."


def _sq_cubes(rng):
    s = rng.randint(1, 5)
    return [(s + j) ** 3 for j in range(6)], "Son cubos."


def _sq_interleave(rng):
    a, p, b, q = rng.randint(1, 9), rng.randint(2, 5), rng.randint(30, 60), rng.randint(2, 6)
    return [a, b, a + p, b - q, a + 2 * p, b - 2 * q], "Dos secuencias alternadas."


def _sq_oblong(rng):
    s = rng.randint(1, 6)
    return [(s + j) * (s + j + 1) for j in range(6)], "Número por el siguiente."


def _sq_primes(rng):
    s = rng.randint(0, 5)
    return list(_PRIMES[s:s + 6]), "Son números primos."


def _sq_pow2plus(rng):
    s, k = rng.randint(1, 3), rng.choice((1, -1))
    return [2 ** (s + j) + k for j in range(6)], "Potencias de dos " + ("más uno." if k > 0 else "menos uno.")


# familias por nivel de dificultad (el reto es mas dificil en los ultimos actos)
_SEQ_LEVELS = ((_sq_arith_up, _sq_arith_down, _sq_squares, _sq_double),
               (_sq_geom3, _sq_tri, _sq_alt, _sq_diffinc, _sq_sqpm, _sq_arith_big),
               (_sq_fib, _sq_muladd, _sq_cubes, _sq_interleave, _sq_oblong, _sq_primes, _sq_pow2plus))


def _gen_seq(rng, level: int):
    """-> (numeros mostrados, siguiente, regla corta hablada). 5 terminos visibles y el 6.o es la respuesta."""
    while True:
        seq, rule = rng.choice(_SEQ_LEVELS[level])(rng)
        if len(set(seq)) == 6 and all(0 < x < 5000 for x in seq):       # sin sucesiones constantes ni cifras enormes
            return seq[:5], seq[5], rule


def _sequence(rng, ctx, a, st):
    S, i, prog = a["S"], a["i"], a["prog"]
    seen = st.setdefault("seen", set())
    for _ in range(12):                         # no repetir la misma secuencia dentro del video
        shown, nxt, rule = _gen_seq(rng, 0 if prog < 0.34 else 1 if prog < 0.67 else 2)
        if tuple(shown) not in seen:
            break
    seen.add(tuple(shown))
    seq_txt = ", ".join(map(str, shown))
    q, full = f"{seq_txt}, ?", f"{seq_txt}, {nxt}"
    items = ((0.2, S, q, _big(q), "", 640), (S, a["length"] - 0.1, full, _big(full), "", 600),
             (S, a["length"] - 0.1, rule.rstrip("."), 56, "", 760))
    voice = _first(rng, i, "sequence", S, "¿Qué número sigue en esta secuencia?") + \
        [(S + 0.25, f"Sigue el {T.num_es(nxt)}. {rule}")]
    return dict(p=(rng.random(), rng.random()), items=items, question=f"¿Qué número sigue? {q}",
                answer=f"{nxt} ({rule.rstrip('.').lower()})", voice=tuple(voice), kind=3, q=(0.155, (660 - 960) / 1080))


# Acertijos con números generados: la estructura es conocida (trampas clásicas) pero los datos cambian siempre, así
# que nunca se repite el mismo enunciado. Devuelven (pregunta, respuesta).
_DAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_PAIRS = (("un bate", "una pelota", "El bate", "la pelota"), ("una raqueta", "una pelota", "La raqueta", "la pelota"),
          ("un libro", "un marcapáginas", "El libro", "el marcapáginas"), ("una jarra", "un vaso", "La jarra", "el vaso"))


def _rid_age(rng):
    son, diff = rng.randint(3, 14), rng.randint(24, 36)
    return (f"Entre padre e hijo suman {2 * son + diff} años y el padre tiene {diff} más. ¿Cuántos años tiene el hijo?",
            f"{T.num_es(son).capitalize()} años.")


def _rid_bat(rng):
    cents = rng.choice((5, 10, 15, 20, 25))
    a, b, A, bb = rng.choice(_PAIRS)
    total = f"{1 + 2 * cents / 100:.2f}".replace(".", ",")
    return (f"{a.capitalize()} y {b} cuestan {total} €. {A} cuesta 1 € más que {bb}. ¿Cuánto cuesta {bb}?",
            f"{cents} céntimos.")


def _rid_machines(rng):
    n = rng.choice((3, 4, 6, 7, 8, 9))
    return (f"{T.num_es(n).capitalize()} máquinas hacen {T.num_es(n)} piezas en {T.num_es(n)} minutos. "
            f"¿Cuánto tardan 100 máquinas en hacer 100 piezas?", f"{T.num_es(n).capitalize()} minutos.")


def _rid_lily(rng):
    d = rng.randint(20, 60)
    return (f"Un nenúfar duplica su tamaño cada día y cubre un lago en {d} días. ¿Cuándo cubre la mitad?", f"El día {d - 1}.")


def _rid_bells(rng):
    n, k = rng.choice((3, 4, 5, 6, 7)), rng.choice((1, 2, 3))
    m = rng.randint(n + 2, 12)
    return (f"Un reloj da {n} campanadas en {k * (n - 1)} segundos. ¿Cuánto tarda en dar {m}?", f"{k * (m - 1)} segundos.")


def _rid_cats(rng):
    c, b = rng.choice((2, 3, 4, 5)), rng.choice((50, 60, 80, 100))
    return (f"Si {T.num_es(c)} gatos cazan {T.num_es(c)} ratones en {T.num_es(c)} minutos, ¿cuántos gatos cazan {b} "
            f"ratones en {b} minutos?", f"{T.num_es(c).capitalize()} gatos.")


def _rid_coins(rng):
    x, y = rng.choice(((20, 10), (50, 20), (50, 10), (20, 5), (10, 5), (50, 5), (5, 2), (10, 2), (20, 2)))
    return (f"Dos monedas suman {x + y} céntimos y una no es de {y} céntimos. ¿Cuáles son?", f"Una de {x} y una de {y}.")


def _rid_digits(rng):
    hi, lo = rng.randint(3, 9), rng.randint(1, 2)
    return (f"Soy un número de dos cifras: suman {hi + lo} y, si las invierto, el número baja {9 * (hi - lo)}. ¿Cuál soy?",
            f"{10 * hi + lo}.")


def _rid_piles(rng):
    d, t = rng.choice((10, 20, 30, 40)), rng.choice((60, 80, 100, 120))
    return (f"Reparto {t} monedas en dos montones y uno tiene {d} más que el otro. ¿Cuántas tiene el mayor?", f"{(t + d) // 2}.")


def _rid_days(rng):
    k = rng.randrange(7)
    return (f"Si anteayer fue {_DAYS[k]}, ¿qué día será pasado mañana?", f"{_DAYS[(k + 4) % 7].capitalize()}.")


def _rid_half(rng):
    a, b = rng.choice((10, 12, 14, 15, 18, 20, 24, 30, 40)), rng.randint(5, 20)
    return (f"¿Cuánto es {a} dividido entre medio, más {b}?", f"{2 * a + b}.")


_RIDDLE_FAMILIES = (_rid_age, _rid_bat, _rid_machines, _rid_lily, _rid_bells, _rid_cats, _rid_coins, _rid_digits,
                    _rid_piles, _rid_days, _rid_half)


RIDDLE_Y = 690          # centro del texto del acertijo (px); deja libre la fila del gancho


def _riddle_layout(q: str) -> tuple:
    """(texto con saltos ASS, tamaño): el bloque nunca debe invadir la fila del gancho ni la franja de subtítulos."""
    for width, size in ((24, 84), (28, 72), (32, 64), (36, 58)):
        lines = textwrap.wrap(q, width)
        if len(lines) * size * 1.2 <= 420:
            break
    return "\\N".join(lines), size


def _riddle(rng, ctx, a, st):
    S, i = a["S"], a["i"]
    riddles = load_riddles()
    if rng.random() < 0.3:                      # acertijo con números generados (nunca se repite el enunciado)
        fam = _pick(rng, _RIDDLE_FAMILIES, st.setdefault("fam", []))
        (q, ans), idx = fam(rng), -1
    else:
        idx = _pick(rng, range(len(riddles)), st.setdefault("riddles", []))
        q, ans = riddles[idx]["q"], riddles[idx]["a"]
    wq, qsize = _riddle_layout(q)
    wa, asize = _riddle_layout(ans)
    items = ((0.2, S, wq, qsize, "", RIDDLE_Y), (S, a["length"] - 0.1, "RESPUESTA\\N" + wa, asize, "", RIDDLE_Y))
    block = max((wq.count("\\N") + 1) * qsize, (wa.count("\\N") + 2) * asize) * 1.2          # alto del texto mas alto (px)
    voice = ((0.30, f"{T.SPOKEN_LABEL['riddle']} {T.NUMS[i]}. {q}"), (S + 0.25, ans))
    return dict(sym=idx, p=(rng.random(), rng.random()), items=items, question=q, answer=ans, voice=voice,
                kind=0, q=((block / 2 + 55) / 1080, (RIDDLE_Y - 960) / 1080))


# --- vasos (¿dónde está la bola?)
def _cups(rng, ctx, a, st):
    """Intercambios de vasos con arco: empiezan a los 2 s, aceleran, y terminan 2.2 s antes de revelar."""
    S, prog, i = a["S"], a["prog"], a["i"]
    nc = 3 if prog < 0.5 else 4
    t0, t_end = 2.0, S - 2.2
    dur0 = 0.62 - 0.22 * prog
    swaps, t, last = [], t0, None
    while len(swaps) < 36:
        dur = max(0.26, dur0 * (1.0 - 0.3 * min(1.0, (t - t0) / max(t_end - t0, 1.0))) * rng.uniform(0.92, 1.08))
        if t + dur > t_end:
            break
        pair = tuple(rng.sample(range(nc), 2))
        if set(pair) == last:                    # no repetir el mismo intercambio seguido
            continue
        swaps.append((t, dur, pair[0], pair[1]))
        last = set(pair)
        t += dur + 0.05
    ball = rng.randrange(nc)
    slot = ball
    for _, _, x, y in swaps:
        slot = y if slot == x else x if slot == y else slot
    pa = np.zeros((SWARM_MAX, 4), "f4")
    for k, sw in enumerate(swaps):
        pa[k] = sw
    instr = "Sigue la bola."
    voice = ([(0.15, rng.choice(T.HOOK_SHORT)), (1.8, instr)] if i == 0 and S >= 8.2
             else [(0.30, f"{T.SPOKEN_LABEL['cups']} {T.NUMS[i]}. {instr}")])
    if S >= 9.0:
        voice.append((4.3, rng.choice(T.CUPS_MID)))
    voice += [(S - 1.5, "¿Dónde está?"),
              (S + 0.25, f"Estaba en el {T.num_es(slot + 1)}. " + ("¿Cuántos acertaste?" if a["last"] else "¿La seguiste?"))]
    return dict(n=len(swaps), q=(float(nc), float(ball)), arrays={"u_pa": pa.tobytes()}, p=(S - 2.0, rng.random()),
                question="¿En qué vaso quedó la bola?", rcap=f"ESTABA EN EL {slot + 1}",
                answer=f"vaso {slot + 1} de {nc} ({len(swaps)} cambios)", voice=tuple(voice))


# --- Simón (recuerda el orden)
def _simon(rng, ctx, a, st):
    S, prog, i = a["S"], a["prog"], a["i"]
    period, t0 = 0.80 - 0.12 * prog, 1.2
    L = max(3, min(3 + round(3 * prog), int((S - 2.8 - t0) / period)))
    seq = [rng.randrange(4)]
    while len(seq) < L:
        x = rng.randrange(4)
        if x != seq[-1] or rng.random() < 0.25:
            seq.append(x)
    asked = rng.randint(2, L)                    # el primero es demasiado facil de adivinar
    pad = seq[asked - 1] + 1
    pa = np.zeros((SWARM_MAX, 4), "f4")
    for k, x in enumerate(seq):
        pa[k, 0] = x
    ordinal = T.ORDINALS[asked - 1]
    question = f"¿Qué número fue el {ordinal}?"
    voice = _first(rng, i, "simon", S, "Memoriza el orden.") + [
        (S - 2.4, question), (S + 0.25, f"Fue el {T.num_es(pad)}. " + ("¿Cuántos acertaste?" if a["last"] else "¿Lo recordaste?"))]
    return dict(n=L, q=(period, t0), arrays={"u_pa": pa.tobytes()}, p=(float(asked), rng.random()), question=question,
                rcap=f"FUE EL {pad}", answer=f"secuencia {'-'.join(str(x + 1) for x in seq)}; el {ordinal} fue el {pad}",
                voice=tuple(voice))


# --- número distinto (pares de dígitos de 7 segmentos que se parecen, de fácil a difícil)
DIGIT_PAIRS = (((2, 5), (4, 2), (7, 2), (1, 5), (3, 4)),                        # fáciles: 3-4 segmentos de diferencia
               ((0, 6), (3, 5), (2, 3), (9, 6), (0, 9)),                        # medios: 2 segmentos
               ((8, 0), (8, 6), (8, 9), (6, 5), (9, 3), (5, 9), (1, 7)))        # difíciles: 1 segmento


def _digits(rng, ctx, a, st):
    prog, i, S = a["prog"], a["i"], a["S"]
    tier = 0 if prog < 0.34 else 1 if prog < 0.67 else 2
    base, odd = rng.choice(DIGIT_PAIRS[tier])
    if rng.random() < 0.5:
        base, odd = odd, base
    target = _grid_target(rng, ctx.cols, ctx.rows, ctx.cell, st)
    instr = "Encuentra el número distinto."
    reveal = f"Era el {T.num_es(odd)}. " + ("¿Cuántos acertaste?" if a["last"] else "¿Lo viste?")
    return dict(sym=base, shape=odd, target=target, grid=(ctx.cols, ctx.rows, ctx.cell, 0),
                p=(rng.random(), rng.random()), question=instr, rcap=f"ERA EL {odd}",
                answer=f"fila {target[1] + 1}, columna {target[0] + 1}: un {odd} entre {base}",
                voice=_voice(rng, i, "digits", S, instr, T.DIGITS_MID, reveal))


_BUILDERS = {
    "anomaly": _anomaly, "illusion": _illusion, "sync": _sync, "ishihara": _ishihara, "swarm": _swarm,
    "magiceye": _magiceye, "contrast": _contrast, "count": _count, "flicker": _flicker, "memory": _memory,
    "stroop": _stroop, "math": _math, "sequence": _sequence, "riddle": _riddle,
    "cups": _cups, "simon": _simon, "digits": _digits,
}


def build_acts(rng, mode: str, ctx: Ctx) -> tuple:
    plan = _plan(rng, mode, ctx.avail)
    n = len(plan)
    accent = _bgr(ctx.pal.accent)
    hook = _hook_item(rng, plan, accent)
    state, acts = {}, []
    for i, (ty, start, length, S) in enumerate(plan):
        prog = i / (n - 1) if n > 1 else 0.0
        a = dict(i=i, S=S, start=start, length=length, prog=prog, last=(i == n - 1))
        fields = _BUILDERS[ty](rng, ctx, a, state.setdefault(ty, {}))
        rcap = fields.pop("rcap", "")
        if ty in CAPTION_TYPES:
            fields["items"] = _caption(fields["question"], S, length, rcap, accent,
                                       HOOK_END + 0.1 if i == 0 else 0.25) + tuple(fields.get("items", ()))
        if i == 0:
            fields["items"] = (hook,) + tuple(fields.get("items", ()))
        fields.setdefault("grid", (ctx.cols, ctx.rows, ctx.cell, int(ctx.hex_layout)))
        fields.setdefault("delta", 1.0 - MIN_DELTA_RANGE * prog)
        fields["hue"] = (ctx.pal.hues[(ctx.hue_off + i) % len(ctx.pal.hues)] + ctx.hue_jit) % 1.0
        acts.append(Act(index=i, type=ty, start=start, length=length, search=S, **fields))
    return tuple(acts)
