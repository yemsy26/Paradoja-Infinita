"""Modelo de datos y generacion procedural determinista.

Un video es una lista de *actos*. Cada acto es un reto de un tipo (TYPES). Un video de tipo unico repite el mismo
tipo; el video "mix" combina tipos distintos. La semilla decide paleta, figura, estructura y contenido."""
import colorsys
import math
import random
from dataclasses import dataclass

import numpy as np

from . import copy_es
from .spin import fill
from .config import ANSWER_TOP, BOTTOM_SAFE, LAYOUTS, SAFE_Y, SUB_BAND, SWARM_MAX, VideoSpec


@dataclass(frozen=True)
class TypeInfo:
    name: str
    scene_id: int      # valor de u_scene en el shader
    hud: str           # etiqueta en pantalla
    base_len: float    # duracion base de un acto (busqueda + 3 s de revelacion)
    countdown: bool    # muestra cuenta atras 5..1
    category: str
    menu: str          # nombre en el menu
    desc: str
    reveal: float = 3.0   # duracion de la revelacion (los retos con texto necesitan mas para leer la respuesta)


TYPES = {t.name: t for t in (
    TypeInfo("anomaly", 0, "RETO", 11.0, True, "Visual", "Reto de anomalía", "Encuentra la figura distinta"),
    TypeInfo("illusion", 1, "ILUSIÓN", 11.0, True, "Visual", "Ilusión óptica", "Patrones que engañan al cerebro"),
    TypeInfo("ishihara", 4, "TEST", 11.0, True, "Visual", "Test de visión", "Número o figura oculta entre puntos"),
    TypeInfo("magiceye", 6, "OJO MÁGICO", 12.0, True, "Visual", "Ojo mágico", "Figura 3D oculta (desenfoca la vista)"),
    TypeInfo("contrast", 7, "CONTRASTE", 10.0, True, "Visual", "Contraste", "Cuál es más claro / ¿cambió el color?"),
    TypeInfo("sync", 3, "PAUSA", 11.0, True, "Reflejos", "Sincronización", "Pausa justo cuando la figura encaja"),
    TypeInfo("swarm", 5, "RONDA", 12.0, False, "Atención", "Seguimiento", "Sigue el punto rojo entre el caos"),
    TypeInfo("count", 8, "CUENTA", 12.0, True, "Atención", "Conteo", "¿Cuántas figuras de este tipo hay?", 3.5),
    TypeInfo("flicker", 9, "¿QUÉ CAMBIA?", 11.0, True, "Atención", "Qué cambió", "Detecta lo que cambia entre dos imágenes"),
    TypeInfo("memory", 9, "MEMORIA", 12.0, False, "Memoria", "Memoria", "Memoriza las figuras y encuentra el cambio"),
    TypeInfo("stroop", 10, "COLORES", 9.5, False, "Mente", "Efecto Stroop", "Di el color de la tinta, no la palabra", 3.5),
    TypeInfo("math", 10, "CÁLCULO", 12.5, True, "Mente", "Cálculo", "Operaciones con trampa de orden", 5.0),
    TypeInfo("sequence", 10, "SECUENCIA", 11.0, True, "Mente", "Secuencia", "¿Qué número sigue?", 3.5),
    TypeInfo("riddle", 10, "ACERTIJO", 14.0, False, "Mente", "Acertijo", "Acertijos y preguntas trampa", 5.0),
    TypeInfo("cups", 11, "VASOS", 12.0, False, "Atención", "Vasos", "¿En qué vaso quedó la bola?"),
    TypeInfo("simon", 12, "SIMÓN", 11.5, False, "Memoria", "Simón", "Recuerda el orden en que se iluminan los pads"),
    TypeInfo("digits", 13, "NÚMEROS", 11.0, True, "Visual", "Número distinto", "Encuentra el número diferente"),
)}
# formatos de video: cada tipo por separado + bucle perfecto + mix de tipos distintos
MODES = (*TYPES, "loop", "mix")
LOOP_SCENE_ID = 2

ANOMALY_KINDS = ("hue", "size", "bright", "dot", "rotate", "missing")  # indice = u_kind (5 solo en flicker/memory)
ILLUSIONS = ("ouchi", "cafe", "ebbinghaus", "scintillating", "spiral", "moire", "hermann", "mullerlyer", "kanizsa", "zollner")

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
    tun_a: tuple     # color claro (ilusiones / bucle / cierre)
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
    type: str
    start: float             # segundo de inicio en el video
    length: float            # duracion total (busqueda + revelacion)
    search: float            # duracion de la fase de busqueda
    kind: int = 0            # variante dentro del tipo (u_kind)
    delta: float = 1.0       # facilidad: 1.0 facil -> 0.3 dificil
    target: tuple = (0, 0)   # (col, fila) en retos de rejilla
    hue: float = 0.0
    p: tuple = (0.5, 0.5)    # parametros aleatorios (u_actp)
    q: tuple = (0.0, 0.0)    # extras: ojo magico (a, b) | enjambre (vmax) | conteo (filtro figura, filtro color)
    sym: int = -1            # ishihara: numero 10-99 (o -1 = figura) | acertijo: indice del acertijo
    shape: int = 0           # figura oculta (ishihara / ojo magico)
    hit: float = 0.0         # sync: instante global del encaje, alineado a un frame
    n: int = 0               # particulas (enjambre) / figuras (conteo)
    arrays: object = None    # {uniform: bytes} para enjambre y conteo
    grid: tuple = (0, 0, 0, 0)   # columnas, filas, celda px, hexagonal
    voice: tuple = ()        # ((t_rel, texto), ...) narracion del acto
    items: tuple = ()        # ((t0, t1, texto, tamaño_max, bgr), ...) texto en pantalla
    question: str = ""       # pregunta del reto (para la metadata)
    answer: str = ""         # respuesta legible (para la metadata)

    @property
    def end(self) -> float:
        return self.start + self.length


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
    hook_kind: int   # escena del cierre y del bucle: 0 tunel log-polar, 1 tunel poligonal, 2 caleidoscopio
    hook_sides: int
    outro_len: float
    rnd: tuple
    acts: tuple
    loop_kind: int
    loop_k: int
    loop_period: float
    loop_ints: tuple
    # Textos dichos y quemados en pantalla, elegidos por semilla (ver copy_es.py)
    hook: str = ""       # gancho de apertura (se narra en 0.15 s y se muestra en grande mientras dura `lead`)
    lead: float = 0.0    # segundos de apertura antes del primer acto (el primer reto esta quieto y visible)
    cta: str = ""        # llamada a seguir de los ultimos `outro_len` segundos (se narra y se muestra)


