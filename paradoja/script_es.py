"""Guion de narracion: convierte la voz de cada acto (generada en acts.py) en segmentos con su instante."""
import random
from dataclasses import dataclass

from .scene import Scene
from .texts_es import num_es  # noqa: F401  (reexportado)
from .timeline import Timeline


@dataclass(frozen=True)
class Segment:
    start: float
    text: str


TENS = {10: "diez", 20: "veinte", 30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta"}
HOOK_AT = 0.15          # el gancho suena casi desde el primer fotograma
CTA_DELAY = 0.20        # la llamada a seguir suena justo al empezar el cierre
LOOP_FILLERS = ("Sigue mirando. No tiene final.", "Tu cerebro busca el inicio.", "Imposible apartar la vista.",
                "Quédate hasta el final.", "¿Ya encontraste dónde empieza?")


def build_script(scene: Scene, tl: Timeline) -> list:
    rng = random.Random(scene.seed ^ 0x5EED)
    D = tl.spec.duration

    if scene.mode == "loop":
        segs = [Segment(0.3, scene.hook)]
        fillers = rng.sample(LOOP_FILLERS, len(LOOP_FILLERS))
        for i, sec in enumerate(range(10, int(D) - 8, 10)):
            segs.append(Segment(sec - 1.0, f"Llevas {TENS[sec]} segundos mirando."))
            if sec + 4.5 < D - 8:
                segs.append(Segment(sec + 4.5, fillers[i % len(fillers)]))
        segs.append(Segment(D - scene.outro_len + CTA_DELAY, scene.cta))
        return sorted(segs, key=lambda s: s.start)

    segs = [Segment(HOOK_AT, scene.hook)] if scene.hook else []
    segs += [Segment(a.start + t, text) for a in scene.acts for t, text in a.voice]
    segs.append(Segment(tl.outro_start + CTA_DELAY, scene.cta))
    return segs
