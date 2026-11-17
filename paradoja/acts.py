"""Generacion de actos: cada tipo de reto crea sus parametros de shader, su narracion y su texto en pantalla."""
import json
import math
import textwrap
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import texts_es as T
from .config import MEMORY_LAYOUTS, SWARM_MAX, VideoSpec
from .scene import (ANOMALY_KINDS, ILLUSIONS, SHAPES, TYPES, Act, Palette, _swarm_act, _swarm_positions,
                    blocked_rows, swarm_clock)

RIDDLES_PATH = Path(__file__).resolve().parent.parent / "content" / "acertijos.json"
FULL_REVEAL_LAST = ("Ese era. ¿Cuántos acertaste?", "Ese era. ¿Los acertaste todos?")


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
        plan.append((ty, t, length, length - 3.0))
        t += length
    return plan


# --------------------------------------------------------------------------- utilidades de narracion
def _voice(rng, i, ty, S, instr, mid_pool=None, reveal="", countdown=True):
    lab = f"{T.SPOKEN_LABEL[ty]} {T.NUMS[i]}."
    v = []
    if i == 0:
        v += [(0.15, rng.choice(T.HOOK_SHORT)), (1.8, instr)]
    else:
        v.append((0.30, f"{lab} {instr}"))
        if mid_pool and S >= 7.0:
            v.append((3.9, rng.choice(mid_pool)))
    if countdown and S >= 7.0:
        v.append((max(5.1, S - 2.9), "Tres. Dos. Uno."))
    v.append((S + 0.25, reveal))
    return tuple(v)


def _reveal(rng, last: bool) -> str:
    return rng.choice(FULL_REVEAL_LAST if last else T.REVEAL)


def _big(text: str, maxlen: int = 0) -> int:
    """Tamaño de fuente (px) para que `text` quepa en ~980 px de ancho."""
    longest = max(len(line) for line in text.split("\\N"))
    return int(min(170, 980 / (0.56 * max(longest, 1))))


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
    return dict(kind=kind, target=target, p=(rng.random(), rng.random()), question=instr,
                answer=f"fila {target[1] + 1}, columna {target[0] + 1} ({T.ANOMALY_DESC[kind]})",
                voice=_voice(rng, a["i"], "anomaly", a["S"], instr, T.MID, _reveal(rng, a["last"])))


def _illusion(rng, ctx, a, st):
    iid = _pick(rng, range(len(ILLUSIONS)), st.setdefault("ill", []))
    instr_pool, mid_pool, rev_pool = T.ILL_TEXT[iid]
    instr, reveal = rng.choice(instr_pool), rng.choice(rev_pool)
    return dict(kind=iid, p=(rng.random(), rng.random()), question=instr,
                answer=f"{T.ILL_NAME[iid]}: {reveal}",
                voice=_voice(rng, a["i"], "illusion", a["S"], instr, mid_pool, reveal))


def _sync(rng, ctx, a, st):
    gr, S = T.g(ctx.shape), a["S"]
    rt_hit = rng.uniform(S - 4.5, S - 0.9)               # dentro de la cuenta atras visible
    hit = round((a["start"] + rt_hit) * ctx.spec.fps) / ctx.spec.fps
    digit = int(S - (hit - a["start"])) + 1
    instr = f"Pausa cuando {gr['el']} {gr['noun']} encaje."
    reveal = f"Encajó en el {T.NUMS[digit - 1]}. " + ("¿Cuántas acertaste?" if a["last"] else "¿Pausaste a tiempo?")
    return dict(p=(rng.random(), rng.random()), hit=hit, question=instr,
                answer=f"encaja cuando el contador marca {digit} (segundo {hit:.2f} del video)",
                voice=_voice(rng, a["i"], "sync", S, instr, T.SYNC_MID, reveal))


