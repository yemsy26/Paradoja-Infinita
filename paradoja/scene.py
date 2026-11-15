"""Generacion procedural determinista: la semilla decide paleta, forma, layout, movimiento,
estructura temporal (gancho, nº de actos), tipo de ilusion y tipo de bucle."""
import colorsys
import math
import random
from dataclasses import dataclass

import numpy as np

from .config import LAYOUTS, REVEAL_LEN, SUB_BAND, SWARM_MAX, VideoSpec

MODES = ("anomaly", "illusion", "loop", "sync", "ishihara", "swarm", "magiceye", "contrast")
MODE_IDS = {m: i for i, m in enumerate(MODES)}  # = u_scene en el shader
# palabra de la etiqueta en pantalla / narracion para cada modo con actos
HUD_LABEL = {"anomaly": "RETO", "illusion": "ILUSIÓN", "sync": "PAUSA", "ishihara": "TEST",
             "swarm": "SEGUIMIENTO", "magiceye": "OJO MÁGICO", "contrast": "CONTRASTE"}
HAS_COUNTDOWN = {"anomaly", "illusion", "sync", "ishihara", "magiceye", "contrast"}  # el enjambre no usa cuenta atras

# anomalia: indice = u_kind. 0 color, 1 tamaño, 2 brillo, 3 punto, 4 giro
ANOMALY_KINDS = ("hue", "size", "bright", "dot", "rotate")
# ilusiones: indice = u_kind
ILLUSIONS = ("ouchi", "cafe", "ebbinghaus", "scintillating", "spiral", "moire")

# (sustantivo, es femenino). Indice = u_shape
SHAPES = (("círculo", False), ("triángulo", False), ("rombo", False), ("hexágono", False),
          ("estrella", True), ("pentágono", False), ("cuadrado", False))


def _rgb(h, s, v):
    return colorsys.hsv_to_rgb(h, s, v)


@dataclass(frozen=True)
class Palette:
    name: str
    hues: tuple      # tonos candidatos para las figuras (uno por acto)
    sat: float
    val: float
    bg1: tuple
    bg2: tuple
    tun_a: tuple     # color claro (gancho / ilusiones / bucle)
    tun_b: tuple     # color oscuro
    accent: tuple    # anillo de revelacion, resaltado de subtitulos, barra
    mono: bool = False


PALETTES = (
    Palette("neon cyberpunk", (0.50, 0.85, 0.30, 0.08, 0.95), 0.85, 0.75,
            _rgb(.72, .9, .06), _rgb(.80, .8, .24), _rgb(.88, .9, 1.0), _rgb(.55, .9, .14), _rgb(.15, .9, 1.0)),
    Palette("tonos calidos", (0.02, 0.06, 0.10, 0.0, 0.97), 0.85, 0.75,
            _rgb(.03, .8, .07), _rgb(.05, .7, .26), _rgb(.09, .9, 1.0), _rgb(.0, .9, .16), _rgb(.13, .3, 1.0)),
    Palette("blanco y negro", (0.0,), 0.0, 0.74,
            (0.02, 0.02, 0.02), (0.14, 0.14, 0.14), (0.97, 0.97, 0.97), (0.03, 0.03, 0.03), (1.0, 0.15, 0.15), True),
    Palette("oceano", (0.50, 0.55, 0.60, 0.45, 0.52), 0.80, 0.75,
            _rgb(.60, .9, .05), _rgb(.52, .8, .24), _rgb(.50, .6, 1.0), _rgb(.62, .95, .18), _rgb(.08, .9, 1.0)),
    Palette("acido toxico", (0.28, 0.22, 0.33, 0.18, 0.40), 0.90, 0.75,
            _rgb(.78, .9, .06), _rgb(.80, .8, .22), _rgb(.25, .95, 1.0), _rgb(.80, .9, .18), _rgb(.92, .9, 1.0)),
)


@dataclass(frozen=True)
class Act:
    index: int
    kind: int        # anomaly: ANOMALY_KINDS idx | illusion: ILLUSIONS idx
    delta: float     # fuerza de la diferencia (anomalia)
    target: tuple    # (col, fila)
    hue: float
    p: tuple         # 2 parametros aleatorios por acto (variantes de cada ilusion)
    q: tuple = (0.0, 0.0)   # parametros extra: ojo magico (periodo, desplazamiento) | enjambre (vmax, -)
    sym: int = -1           # ishihara: numero 10-99 oculto, o -1 = figura
    shape: int = 0          # ishihara/ojo magico: figura oculta (indice SHAPES)
    hit: float = 0.0        # sync: instante global (s) del encaje, alineado a un frame
    n: int = 0              # enjambre: nº de particulas
    arrays: object = None   # enjambre: {uniform: bytes}


