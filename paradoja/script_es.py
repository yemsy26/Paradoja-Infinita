"""Guion de narracion en español adaptado al modo (anomalia / ilusion / bucle), variantes por semilla."""
import random
from dataclasses import dataclass

from .config import BRAND_SPOKEN
from .scene import ANOMALY_KINDS, SHAPES, Scene
from .timeline import Timeline


@dataclass(frozen=True)
class Segment:
    start: float
    text: str


NUMS = ("uno", "dos", "tres", "cuatro", "cinco", "seis")
TENS = {10: "diez", 20: "veinte", 30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta"}
MID = ("Mira bien.", "No parpadees.", "Concéntrate.", "Sin trampas.")
REVEAL = ("Ahí estaba. ¿Lo viste?", "Ese era. ¿Acertaste?", "Mira dónde estaba. ¿Lo encontraste?")
FINAL_REVEAL = ("Ese era. ¿Los acertaste todos?", "Ese era. ¿Cuántos acertaste?")


# --------------------------------------------------------------------------- anomalia
def _g(shape: int) -> dict:
    noun, fem = SHAPES[shape]
    return dict(noun=noun, el="la" if fem else "el", un="una" if fem else "un",
                Uno="Una" if fem else "Uno", o="a" if fem else "o")


def _anomaly_instr(kind: str, g: dict) -> tuple:
    n, el, o = g["noun"], g["el"], g["o"]
    return {
        "hue": (f"Encuentra {el} {n} de otro color.", f"{g['Uno']} tiene otro color. Encuéntral{o}."),
        "size": (f"Encuentra {el} {n} más pequeñ{o}.", f"{g['Uno']} es más pequeñ{o} que los demás."),
        "bright": (f"Encuentra {el} {n} más brillante.", f"{g['Uno']} brilla más que el resto."),
        "dot": ("Encuentra el punto fuera de lugar.", f"{g['Uno']} tiene el punto descentrado."),
        "rotate": (f"Encuentra {el} {n} que está girad{o}.", f"{g['Uno']} está girad{o}. Encuéntral{o}."),
    }[kind]


def _anomaly_hooks(g: dict, n_acts: int) -> tuple:
    return (
        f"Solo el uno por ciento encuentra {g['el']} {g['noun']} diferente. ¿Serás tú?",
        "Tu cerebro cree que es fácil. No lo es. Acepta el reto.",
        f"Casi nadie pasa el reto {NUMS[n_acts - 1]}. Veamos si tú puedes.",
        "Tienes pocos segundos por reto. Sin trampas.",
        f"Hay {g['un']} {g['noun']} distinto escondido. ¿Lo ves?",
    )


# --------------------------------------------------------------------------- ilusiones
# id (ver scene.ILLUSIONS) -> (instrucciones, lineas intermedias, revelaciones)
ILL_TEXT = {
    0: (("¿Ves cómo se mueve el círculo del centro?", "¿Se mueve el círculo del centro?"),
        ("Míralo bien.", "Obsérvalo."),
        ("Nada se mueve. Es una ilusión.", "Está totalmente quieto.")),
    1: (("¿Las líneas están torcidas?", "¿Estas líneas son rectas o inclinadas?"),
        ("¿Torcidas?", "Mira bien."),
        ("Son totalmente paralelas.", "Todas son rectas. Tu cerebro te engañó.")),
    2: (("¿Cuál círculo central es más grande?", "¿Cuál de los dos círculos del centro es mayor?"),
        ("Decide ya.", "Elige rápido."),
        ("Son idénticos. Tu cerebro te engañó.", "Miden exactamente lo mismo.")),
    3: (("¿Ves puntos negros parpadeando?", "Hay puntos negros apareciendo. ¿Los ves?"),
        ("Cuéntalos.", "Mira bien."),
        ("No hay ninguno. Todos son blancos.", "Nunca hubo puntos negros.")),
    4: (("Mira fijamente el centro.", "No apartes los ojos del punto central."),
        ("No parpadees.", "Sigue mirando."),
        ("Ahora mira tu mano. ¡Se mueve!", "Mira tu mano. ¿Se mueve?")),
    5: (("¿Cuántas capas se mueven?", "¿Ves ondas moviéndose? Cuéntalas."),
        ("Observa.", "Mira bien."),
        ("Solo son dos mallas girando.", "Dos capas. Nada más.")),
}
ILL_HOOKS = (
    "Tu cerebro te está mintiendo. Mira bien.",
    "Estas ilusiones engañan a casi todos. ¿Y a ti?",
    "Lo que vas a ver no es real.",
    "{n} ilusiones. ¿Cuántas te engañan?",
)

# --------------------------------------------------------------------------- bucle
LOOP_HOOKS = (
    "Este video es un bucle perfecto. ¿Puedes ver dónde empieza?",
    "No tiene principio ni final. Intenta encontrarlos.",
    "Mira fijamente. Esto nunca termina.",
)
LOOP_FILLERS = ("Sigue mirando. No tiene final.", "Tu cerebro busca el inicio.", "Imposible apartar la vista.",
                "Quédate hasta el final.", "¿Ya encontraste dónde empieza?")


# --------------------------------------------------------------------------- modos de interaccion
_SPECIAL = {10: "diez", 11: "once", 12: "doce", 13: "trece", 14: "catorce", 15: "quince", 16: "dieciséis",
            17: "diecisiete", 18: "dieciocho", 19: "diecinueve", 20: "veinte", 21: "veintiuno", 22: "veintidós",
            23: "veintitrés", 24: "veinticuatro", 25: "veinticinco", 26: "veintiséis", 27: "veintisiete",
            28: "veintiocho", 29: "veintinueve"}
_TENS = {3: "treinta", 4: "cuarenta", 5: "cincuenta", 6: "sesenta", 7: "setenta", 8: "ochenta", 9: "noventa"}
_UNITS = ("", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve")


def num_es(n: int) -> str:
    """Numero 10-99 en palabras (para que el TTS lo lea bien)."""
    if n in _SPECIAL:
        return _SPECIAL[n]
    t, u = divmod(n, 10)
    return _TENS[t] + (f" y {_UNITS[u]}" if u else "")


HOOKS_NEW = {
    "sync": ("Pausa el video justo cuando la figura encaje. Tienes un solo fotograma.",
             "Casi nadie logra pausar en el instante exacto. ¿Y tú?", "Reflejos al límite. Pausa cuando encaje."),
    "ishihara": ("Solo una de cada diez personas ve lo que hay escondido.",
                 "Test de visión. ¿Qué escondí entre los puntos?", "Entrecierra los ojos. Hay algo escondido."),
    "swarm": ("Sigue el punto rojo con los ojos. Solo los mejores no lo pierden.",
              "Tu atención contra el caos. Sigue el punto rojo."),
    "magiceye": ("Relaja la vista y mira a través de la pantalla. Hay una figura en 3D escondida.",
                 "Desenfoca la mirada. Algo está flotando en esta imagen."),
    "contrast": ("Este bloque cambia de color. ¿O no?", "Tus ojos te van a engañar. Mira el bloque del centro."),
}
MID_NEW = {
    "sync": ("Prepárate.", "Atento.", "Ya casi."),
    "ishihara": ("Mira bien.", "Sin trampas.", "Atento."),
    "magiceye": ("Paciencia.", "Relájate.", "Sin prisa."),
    "contrast": ("Míralo bien.", "¿Seguro?", "Atento."),
}
OUTRO_WORD = {"sync": "retos", "ishihara": "tests", "swarm": "retos", "magiceye": "retos",
              "contrast": "ilusiones"}
LABEL_ES = {"sync": "Prueba", "ishihara": "Test", "swarm": "Ronda", "magiceye": "Ojo mágico",
            "contrast": "Prueba"}


def _build_new(scene: Scene, tl: Timeline, rng) -> list:
    mode, n, S = scene.mode, len(scene.acts), tl.search_len
    segs = [Segment(0.25, rng.choice(HOOKS_NEW[mode]))]
    for a in scene.acts:
        s = tl.act_start(a.index)
        head = f"{LABEL_ES[mode]} {NUMS[a.index]}."
        countdown = Segment(s + max(5.10, S - 2.9), "Tres. Dos. Uno.")
        if mode == "sync":
            g = _g(scene.shape)
            digit = int(S - (a.hit - s)) + 1               # numero de la cuenta atras en el que encaja
            segs += [Segment(s + 0.30, f"{head} Pausa cuando {g['el']} {g['noun']} encaje."),
                     Segment(s + 3.90, rng.choice(MID_NEW[mode])), countdown,
                     Segment(s + S + 0.25, f"Encajó en el {NUMS[digit - 1]}. "
                             + ("¿Cuántas acertaste?" if a.index == n - 1 else "¿Pausaste a tiempo?"))]
        elif mode == "ishihara":
            g = _g(a.shape)
            what = "¿Qué número hay escondido?" if a.sym >= 0 else "¿Qué figura hay escondida?"
            answer = f"Era el {num_es(a.sym)}." if a.sym >= 0 else f"Era {g['el']} {g['noun']}."
            segs += [Segment(s + 0.30, f"{head} {what}"), Segment(s + 3.90, rng.choice(MID_NEW[mode])), countdown,
                     Segment(s + S + 0.25, f"{answer} ¿Lo viste?")]
        elif mode == "swarm":
            segs += [Segment(s + 0.30, f"{head} Sigue el punto rojo."),
                     Segment(s + 3.00, "Ahora es igual a todos."),
                     Segment(s + 5.00, "No lo pierdas."),
                     Segment(s + S - 1.25, "¿Dónde quedó?"),
                     Segment(s + S + 0.25, rng.choice(("Ahí estaba. ¿Lo seguiste?", "Ese era. ¿Acertaste?")))]
        elif mode == "magiceye":
            g = _g(a.shape)
            segs += [Segment(s + 0.30, f"{head} Desenfoca la vista y espera."),
                     Segment(s + 3.90, rng.choice(MID_NEW[mode])), countdown,
                     Segment(s + S + 0.25, f"Era {g['el']} {g['noun']}. ¿La viste en 3D?")]
        else:  # contrast
            segs += [Segment(s + 0.30, f"{head} ¿Cambia de color la figura del centro?"),
                     Segment(s + 3.90, rng.choice(MID_NEW[mode])), countdown,
                     Segment(s + S + 0.25, rng.choice(("Nunca cambió. Es el mismo color.", "Siempre fue el mismo color.")))]
    segs.append(Segment(tl.outro_start + 0.20, _outro(rng, OUTRO_WORD[mode])))
    return segs


def _outro(rng, plural_word: str) -> str:
    return rng.choice((f"Sigue {BRAND_SPOKEN} para más {plural_word}.", f"Más {plural_word} en {BRAND_SPOKEN}. Sígueme."))


def build_script(scene: Scene, tl: Timeline) -> list:
    rng = random.Random(scene.seed ^ 0x5EED)
    D = tl.spec.duration

    if scene.mode == "loop":
        segs = [Segment(0.3, rng.choice(LOOP_HOOKS))]
        fillers = rng.sample(LOOP_FILLERS, len(LOOP_FILLERS))
        for i, sec in enumerate(range(10, int(D) - 8, 10)):
            segs.append(Segment(sec - 1.0, f"Llevas {TENS[sec]} segundos mirando."))
            if sec + 4.5 < D - 8:
                segs.append(Segment(sec + 4.5, fillers[i % len(fillers)]))
        segs.append(Segment(D - 3.0, _outro(rng, "bucles")))
        return sorted(segs, key=lambda s: s.start)

    if scene.mode in HOOKS_NEW:
        return _build_new(scene, tl, rng)

    n = len(scene.acts)
    illusion = scene.mode == "illusion"
    g = _g(scene.shape)
    hooks = ILL_HOOKS if illusion else _anomaly_hooks(g, n)
    segs = [Segment(0.25, rng.choice(hooks).format(n=NUMS[n - 1].capitalize()))]
    label = "Ilusión" if illusion else "Reto"

    for a in scene.acts:
        s = tl.act_start(a.index)
        if illusion:
            instr_pool, mid_pool, rev_pool = ILL_TEXT[a.kind]
            instr, mid, reveal = rng.choice(instr_pool), rng.choice(mid_pool), rng.choice(rev_pool)
        else:
            instr = rng.choice(_anomaly_instr(ANOMALY_KINDS[a.kind], g))
            mid = rng.choice(MID)
            reveal = rng.choice(FINAL_REVEAL if a.index == n - 1 else REVEAL)
        segs += [
            Segment(s + 0.30, f"{label} {NUMS[a.index]}. {instr}"),
            Segment(s + 3.90, mid),
            Segment(s + max(5.10, tl.search_len - 2.9), "Tres. Dos. Uno."),
            Segment(s + tl.search_len + 0.25, reveal),
        ]
    segs.append(Segment(tl.outro_start + 0.20, _outro(rng, "ilusiones" if illusion else "retos")))
    return segs