def _ishihara(rng, ctx, a, st):
    used = st.setdefault("numbers", [])
    if rng.random() < 0.65:
        sym = _pick(rng, range(10, 100), used)
        shape = rng.randrange(len(SHAPES))
        instr, answer = "¿Qué número hay escondido?", str(sym)
        reveal = f"Era el {T.num_es(sym)}. ¿Lo viste?"
    else:
        sym, shape = -1, _pick(rng, range(len(SHAPES)), st.setdefault("shapes", []))
        gr = T.g(shape)
        instr, answer = "¿Qué figura hay escondida?", gr["noun"]
        reveal = f"Era {gr['el']} {gr['noun']}. ¿Lo viste?"
    return dict(sym=sym, shape=shape, p=(rng.random(), rng.random()), question=instr, answer=answer,
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
    reveal = rng.choice(("Ahí estaba. ¿Lo seguiste?", "Ese era. ¿Acertaste?"))
    voice = [(0.30, f"{T.SPOKEN_LABEL['swarm']} {T.NUMS[i]}. Sigue el punto rojo.")] if i else \
        [(0.15, rng.choice(T.HOOK_SHORT)), (1.8, "Sigue el punto rojo.")]
    voice += [(3.0, "Ahora es igual a todos."), (5.0, "No lo pierdas."), (S - 1.25, "¿Dónde quedó?"), (S + 0.25, reveal)]
    return dict(n=n_part, q=(vmax, 0.0), arrays=arrays, p=(rng.random(), rng.random()),
                question="Sigue el punto rojo", answer=f"queda {_quadrant(x, y)} ({n_part} partículas)", voice=tuple(voice))


def _magiceye(rng, ctx, a, st):
    shape = _pick(rng, range(len(SHAPES)), st.setdefault("shapes", []))
    gr = T.g(shape)
    reveal = f"Era {gr['el']} {gr['noun']}. ¿La viste en 3D?"
    return dict(shape=shape, p=(rng.random(), rng.random()), q=(rng.random(), rng.random()),
                question="Desenfoca la vista y espera", answer=gr["noun"],
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
        instr, reveal, ans = "¿Cuál bloque es más oscuro, el izquierdo o el derecho?", "Son idénticos. El mismo color.", "idénticos"
    else:
        side = "derecha" if dark_left else "izquierda"
        instr, reveal, ans = "¿Cuál bloque es más claro?", f"El de la {side}. Parecía al revés.", f"el de la {side}"
    return dict(kind=kind, p=p, question=instr, answer=ans,
                voice=_voice(rng, a["i"], "contrast", a["S"], instr, T.CONTRAST_MID, reveal))


def _count(rng, ctx, a, st):
    prog, S = a["prog"], a["S"]
    mono = ctx.pal.mono
    shapes = rng.sample(range(len(SHAPES)), 3)
    colors = rng.sample(range(len(T.NAMED_COLORS)), 3)
    mode = "shape" if mono else rng.choice(("shape", "color") if prog < 0.5 else ("shape", "color", "both", "both"))
    sT, cT = rng.choice(shapes), rng.choice(colors)
    total = int(14 + 16 * prog)
    m = rng.randint(3, 8)

    def ok(sh, co):
        return (mode == "color" or sh == sT) and (mode == "shape" or co == cT)

    items = [(sT if mode != "color" else rng.choice(shapes), cT if mode != "shape" else rng.choice(colors))
             for _ in range(m)]
    while len(items) < total:
        sh, co = rng.choice(shapes), rng.choice(colors)
        if not ok(sh, co):
            items.append((sh, co))
    rng.shuffle(items)
    assert sum(ok(*it) for it in items) == m
    pa = np.zeros((SWARM_MAX, 4), "f4")
    pb = np.zeros((SWARM_MAX, 4), "f4")
    for k, (sh, co) in enumerate(items):
        pa[k] = (rng.uniform(.18, .44), rng.uniform(.18, .50), rng.uniform(.5, 1.4), rng.uniform(.5, 1.4))
        pb[k] = (rng.uniform(0, math.tau), rng.uniform(0, math.tau), sh, T.NAMED_COLORS[co][2])
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
                question=instr, answer=f"{m} (de {total} figuras)",
                voice=_voice(rng, a["i"], "count", S, instr, T.COUNT_MID, reveal))


def _grid_target(rng, cols, rows, cell, st):
    blocked = set(blocked_rows(rows, cell))
    cells = [(c, r) for c in range(cols) for r in range(rows) if r not in blocked and (c, r) != st.get("prev")]
    st["prev"] = rng.choice(cells)
    return st["prev"]


def _flicker(rng, ctx, a, st):
    prog, S = a["prog"], a["S"]
    allowed = [1, 2, 3, 5] + ([] if ctx.pal.mono else [0]) + ([4] if ctx.shape != 0 else [])
    kind = _pick(rng, [k for k in allowed if k != st.get("last_kind")] or allowed, st.setdefault("kinds", []))
    st["last_kind"] = kind
    target = _grid_target(rng, ctx.cols, ctx.rows, ctx.cell, st)
    instr = "¿Qué cambia entre una imagen y la otra?" if a["i"] else "¿Qué cambia?"
    reveal = T.KIND_REVEAL[kind] + " ¿Lo viste?"
    return dict(kind=kind, delta=1.0 - 0.4 * prog, target=target, p=(rng.random(), rng.random()), question=instr,
                answer=f"fila {target[1] + 1}, columna {target[0] + 1}: {T.KIND_REVEAL[kind].rstrip('.').lower()}",
                voice=_voice(rng, a["i"], "flicker", S, instr, T.FLICKER_MID, reveal))


def _memory(rng, ctx, a, st):
    prog, S, i = a["prog"], a["S"], a["i"]
    cols, rows, cell = rng.choice(MEMORY_LAYOUTS)
    allowed = [1, 3, 5, 5, 5] + ([] if ctx.pal.mono else [0]) + ([4] if ctx.shape != 0 else [])
    kind = rng.choice(allowed)
    target = _grid_target(rng, cols, rows, cell, st)
    reveal = rng.choice(("Ese cambió. ¿Lo recordabas?", "Ese era. ¿Lo recordaste?")) if not a["last"] else \
        "Ese era. ¿Cuántos acertaste?"
    first = [(0.15, rng.choice(T.HOOK_SHORT)), (1.55, "Memoriza las figuras.")] if i == 0 else \
        [(0.30, f"{T.SPOKEN_LABEL['memory']} {T.NUMS[i]}. Memoriza las figuras.")]
    return dict(kind=kind, delta=1.0 - 0.4 * prog, target=target, p=(rng.random(), rng.random()),
                grid=(cols, rows, cell, 0), question="Memoriza las figuras y encuentra el cambio",
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
    items.append((S, a["length"] - 0.1, "TINTAS\\N" + "  ".join(c.upper() for c in inks), 64, "", 640))
    instr = "Di el color de la tinta, no lo que dice."
    voice = [(0.30, f"{T.SPOKEN_LABEL['stroop']} {T.NUMS[i]}. {instr}")] if i else \
        [(0.15, rng.choice(T.HOOK_SHORT)), (1.8, instr)]
    voice.append((S + 0.25, answer.capitalize() + "."))
    return dict(p=(rng.random(), rng.random()), items=tuple(items), question=instr, answer=answer, voice=tuple(voice))


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
    instr = f"¿Cuánto es {spoken}?"
    voice = [(0.30, f"{T.SPOKEN_LABEL['math']} {T.NUMS[i]}. {instr}")] if i else \
        [(0.15, rng.choice(T.HOOK_SHORT)), (1.8, instr)]
    voice.append((S + 0.25, f"Es {T.num_es(value)}. ¿Dijiste {T.num_es(wrong)}?"))
    return dict(p=(rng.random(), rng.random()), items=items, question=f"¿Cuánto es {text}?",
                answer=f"{text} = {value} (trampa: {wrong})", voice=tuple(voice))


# --- secuencia
def _gen_seq(rng, level: int):
    """-> (numeros mostrados, siguiente, regla corta hablada)"""
    kinds = (("arith", "square"), ("geom", "tri", "alt"), ("fib", "dbl1", "prime"))[level]
    k = rng.choice(kinds)
    if k == "arith":
        a, d = rng.randint(1, 20), rng.randint(2, 9)
        seq, rule = [a + d * j for j in range(6)], f"Suma {T.num_es(d)}."
    elif k == "square":
        s = rng.randint(1, 6)
        seq, rule = [(s + j) ** 2 for j in range(6)], "Son cuadrados."
    elif k == "geom":
        a, r = rng.randint(1, 5), rng.choice((2, 3))
        seq, rule = [a * r ** j for j in range(6)], f"Multiplica por {T.num_es(r)}."
    elif k == "tri":
        s = rng.randint(1, 4)
        seq, rule = [(s + j) * (s + j + 1) // 2 for j in range(6)], "Suma uno más cada vez."
    elif k == "alt":
        a, u, v = rng.randint(1, 20), rng.randint(3, 9), rng.randint(1, 2)
        seq, x = [a], a
        for j in range(5):
            x += u if j % 2 == 0 else -v
            seq.append(x)
        rule = f"Suma {T.num_es(u)}, resta {T.num_es(v)}."
    elif k == "fib":
        a, b = rng.randint(1, 4), rng.randint(1, 5)
        seq = [a, b]
        for _ in range(4):
            seq.append(seq[-1] + seq[-2])
        rule = "Suma los dos anteriores."
    elif k == "dbl1":
        a = rng.randint(1, 3)
        seq = [a]
        for _ in range(5):
            seq.append(seq[-1] * 2 + 1)
        rule = "Duplica y suma uno."
    else:
        seq, rule = [2, 3, 5, 7, 11, 13, 17][:6], "Son números primos."
    return seq[:4 if k == "prime" else 5], seq[4 if k == "prime" else 5], rule


def _sequence(rng, ctx, a, st):
    S, i, prog = a["S"], a["i"], a["prog"]
    shown, nxt, rule = _gen_seq(rng, 0 if prog < 0.34 else 1 if prog < 0.67 else 2)
    seq_txt = ", ".join(map(str, shown))
    q, full = f"{seq_txt}, ?", f"{seq_txt}, {nxt}"
    items = ((0.2, S, q, _big(q), "", 640), (S, a["length"] - 0.1, full, _big(full), "", 600),
             (S, a["length"] - 0.1, rule.rstrip("."), 56, "", 760))
    instr = "¿Qué número sigue en esta secuencia?"
    voice = [(0.30, f"{T.SPOKEN_LABEL['sequence']} {T.NUMS[i]}. {instr}")] if i else \
        [(0.15, rng.choice(T.HOOK_SHORT)), (1.8, instr)]
    voice.append((S + 0.25, f"Sigue el {T.num_es(nxt)}. {rule}"))
    return dict(p=(rng.random(), rng.random()), items=tuple(items), question=f"¿Qué número sigue? {q}",
                answer=f"{nxt} ({rule.rstrip('.').lower()})", voice=tuple(voice))


def _riddle(rng, ctx, a, st):
    S, i = a["S"], a["i"]
    riddles = load_riddles()
    idx = _pick(rng, range(len(riddles)), st.setdefault("riddles", []))
    q, ans = riddles[idx]["q"], riddles[idx]["a"]
    wq = "\\N".join(textwrap.wrap(q, 24))
    wa = "RESPUESTA\\N" + "\\N".join(textwrap.wrap(ans, 24))
    items = ((0.2, S, wq, 84, "", 600), (S, a["length"] - 0.1, wa, 84, "", 600))
    voice = ((0.30, f"{T.SPOKEN_LABEL['riddle']} {T.NUMS[i]}. {q}"), (S + 0.25, ans))
    return dict(sym=idx, p=(rng.random(), rng.random()), items=items, question=q, answer=ans, voice=voice)


_BUILDERS = {
    "anomaly": _anomaly, "illusion": _illusion, "sync": _sync, "ishihara": _ishihara, "swarm": _swarm,
    "magiceye": _magiceye, "contrast": _contrast, "count": _count, "flicker": _flicker, "memory": _memory,
    "stroop": _stroop, "math": _math, "sequence": _sequence, "riddle": _riddle,
}


def build_acts(rng, mode: str, ctx: Ctx) -> tuple:
    plan = _plan(rng, mode, ctx.avail)
    n = len(plan)
    state, acts = {}, []
    for i, (ty, start, length, S) in enumerate(plan):
        prog = i / (n - 1) if n > 1 else 0.0
        a = dict(i=i, S=S, start=start, length=length, prog=prog, last=(i == n - 1))
        fields = _BUILDERS[ty](rng, ctx, a, state.setdefault(ty, {}))
        fields.setdefault("grid", (ctx.cols, ctx.rows, ctx.cell, int(ctx.hex_layout)))
        fields.setdefault("delta", 1.0 - 0.7 * prog)
        fields["hue"] = (ctx.pal.hues[(ctx.hue_off + i) % len(ctx.pal.hues)] + ctx.hue_jit) % 1.0
        acts.append(Act(index=i, type=ty, start=start, length=length, search=S, **fields))
    return tuple(acts)