@dataclass(frozen=True)
class Scene:
    seed: int
    mode: str
    palette: Palette
    shape: int
    hex_layout: bool
    cols: int
    rows: int
    cell: int
    motion: int      # 0 flote, 1 orbita, 2 onda horizontal, 3 onda vertical
    speed: float
    bgstyle: int
    spin: float
    hook_kind: int   # 0 tunel log-polar, 1 tunel poligonal, 2 caleidoscopio
    hook_sides: int
    hook_len: float
    outro_len: float
    rnd: tuple
    acts: tuple
    loop_kind: int
    loop_k: int
    loop_period: float
    loop_ints: tuple


def swarm_clock(rt: float, S: float, vmax: float) -> float:
    """Reloj del enjambre (integral de la velocidad): lento mientras destaca el rojo (0-2 s), rampa
    agresiva (2-3 s), meseta, frenada suave y parada total 1 s antes de revelar."""
    v0, stop = 0.35, S - 2.0
    rt = max(0.0, min(rt, S))
    if rt <= 2.0:
        return v0 * rt
    t = min(rt, 3.0) - 2.0
    s = v0 * 2.0 + v0 * t + (vmax - v0) * t * t / 2.0
    if rt <= 3.0:
        return s
    s += vmax * (min(rt, stop) - 3.0)
    if rt <= stop:
        return s
    u = min(rt - stop, 1.0)
    return s + vmax * (1.0 - (1.0 - u) ** 3) / 3.0


def _swarm_positions(pa, pb, n, s):
    t = np.arange(n)
    x = pa[t, 0] * np.sin(pa[t, 2] * s + pb[t, 0])
    y = SWARM_CY + pa[t, 1] * np.sin(pa[t, 3] * s + pb[t, 1])
    return np.stack([x, y], axis=1)


SWARM_CY = -0.02


def _swarm_act(rng, i, n_part, vmax, S):
    """Parametros de las particulas (la 0 es la objetivo). Se re-muestrea hasta que, al detenerse, la
    objetivo quede fuera de la franja de subtitulos y no tapada por otra particula."""
    s_end = swarm_clock(S, S, vmax)
    while True:
        pa = np.zeros((SWARM_MAX, 4), "f4")
        pb = np.zeros((SWARM_MAX, 4), "f4")
        for k in range(n_part):
            pa[k] = (rng.uniform(.22, .44), rng.uniform(.20, .50), rng.uniform(.8, 2.3), rng.uniform(.8, 2.3))
            pb[k, 0], pb[k, 1] = rng.uniform(0, math.tau), rng.uniform(0, math.tau)
        pos = _swarm_positions(pa, pb, n_part, s_end)
        dist = np.linalg.norm(pos[1:] - pos[0], axis=1).min()
        if abs(pos[0, 1]) > 0.11 and dist > 0.07:
            return {"u_pa": pa.tobytes(), "u_pb": pb.tobytes()}


def _blocked_rows(rows: int, cell: int, height: int = 1920) -> tuple:
    top = (height - rows * cell) / 2
    return tuple(r for r in range(rows) if top + r * cell < SUB_BAND[1] and top + (r + 1) * cell > SUB_BAND[0])


