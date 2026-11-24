"""Biblioteca de textos en español: numeros en palabras, gramatica de figuras y colores, frases por tipo de reto."""
from .scene import SHAPES

NUMS = ("uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho")
SPOKEN_LABEL = {
    "anomaly": "Reto", "illusion": "Ilusión", "ishihara": "Test", "magiceye": "Ojo mágico", "contrast": "Prueba",
    "sync": "Prueba", "swarm": "Ronda", "count": "Conteo", "flicker": "Cambio", "memory": "Memoria",
    "stroop": "Colores", "math": "Cálculo", "sequence": "Secuencia", "riddle": "Acertijo",
    "cups": "Vasos", "simon": "Simón", "digits": "Números",
}

_UNI = ("cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce",
        "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve")
_VEINTI = {20: "veinte", 21: "veintiuno", 22: "veintidós", 23: "veintitrés", 24: "veinticuatro", 25: "veinticinco",
           26: "veintiséis", 27: "veintisiete", 28: "veintiocho", 29: "veintinueve"}
_DEC = {3: "treinta", 4: "cuarenta", 5: "cincuenta", 6: "sesenta", 7: "setenta", 8: "ochenta", 9: "noventa"}
_CENT = {1: "ciento", 2: "doscientos", 3: "trescientos", 4: "cuatrocientos", 5: "quinientos", 6: "seiscientos",
         7: "setecientos", 8: "ochocientos", 9: "novecientos"}


def num_es(n: int) -> str:
    """Entero (hasta 999 999) en palabras, para que el TTS lo lea bien."""
    if n < 0:
        return "menos " + num_es(-n)
    if n < 20:
        return _UNI[n]
    if n < 30:
        return _VEINTI[n]
    if n < 100:
        t, u = divmod(n, 10)
        return _DEC[t] + (f" y {_UNI[u]}" if u else "")
    if n == 100:
        return "cien"
    if n < 1000:
        c, r = divmod(n, 100)
        return _CENT[c] + (f" {num_es(r)}" if r else "")
    k, r = divmod(n, 1000)
    return ("mil" if k == 1 else num_es(k) + " mil") + (f" {num_es(r)}" if r else "")


def g(shape: int) -> dict:
    """Gramatica de la figura: articulos, terminaciones y plural."""
    noun, fem = SHAPES[shape]
    return dict(noun=noun, pl=noun + "s", el="la" if fem else "el", los="las" if fem else "los",
                un="una" if fem else "un", Uno="Una" if fem else "Uno", o="a" if fem else "o", fem=fem)


# (masculino, femenino, tono HSV) para el reto de conteo
NAMED_COLORS = (("rojo", "roja", 0.0), ("naranja", "naranja", 0.07), ("amarillo", "amarilla", 0.15),
                ("verde", "verde", 0.33), ("celeste", "celeste", 0.5), ("azul", "azul", 0.62),
                ("morado", "morada", 0.76), ("rosa", "rosa", 0.90))


def adj_plural(adj: str) -> str:
    return adj + ("es" if adj[-1] in "lz" else "s")


# tinta del efecto Stroop: (nombre, BGR para ASS)
STROOP_COLORS = (("rojo", "2020FF"), ("verde", "30E050"), ("azul", "FF6A20"), ("amarillo", "00E6FF"),
                 ("naranja", "0080FF"), ("morado", "FF3399"), ("rosa", "9933FF"), ("celeste", "FFD500"))

HOOK_SHORT = ("Tiene truco.", "Piénsalo bien.", "Atento.", "¿Estás listo?", "Mira bien.")
MID = ("Mira bien.", "No parpadees.", "Concéntrate.", "Sin trampas.")
REVEAL = ("Ahí estaba. ¿Lo viste?", "Ese era. ¿Acertaste?", "Mira dónde estaba. ¿Lo encontraste?")

# cierre hablado (<= 7 palabras): una pregunta sobre el propio reto, sin pedir comentar ni compartir (ver subtitles.py)
OUTRO = ("¿Cuántos acertaste?", "¿Cuántos sacaste?", "Hasta aquí el reto de hoy.")
LOOP_OUTRO = ("¿Cuántas veces lo repetiste?", "¿Cuántas veces lo viste?")

