"""Constantes globales del proyecto Paradoja Infinita."""
from dataclasses import dataclass

BRAND = "PARADOJA INFINITA"
BRAND_SPOKEN = "Paradoja Infinita"

SWARM_MAX = 40         # particulas maximas del enjambre (debe coincidir con NMAX del shader)
REVEAL_LEN = 3.0        # segundos de revelacion al final de cada acto
SUB_BAND = (890, 1030)  # franja vertical (px) que tapan los subtitulos: el objetivo nunca cae ahi
# Zona segura de Reels (estimada: ~14 % superior y ~35 % inferior los tapa la interfaz de la app; no hay cifra oficial
# para Facebook, comprobar en el movil). Texto de pantalla por debajo de TOP_SAFE; las respuestas, entre ambos limites.
TOP_SAFE = 270
BOTTOM_SAFE = 1248
HUD_Y = 306             # fila de etiqueta del reto (izquierda) y cuenta atras (derecha)
CAPTION_Y = 430         # pregunta fija / gancho del primer segundo
# Las respuestas no pueden quedar bajo la pregunta fija ni bajo la zona de la app: ANSWER_TOP es el borde superior
# del area de respuestas (px). SAFE_Y / COUNT_TOP_Y: lo mismo en coordenadas del shader (px = 960 + y * 1080).
ANSWER_TOP = CAPTION_Y + 40
SAFE_Y = ((CAPTION_Y + 90) - 960) / 1080, ((BOTTOM_SAFE - 20) - 960) / 1080
COUNT_TOP_Y = ((CAPTION_Y + 180) - 960) / 1080        # las figuras contadas llevan su numero encima

# (columnas, filas, tamaño de celda en px). cols*cell (+0.5 celda en modo hexagonal) <= 1080
LAYOUTS = ((5, 7, 192), (6, 8, 160), (7, 9, 144), (9, 12, 112))
# rejillas pequeñas para los retos de memoria (pocas figuras que recordar)
MEMORY_LAYOUTS = ((4, 5, 208), (3, 5, 224), (3, 5, 240))


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