def build_scene(seed: int, mode: str, spec: VideoSpec) -> Scene:
    rng = random.Random(seed)
    pal = rng.choice(PALETTES)
    shape = rng.randrange(len(SHAPES))
    cols, rows, cell = rng.choice(LAYOUTS)
    hex_layout = rng.random() < 0.4
    n = rng.choice((4, 5))
    hook_len = rng.choice((4.0, 5.0, 6.0))
    outro_len = rng.choice((3.0, 3.5))
    hue_off = rng.randrange(len(pal.hues))
    hue_jit = rng.uniform(-0.02, 0.02)

    acts = ()
    if mode == "anomaly":
        allowed = [1, 2, 3] + ([] if pal.mono else [0]) + ([4] if shape != 0 else [])
        kinds = []
        while len(kinds) < n:
            cand = allowed[:]
            rng.shuffle(cand)
            if kinds and cand[0] == kinds[-1]:
                cand.reverse()
            kinds += cand
        blocked = set(_blocked_rows(rows, cell))
        cells = [(c, r) for c in range(cols) for r in range(rows) if r not in blocked]
        acts, prev = [], None
        for i in range(n):
            target = rng.choice([c for c in cells if c != prev])
            prev = target
            delta = 1.0 - 0.7 * i / (n - 1)
            hue = (pal.hues[(hue_off + i) % len(pal.hues)] + hue_jit) % 1.0
            acts.append(Act(i, kinds[i], delta, target, hue, (rng.random(), rng.random())))
    elif mode == "illusion":
        ids = rng.sample(range(len(ILLUSIONS)), n)
        acts = [Act(i, ids[i], 0.0, (0, 0), 0.0, (rng.random(), rng.random())) for i in range(n)]
    elif mode in ("sync", "ishihara", "swarm", "magiceye", "contrast"):
        act_len = (spec.duration - hook_len - outro_len) / n
        S = act_len - REVEAL_LEN
        acts = []
        numbers = rng.sample(range(10, 100), n)
        magic_shapes = rng.sample(range(len(SHAPES)), n)
        ishi_shapes = rng.sample(range(len(SHAPES)), n)
        cvar = [i % 3 for i in range(n)]
        rng.shuffle(cvar)
        for i in range(n):
            delta = 1.0 - 0.7 * i / (n - 1)           # 1.0 facil -> 0.3 dificil
            hue = (pal.hues[(hue_off + i) % len(pal.hues)] + hue_jit) % 1.0
            p = (rng.random(), rng.random())
            kw = {}
            if mode == "sync":
                rt_hit = rng.uniform(S - 4.5, S - 0.9)  # siempre dentro de los ultimos 4.5 s (cuenta atras visible)
                kw["hit"] = round((hook_len + i * act_len + rt_hit) * spec.fps) / spec.fps
            elif mode == "ishihara":
                kw["sym"] = numbers[i] if rng.random() < 0.65 else -1
                kw["shape"] = ishi_shapes[i]
            elif mode == "swarm":
                n_part = min(SWARM_MAX, 18 + 5 * i)
                vmax = 3.0 + 0.9 * i
                kw.update(n=n_part, q=(vmax, 0.0), arrays=_swarm_act(rng, i, n_part, vmax, S))
            elif mode == "magiceye":
                kw["shape"] = magic_shapes[i]
                kw["q"] = (rng.random(), rng.random())
            acts.append(Act(i, cvar[i] if mode == "contrast" else 0, delta, (0, 0), hue, p, **kw))

    k = rng.choice((3, 5, 7, 9))
    ints = tuple(rng.choice((-3, -2, -1, 1, 2, 3)) for _ in range(3))
    return Scene(
        seed, mode, pal, shape, hex_layout, cols, rows, cell,
        rng.randrange(4), rng.uniform(0.5, 1.9), rng.randrange(4), rng.choice((0.0, 0.0, 0.5, -0.5, 0.9)),
        rng.randrange(3), rng.choice((3, 4, 5, 6, 8)), hook_len, outro_len,
        tuple(rng.random() for _ in range(4)), tuple(acts),
        rng.randrange(3), k, spec.duration / k, ints,
    )


def shader_static(sc: Scene) -> dict:
    """Uniforms constantes durante todo el video."""
    p = sc.palette
    return {
        "u_scene": MODE_IDS[sc.mode], "u_shape": sc.shape, "u_hex": int(sc.hex_layout),
        "u_grid": (float(sc.cols), float(sc.rows)), "u_cell": float(sc.cell),
        "u_motion": sc.motion, "u_speed": sc.speed, "u_bgstyle": sc.bgstyle, "u_spin": sc.spin,
        "u_hook": sc.hook_kind, "u_hooksides": sc.hook_sides, "u_rnd": sc.rnd,
        "u_loopkind": sc.loop_kind, "u_lint": tuple(float(x) for x in sc.loop_ints),
        "u_loopP": sc.loop_period,
        "u_bg1": p.bg1, "u_bg2": p.bg2, "u_tuna": p.tun_a, "u_tunb": p.tun_b, "u_accent": p.accent,
        "u_sv": (p.sat, p.val),
    }