# Gancho en pantalla durante el primer segundo (el primer fotograma decide si el usuario se queda; los Reels suelen
# verse sin sonido al principio). {N} = numero de retos. Se elige segun la categoria del primer reto.
HOOK_TEXT = {
    "Visual": ("¿LO ENCUENTRAS?", "¿TIENES VISTA DE ÁGUILA?", "TU CEREBRO TE VA A ENGAÑAR", "{N} RETOS · ¿CUÁNTOS ACIERTAS?"),
    "Reflejos": ("¿TUS REFLEJOS SON REALES?", "UN SOLO FOTOGRAMA PARA ACERTAR", "{N} RETOS · ¿CUÁNTOS ACIERTAS?"),
    "Atención": ("NO PIERDAS LA CUENTA", "¿PUEDES SEGUIRLO?", "{N} RETOS · ¿CUÁNTOS ACIERTAS?"),
    "Memoria": ("¿TIENES BUENA MEMORIA?", "NO PARPADEES", "{N} RETOS · ¿CUÁNTOS ACIERTAS?"),
    "Mente": ("¿ERES MÁS LISTO QUE ESTE RETO?", "EL PRIMERO YA TIENE TRUCO", "{N} RETOS · ¿CUÁNTOS ACIERTAS?"),
}


# --------------------------------------------------------------------------- anomalia
def anomaly_instr(kind: int, gr: dict) -> tuple:
    n, el, o = gr["noun"], gr["el"], gr["o"]
    return (
        (f"Encuentra {el} {n} de otro color.", f"{gr['Uno']} tiene otro color. Encuéntral{o}."),
        (f"Encuentra {el} {n} más pequeñ{o}.", f"{gr['Uno']} es más pequeñ{o} que los demás."),
        (f"Encuentra {el} {n} más brillante.", f"{gr['Uno']} brilla más que el resto."),
        ("Encuentra el punto fuera de lugar.", f"{gr['Uno']} tiene el punto descentrado."),
        (f"Encuentra {el} {n} que está girad{o}.", f"{gr['Uno']} está girad{o}. Encuéntral{o}."),
    )[kind]


ANOMALY_DESC = ("de otro color", "más pequeño", "más brillante", "con el punto descentrado", "girado")

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
    6: (("¿Ves puntos grises entre los cuadrados?", "¿Ves puntitos grises en los cruces?"),
        ("Mira un cruce.", "Mira bien."),
        ("No hay puntos grises. Es una ilusión.", "Todos los cruces son blancos.")),
    7: (("¿Cuál línea es más larga?", "¿Cuál es más larga, la de arriba o la de abajo?"),
        ("Decide ya.", "Elige rápido."),
        ("Son iguales. Miden lo mismo.", "Exactamente iguales. Tu cerebro te engañó.")),
    8: (("¿Ves un triángulo blanco en el centro?", "¿Ves un triángulo entre los círculos?"),
        ("Míralo bien.", "¿Seguro?"),
        ("No hay triángulo. Tu cerebro lo inventó.", "Nunca hubo triángulo.")),
    9: (("¿Las líneas largas son paralelas?", "¿Estas líneas están inclinadas?"),
        ("¿Paralelas?", "Mira bien."),
        ("Son totalmente paralelas.", "Todas son paralelas. Tu cerebro te engañó.")),
}
ILL_NAME = ("ilusión de Ouchi", "ilusión del Café Wall", "ilusión de Ebbinghaus", "rejilla centelleante",
            "espiral hipnótica", "efecto muaré", "rejilla de Hermann", "ilusión de Müller-Lyer", "triángulo de Kanizsa",
            "ilusión de Zöllner")
ILL_ASK = ("¿Viste moverse el círculo del centro?", "¿Te parecieron torcidas las líneas?",
           "¿Cuál círculo del centro viste más grande: el izquierdo o el derecho?",
           "¿Cuántos puntos negros alcanzaste a ver?", "Después de mirarla, ¿se movió tu mano?",
           "¿Cuántas capas viste moverse?", "¿Viste puntos grises en los cruces?",
           "¿Cuál de las dos líneas viste más larga?", "¿Viste un triángulo blanco en el centro?",
           "¿Te parecieron paralelas las líneas largas?")

# --------------------------------------------------------------------------- otros tipos
SYNC_MID = ("Prepárate.", "Atento.", "Ya casi.")
ISHI_MID = ("Mira bien.", "Sin trampas.", "Atento.")
MAGIC_MID = ("Paciencia.", "Relájate.", "Sin prisa.")
CONTRAST_MID = ("Míralo bien.", "¿Seguro?", "Atento.")
COUNT_MID = ("Cuenta bien.", "Atento.", "Sin trampas.")
FLICKER_MID = ("Mira bien.", "Algo cambia.", "Atento.")
DIGITS_MID = ("Mira bien.", "Casi iguales.", "Atento.")
CUPS_MID = ("Más rápido.", "No la pierdas.", "Atento.")
ORDINALS = ("primero", "segundo", "tercero", "cuarto", "quinto", "sexto")

KIND_REVEAL = ("Cambió de color.", "Cambió de tamaño.", "Cambió de brillo.", "Se movió el punto.", "Giró.",
               "Desapareció una figura.")
KIND_REVEAL_FIGURE = "Esa figura cambió."
