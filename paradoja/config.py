"""Constantes globales del proyecto Paradoja Infinita."""
from dataclasses import dataclass

BRAND = "PARADOJA INFINITA"
BRAND_SPOKEN = "Paradoja Infinita"

SWARM_MAX = 40         # particulas maximas del enjambre (debe coincidir con NMAX del shader)
REVEAL_LEN = 3.0        # segundos de revelacion al final de cada acto
SUB_BAND = (890, 1030)  # franja vertical (px) que tapan los subtitulos: el objetivo nunca cae ahi

# (columnas, filas, tamaño de celda en px). cols*cell (+0.5 celda en modo hexagonal) <= 1080
LAYOUTS = ((5, 7, 192), (6, 8, 160), (7, 9, 144), (9, 12, 112))


@dataclass(frozen=True)
class VideoSpec:
    width: int = 1080
    height: int = 1920
    fps: int = 60
    duration: float = 63.0  # monetizacion In-Stream: 61-65 s

    def __post_init__(self):
        if not 61.5 <= self.duration <= 65.0:
            raise ValueError("duration debe estar entre 61.5 y 65 s")

    @property
    def frames(self) -> int:
        return round(self.duration * self.fps)