SWARM_CY = -0.02


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


def _swarm_act(rng, n_part, vmax, S):
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
        if abs(pos[0, 1]) > 0.11 and SAFE_Y[0] <= pos[0, 1] <= SAFE_Y[1] and dist > 0.07:
            return {"u_pa": pa.tobytes(), "u_pb": pb.tobytes()}


def blocked_rows(rows: int, cell: int, height: int = 1920) -> tuple:
    """Filas donde NO puede caer la respuesta: bajo los subtitulos o fuera de la zona segura de la app."""
    top = (height - rows * cell) / 2
    out = []
    for r in range(rows):
        y0, y1 = top + r * cell, top + (r + 1) * cell
        centre = (y0 + y1) / 2
        if (y0 < SUB_BAND[1] and y1 > SUB_BAND[0]) or not ANSWER_TOP + 0.4 * cell <= centre <= BOTTOM_SAFE - 20:
            out.append(r)
    return tuple(out)


def build_scene(seed: int, mode: str, spec: VideoSpec) -> Scene:
    from . import acts as acts_mod  # import tardio: acts depende de este modulo

    if mode not in MODES:
        raise ValueError(f"modo desconocido: {mode}")
    rng = random.Random(seed)
    pal = rng.choice(PALETTES)
    shape = rng.randrange(len(SHAPES))
    cols, rows, cell = rng.choice(LAYOUTS)
    hex_layout = rng.random() < 0.4
    outro_len = rng.choice((4.0, 4.5, 5.0))   # cierre: llamada a seguir (voz + pantalla), nota y compartir
    hue_off = rng.randrange(len(pal.hues))
    hue_jit = rng.uniform(-0.02, 0.02)

    # Textos propios con un generador aparte: elegirlos no consume numeros del generador de los retos (el largo del
    # gancho si fija `lead`, y con el, el tiempo que queda para los actos)
    trng = random.Random(seed ^ 0x7E27)
    loop = mode == "loop"
    category = TYPES[mode].category if mode in TYPES else None
    hook = copy_es.make_hook(trng, category, "<n>", loop=loop)           # <n> se rellena al conocer el numero de retos
    cta = copy_es.make_cta(trng, loop=loop)
    lead = 0.0 if loop else copy_es.hook_lead(hook)

    acts = ()
    if not loop:
        ctx = acts_mod.Ctx(pal, shape, cols, rows, cell, hex_layout, hue_off, hue_jit, spec,
                           spec.duration - outro_len - lead, lead)
        acts = acts_mod.build_acts(rng, mode, ctx)
    hook = fill(hook, n=len(acts))

    k = rng.choice((3, 5, 7, 9))
    ints = tuple(rng.choice((-3, -2, -1, 1, 2, 3)) for _ in range(3))
    return Scene(
        seed, mode, pal, shape, hex_layout, cols, rows, cell,
        rng.randrange(4), rng.uniform(0.5, 1.9), rng.randrange(4), rng.choice((0.0, 0.0, 0.5, -0.5, 0.9)),
        rng.randrange(3), rng.choice((3, 4, 5, 6, 8)), outro_len,
        tuple(rng.random() for _ in range(4)), tuple(acts),
        rng.randrange(3), k, spec.duration / k, ints, hook=hook, lead=lead, cta=cta,
    )


def shader_static(sc: Scene) -> dict:
    """Uniforms constantes durante todo el video (los que dependen del acto los entrega Timeline)."""
    p = sc.palette
    return {
        "u_shape": sc.shape, "u_motion": sc.motion, "u_speed": sc.speed, "u_bgstyle": sc.bgstyle, "u_spin": sc.spin,
        "u_hook": sc.hook_kind, "u_hooksides": sc.hook_sides, "u_rnd": sc.rnd,
        "u_loopkind": sc.loop_kind, "u_lint": tuple(float(x) for x in sc.loop_ints), "u_loopP": sc.loop_period,
        "u_bg1": p.bg1, "u_bg2": p.bg2, "u_tuna": p.tun_a, "u_tunb": p.tun_b, "u_accent": p.accent,
        "u_sv": (p.sat, p.val),
    }
