"""Nombre de archivo descriptivo + borrador de publicacion (.txt) para cada video."""
import hashlib
import random
import unicodedata
from pathlib import Path

from . import copy_es
from . import texts_es as T
from .scene import SHAPES, TYPES, Scene
from .timeline import Timeline

LOOP_KINDS = (("poligonos", "zoom de polígonos sin fin"), ("anillos", "anillos de figuras orbitando"),
              ("ondas", "ondas hipnóticas"))
MODE_LABEL = {
    "anomaly": "Reto de Anomalía", "illusion": "Ilusión Óptica", "ishihara": "Test de Visión (Ishihara)",
    "magiceye": "Ojo Mágico (Autoestereograma)", "contrast": "Ilusión de Contraste", "sync": "Reto de Sincronización (Pausa)",
    "swarm": "Seguimiento de Enjambre", "count": "Reto de Conteo", "flicker": "¿Qué Cambió? (Detección de cambio)",
    "memory": "Reto de Memoria", "stroop": "Efecto Stroop", "math": "Cálculo con Trampa", "sequence": "Secuencia Numérica",
    "riddle": "Acertijos", "loop": "Bucle", "mix": "Video Mixto (varios retos)",
    "cups": "Vasos (¿Dónde está la bola?)", "simon": "Simón (Memoria de secuencia)", "digits": "Número Distinto",
}
MODE_SLUG = {
    "anomaly": "anomalia", "illusion": "ilusion", "ishihara": "ishihara", "magiceye": "ojomagico", "contrast": "contraste",
    "sync": "sincronia", "swarm": "enjambre", "count": "conteo", "flicker": "cambio", "memory": "memoria",
    "stroop": "stroop", "math": "calculo", "sequence": "secuencia", "riddle": "acertijo", "loop": "bucle", "mix": "mixto",
    "cups": "vasos", "simon": "simon", "digits": "numerodistinto",
}


def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().replace(" ", "")


def video_slug(sc: Scene) -> str:
    """anomalia_estrella_<semilla> | calculo_..._<semilla> | mixto_calculo-conteo-memoria_<semilla> ..."""
    a0 = sc.acts[0] if sc.acts else None
    if sc.mode == "loop":
        detail = LOOP_KINDS[sc.loop_kind][0]
    elif sc.mode == "mix":
        detail = "-".join(MODE_SLUG[a.type] for a in sc.acts[:3])
    elif sc.mode == "illusion":
        detail = ("ouchi", "cafewall", "ebbinghaus", "rejilla", "espiral", "muare", "hermann", "mullerlyer", "kanizsa", "zollner")[a0.kind]
    elif sc.mode == "ishihara":
        detail = str(a0.sym) if a0.sym >= 0 else _ascii(SHAPES[a0.shape][0])
    elif sc.mode == "magiceye":
        detail = str(a0.sym) if a0.sym >= 0 else _ascii(SHAPES[a0.shape][0])
    elif sc.mode == "count":
        detail = _ascii(SHAPES[int(a0.q[0])][0]) if a0.q[0] >= 0 else "colores"
    elif sc.mode == "math":
        detail = "operaciones"
    elif sc.mode == "sequence":
        detail = "numeros"
    elif sc.mode == "stroop":
        detail = "colores"
    elif sc.mode == "riddle":
        detail = "preguntas"
    elif sc.mode == "cups":
        detail = "bola"
    elif sc.mode == "simon":
        detail = "colores"
    elif sc.mode == "digits":
        detail = f"{a0.sym}y{a0.shape}"
    else:  # anomaly, sync, swarm, contrast, flicker, memory
        detail = _ascii(SHAPES[sc.shape][0])
    return f"{MODE_SLUG[sc.mode]}_{detail}_{sc.seed}"


class _Pick:
    """Como random.Random pero evita repetir titulos usados recientemente."""

    def __init__(self, rng, avoid):
        self.rng, self.avoid = rng, set(avoid)

    def choice(self, seq):
        return self.rng.choice(seq)

    def title(self, options):
        fresh = [o for o in options if o not in self.avoid]
        return self.rng.choice(fresh or list(options))


def _answers_text(sc) -> str:
    return "; ".join(f"{a.index + 1}) {a.answer}" for a in sc.acts)


# ----------------------------------------------------------------------------- textos por tipo
# cada funcion devuelve (titulos, descripciones, lineas extra de VARIABLES)
def _anomaly(sc, tl):
    g, n = T.g(sc.shape), len(sc.acts)
    titles = (f"¿Puedes encontrar {g['el']} {g['noun']} diferente? Solo el 1% lo logra",
              f"Reto visual: {n} retos y {g['un']} {g['noun']} distinto escondido",
              f"Tu cerebro no es tan rápido como crees: encuentra {g['el']} {g['noun']} que no encaja",
              f"{n} retos, 1 {g['noun']} diferente en cada uno. ¿Cuántos aciertas?")
    descs = (f"Hay {g['un']} {g['noun']} distinto escondido en cada reto, y cada vez es más difícil. 🔍\n\n"
             f"👇 Comenta en qué segundo lo notaste en el último reto. ¿Llegaste a ver los {n}?\n\n"
             "Si lo lograste sin pausar, eres de los pocos. Sígueme para más retos visuales.",
             f"Mira bien: entre decenas de figuras hay {g['un']} {g['noun']} que no es igual a las demás.\n\n"
             "👇 Escribe en qué segundo lo encontraste. ¡El último reto es casi imposible!\n\n"
             "Etiqueta a alguien que crea que tiene mejor vista que tú.",
             f"{n} retos. {g['el'].capitalize()} {g['noun']} diferente se esconde cada vez mejor. 👀\n\n"
             "👇 Cuéntame en los comentarios: ¿en qué segundo lo notaste? ¿Cuántos retos acertaste?")
    return titles, descs, [f"Figura: {g['noun'].capitalize()}"]


def _illusion(sc, tl):
    n = len(sc.acts)
    names = [T.ILL_NAME[a.kind] for a in sc.acts]
    first, listing = names[0], ", ".join(names)
    ask = T.ILL_ASK[sc.acts[0].kind]
    titles = (f"Tu cerebro te miente: {first} y {n - 1} ilusiones más",
              f"{n} ilusiones ópticas que engañan a casi todos. ¿Y a ti?",
              f"Lo que ves no es real: {first}",
              f"¿Caes en las {n} ilusiones? Empieza con la {first}")
    descs = (f"Cada ilusión usa un truco distinto de tu cerebro: {listing}. 🧠\n\n"
             f"👇 {ask} Cuéntame en los comentarios cuántas de las {n} te engañaron.",
             f"Mira con calma: nada de esto es lo que parece ({listing}).\n\n"
             f"👇 Pregunta rápida: {ask} ¿Y cuántas ilusiones viste funcionar, de 0 a {n}?",
             f"Tu cerebro rellena huecos... y se equivoca. 👁️ Hoy: {listing}.\n\n"
             f"👇 {ask} Escribe tu resultado (0 a {n}).")
    return titles, descs, ["Preguntas por ilusión: " + " | ".join(f"{i + 1}) {T.ILL_ASK[a.kind]}" for i, a in enumerate(sc.acts))]


def _sync(sc, tl):
    g, n = T.g(sc.shape), len(sc.acts)
    titles = (f"¿Puedes pausar justo cuando {g['el']} {g['noun']} encaja? Solo tienes 1 fotograma",
              f"Reto de reflejos: pausa en el instante exacto ({n} intentos)",
              f"El 99% falla: pausa cuando {g['el']} {g['noun']} encaje en la silueta",
              f"{n} pruebas, 1 fotograma para acertar. ¿Cuántas logras?")
    descs = (f"{g['el'].capitalize()} {g['noun']} gira a velocidad extrema y solo encaja UN fotograma por prueba. ⏸️\n\n"
             f"👇 Pausa el video y comenta en qué número del contador (5, 4, 3, 2 o 1) lo hiciste en la última prueba. ¿Acertaste las {n}?",
             f"Pon a prueba tus reflejos: pausa justo cuando {g['el']} {g['noun']} coincida con la silueta. Cada prueba es más rápida. ⚡\n\n"
             f"👇 Comenta cuántas de las {n} pruebas lograste y reta a un amigo a superarte.",
             f"Un solo fotograma. Una sola oportunidad. ⏱️\n\n"
             f"👇 Escribe en qué prueba fallaste primero (1 a {n}) y etiqueta a quien tenga mejores reflejos.")
    return titles, descs, [f"Figura: {g['noun'].capitalize()}"]


def _ishihara(sc, tl):
    n = len(sc.acts)
    nums = sum(a.sym >= 0 for a in sc.acts)
    what = "números" if nums == n else "figuras" if nums == 0 else "números y figuras"
    note = "(Es solo un juego, no un test médico.)"
    titles = (f"Test de visión: ¿qué {what} escondí? Solo 1 de cada 10 los ve",
              f"¿Ves lo que hay escondido? {n} tests, cada uno más difícil",
              f"Entrecierra los ojos: {n} tests con {what} escondidos entre los puntos",
              f"Reto visual: ¿cuántos de los {n} tests logras ver?")
    descs = (f"Hay {what} escondidos entre los puntos y cada test es más difícil. 👀\n\n"
             f"👇 Escribe lo que viste en cada test (1, 2, 3...). Si no ves nada, comenta NO VEO.\n\n{note}",
             f"Tu cerebro busca patrones en el caos. ¿Puedes encontrarlos? 🧠\n\n"
             f"👇 Comenta cuántos de los {n} tests lograste ver y cuál fue el más difícil.\n\n{note}",
             f"Aleja el teléfono, entrecierra los ojos y mira bien. {n} tests con {what} escondidos. 🔍\n\n"
             f"👇 ¿Qué viste en el último? Escríbelo antes de ver la respuesta.\n\n{note}")
    return titles, descs, []


def _swarm(sc, tl):
    g, n = T.g(sc.shape), len(sc.acts)
    titles = ("Sigue el punto rojo: solo los mejores no lo pierden",
              f"¿Dónde quedó el punto rojo? {n} retos de atención",
              "Tu atención contra el caos: no pierdas de vista el punto rojo",
              f"Reto de seguimiento: {n} rondas y cada vez más rápido")
    descs = (f"Un {g['noun']} rojo se mezcla con decenas más... y todos se detienen. ¿Sabes cuál era? 🔴\n\n"
             "👇 Comenta en qué parte quedó en el último reto: ARRIBA, ABAJO, IZQUIERDA o DERECHA.",
             "No parpadees. El punto rojo desaparece entre el caos y cada ronda hay más figuras. 👁️\n\n"
             f"👇 Escribe cuántas rondas acertaste (0 a {n}) y etiqueta a alguien con buena vista.",
             f"{n} rondas, un solo objetivo. Sigue el punto rojo con los ojos. 🎯\n\n"
             "👇 ¿En qué ronda lo perdiste? Cuéntamelo en los comentarios.")
    return titles, descs, [f"Figura de las partículas: {g['noun'].capitalize()}"]


def _magiceye(sc, tl):
    n = len(sc.acts)
    titles = ("Ojo mágico: ¿qué figura en 3D está escondida?",
              f"Desenfoca la vista: {n} figuras 3D escondidas en el ruido",
              "Solo 1 de cada 5 ve la figura 3D. ¿Y tú?",
              f"Reto de ojo mágico: ¿cuántas de las {n} figuras logras ver?")
    descs = ("Relaja la vista, mira a través de la pantalla y espera: una figura 3D flota en el ruido. 👁️\n\n"
             "👇 Escribe qué figura viste en cada prueba. ¿No ves nada? Comenta NO VEO y te cuento el truco.",
             f"Mira a través de la imagen, como si enfocaras algo detrás de la pantalla. {n} pruebas. 🧠\n\n"
             "👇 Comenta qué figura viste en la última y cuánto tardaste en verla.",
             f"No es ruido: hay una figura escondida. Desenfoca y espera unos segundos. ✨\n\n"
             f"👇 Dime qué figura apareció (1 a {n}) y comparte con quien tenga paciencia.")
    return titles, descs, ["Truco: mirar 'a través' de la pantalla hasta que los dos puntos de arriba se fusionen y aparezcan tres"]


def _contrast(sc, tl):
    n = len(sc.acts)
    titles = ("Ilusión de contraste: ¿cuál es más claro? Tus ojos mienten",
              f"{n} pruebas de color: ¿cambia o no cambia?",
              "Mira el bloque: ¿qué color tiene realmente?",
              "Solo cambia el fondo... ¿o también la figura?")
    descs = ("El fondo cambia y tu cerebro jura que la figura también. 🎨\n\n"
             "👇 Vota en los comentarios antes de ver cada respuesta. ¿Cuántas pruebas te engañaron?",
             "Dos bloques, un truco del cerebro. ¿Cuál es más claro? 🧠\n\n"
             f"👇 Comenta cuántas de las {n} pruebas acertaste (0 a {n}).",
             "Mira con atención y decide. La respuesta llega al final de cada prueba. 👁️\n\n"
             "👇 Escribe tu respuesta y etiqueta a alguien que crea que no se deja engañar.")
    return titles, descs, []


def _count(sc, tl):
    n, q = len(sc.acts), sc.acts[0].question
    titles = (f"{q} Cuenta bien: {n} rondas",
              f"Reto de conteo: {n} rondas, cada vez más figuras",
              f"¿Cuántas figuras puedes contar sin perderte? {n} retos",
              f"{q} Dime tu número en los comentarios")
    descs = ("Las figuras se mueven y en cada ronda hay más. ¿Sabes contarlas sin perder la cuenta? 🔢\n\n"
             "👇 Comenta tu número de la última ronda. ¡Gana quien acierte!",
             f"{n} rondas de conteo. Cada una más difícil que la anterior. 👀\n\n"
             "👇 Escribe cuántas había en la ronda 3 y etiqueta a alguien con buena vista.",
             "Cuenta en silencio y no te distraigas. 🧠\n\n"
             f"👇 ¿Cuántas rondas acertaste, de 0 a {n}? Cuéntamelo.")
    return titles, descs, []


def _flicker(sc, tl):
    n = len(sc.acts)
    titles = (f"¿Qué cambia entre las dos imágenes? {n} retos",
              "Solo el 5% ve el cambio a la primera. ¿Y tú?",
              f"Detecta el cambio: {n} pruebas de atención",
              "Una figura cambia en cada reto. ¿La ves?")
    descs = ("Una imagen parpadea y algo cambia en ella. ¿Puedes verlo? 👀\n\n"
             "👇 Comenta en qué fila y columna estaba el cambio en el último reto.",
             f"{n} retos de atención. En cada uno, una sola figura cambia. 🔍\n\n"
             "👇 Escribe cuántos cambios encontraste antes de la respuesta (0 a " + str(n) + ").",
             "Tu cerebro ignora lo que no espera. ¿Qué cambió? 🧠\n\n"
             "👇 Dime qué cambió en el último reto: color, tamaño, giro o desapareció.")
    return titles, descs, []


def _memory(sc, tl):
    n = len(sc.acts)
    titles = (f"Test de memoria: memoriza las figuras y encuentra el cambio ({n} rondas)",
              "¿Qué figura cambió? Pon a prueba tu memoria visual",
              f"{n} rondas, 3 segundos para memorizar. ¿Cuántas aciertas?",
              "Memoriza, parpadea y encuentra la diferencia")
    descs = ("Tienes 3 segundos para memorizar. Luego la pantalla se apaga y algo cambia. 🧠\n\n"
             "👇 Comenta qué figura cambió en la última ronda (fila y columna).",
             f"{n} rondas de memoria visual. Cada una con más cosas que recordar. 👀\n\n"
             f"👇 ¿Cuántas rondas acertaste, de 0 a {n}? Cuéntamelo.",
             "Tu memoria te engaña más de lo que crees. ¿Qué cambió? 🔍\n\n"
             "👇 Escribe tu respuesta antes de ver la solución.")
    return titles, descs, []


def _stroop(sc, tl):
    n = len(sc.acts)
    titles = ("Efecto Stroop: di el color de la tinta, no la palabra",
              f"{n} rondas que confunden a tu cerebro: ¿cuántas fallas?",
              "Lee el color, no la palabra. Casi nadie lo logra sin fallar",
              "Test Stroop: tu cerebro contra tus ojos")
    descs = ("Di en voz alta el COLOR de la tinta, no lo que dice la palabra. 🎨\n\n"
             "👇 Comenta cuántas palabras fallaste en la última ronda.",
             f"{n} rondas de palabras de colores que no coinciden con su tinta. 🧠\n\n"
             f"👇 Escribe cuántas rondas hiciste sin equivocarte (0 a {n}).",
             "Tu cerebro lee más rápido de lo que ve. ¿Podrás ignorar la palabra? 👀\n\n"
             "👇 Cuéntame tu puntaje y reta a alguien a superarlo.")
    return titles, descs, []


def _math(sc, tl):
    n, q = len(sc.acts), sc.acts[0].question
    titles = (f"{q} Solo 1 de cada 10 acierta",
              f"Reto de cálculo: {n} operaciones con trampa. ¿Cuántas aciertas?",
              "El orden de las operaciones engaña a casi todos. ¿Y a ti?",
              f"{q} Sin calculadora")
    descs = ("Operaciones con trampa. El orden importa. 🔢\n\n"
             "👇 Comenta tu resultado de la última operación SIN calculadora. ¡Gana quien acierte!",
             f"{n} operaciones. En cada una hay un resultado «obvio» que es incorrecto. 🧠\n\n"
             f"👇 Escribe cuántas acertaste (0 a {n}) y qué resultado diste en la primera.",
             "Muchos se equivocan por hacer las cuentas de izquierda a derecha. 😅\n\n"
             "👇 ¿Cuál fue tu respuesta? Cuéntamelo en los comentarios.")
    return titles, descs, []


def _sequence(sc, tl):
    n, q = len(sc.acts), sc.acts[0].question
    titles = (f"{q}", f"{n} secuencias numéricas: ¿cuántas adivinas?",
              "Test de lógica: ¿qué número sigue? Solo 1 de cada 5 acierta",
              "¿Ves el patrón? Completa la secuencia")
    descs = ("Cada secuencia sigue una regla distinta. ¿Puedes encontrarla? 🧩\n\n"
             "👇 Comenta qué número sigue en la última secuencia.",
             f"{n} secuencias, cada vez más difíciles. 🧠\n\n"
             f"👇 Escribe cuántas lograste resolver (0 a {n}) y cuál te costó más.",
             "Los números esconden un patrón. ¿Lo ves antes de que acabe el tiempo? ⏱️\n\n"
             "👇 Dime tu respuesta de la secuencia 3 y etiqueta a quien sea bueno en lógica.")
    return titles, descs, []


def _riddle(sc, tl):
    """El primer acertijo va en el titulo y se pide la respuesta: es lo que mas comentarios genera."""
    n, q = len(sc.acts), sc.acts[0].question
    short = q if len(q) <= 70 else f"{q[:66].rsplit(' ', 1)[0]}..."
    titles = (short, f"Acertijo: {short}", f"{short} (la respuesta, al final)",
              f"{n} acertijos y preguntas trampa: ¿cuántos aciertas?", "Solo 1 de cada 10 resuelve estos acertijos a la primera")
    descs = (f"Empezamos con este: «{short}» 🧩\n\n"
             "👇 Escribe tu respuesta ANTES de ver la solución y cuéntame si acertaste.",
             f"{n} acertijos. Algunos son más fáciles de lo que parecen. 😏\n\n"
             f"👇 Escribe cuántos acertaste (0 a {n}) y cuál te sorprendió.",
             "Tu primera respuesta suele ser la equivocada. 🤔\n\n"
             f"👇 ¿Qué respondiste a «{short}»? Cuéntamelo en los comentarios.",
             "Piensa antes de responder: algunos son preguntas trampa. 🧠\n\n"
             "👇 Comenta tu respuesta al último acertijo (sin hacer trampa).")
    return titles, descs, ["Acertijos: " + " | ".join(f"{a.index + 1}) {a.question} -> {a.answer}" for a in sc.acts)]


def _cups(sc, tl):
    n = len(sc.acts)
    titles = (f"¿En qué vaso está la bola? {n} rondas, cada vez más rápido",
              "El juego de los vasos: ¿puedes seguir la bola hasta el final?",
              f"Sigue la bola sin parpadear: ¿cuántas de {n} aciertas?",
              "Tus ojos contra los vasos. Casi nadie llega a la última ronda")
    descs = (f"{n} rondas del juego de los vasos y cada una es más rápida. 🥤\n\n"
             "👇 Escribe 1, 2 o 3 en los comentarios ANTES de que termine cada ronda y mira si acertaste.",
             "Sigue la bola con los ojos, sin pausar. Al final de cada ronda se levanta el vaso. 👀\n\n"
             f"👇 Cuéntame: ¿cuántas de las {n} rondas acertaste?",
             "Tu cerebro cree que sigue la bola... y se pierde. 🧠\n\n"
             "👇 Comenta en qué ronda la perdiste por primera vez.")
    return titles, descs, ["Rondas: " + "; ".join(f"{a.index + 1}) {a.answer}" for a in sc.acts)]


def _simon(sc, tl):
    n = len(sc.acts)
    titles = (f"Test de memoria: recuerda el orden de {n} secuencias de luces",
              "¿Recuerdas el orden? Memoria tipo Simón",
              f"Mira, memoriza y responde: ¿cuántas de {n} secuencias aciertas?",
              "Solo el 1% recuerda la última secuencia. ¿Y tú?")
    descs = (f"{n} secuencias de luces, cada vez más largas. Memoriza el orden y responde. 🔴🟢🔵🟡\n\n"
             f"👇 Comenta cuántas de las {n} acertaste (0 a {n}). ¿Hasta qué secuencia llegaste?",
             "Mira cómo se iluminan los pads y memoriza el orden. La pregunta llega al final. 🧠\n\n"
             "👇 Escribe tu respuesta a la última secuencia antes de ver la solución.",
             "Tu memoria de trabajo, al límite. ⏱️\n\n"
             f"👇 ¿Cuántas acertaste de {n}? Etiqueta a quien tenga mejor memoria.")
    return titles, descs, ["Secuencias: " + "; ".join(f"{a.index + 1}) {a.answer}" for a in sc.acts)]


def _digits(sc, tl):
    n = len(sc.acts)
    titles = (f"¿Encuentras el número distinto? {n} retos, cada vez más parecidos",
              "Todos son iguales menos uno: encuéntralo antes de que acabe el tiempo",
              f"Test de vista: {n} números escondidos entre dígitos casi idénticos",
              "Solo el 1% encuentra el último número distinto")
    descs = (f"En cada reto hay UN número distinto entre muchos casi iguales, y cada vez se parecen más. 🔢\n\n"
             f"👇 Comenta en qué segundo lo encontraste en el último reto. ¿Cuántos de {n} acertaste?",
             "Mira bien: parecen todos iguales, pero uno es diferente. 👀\n\n"
             "👇 Escribe el número que encontraste en el último reto.",
             f"{n} retos de vista de águila. 🦅\n\n"
             "👇 Dime tu puntaje (0 a " + str(n) + ") y etiqueta a alguien que tenga mejor vista que tú.")
    return titles, descs, ["Respuestas: " + _answers_text(sc)]


def _loop(sc, tl):
    g = T.g(sc.shape)
    kind = LOOP_KINDS[sc.loop_kind][1]
    if sc.loop_kind == 1:
        kind = f"anillos de {g['pl']} orbitando"
    P, D = sc.loop_period, tl.spec.duration
    titles = ("Este bucle no tiene principio ni final. ¿Dónde empieza?",
              f"Bucle infinito: {kind}. Imposible dejar de mirar",
              "Intenta encontrar el momento exacto donde se repite",
              "Mira fijamente: este video nunca termina")
    descs = (f"Un bucle perfecto de {kind}. Se repite cada {P:.0f} segundos y el final conecta con el inicio sin saltos. ♾️\n\n"
             "👇 Comenta cuántas veces lo repetiste antes de darte cuenta.",
             f"¿Puedes ver dónde empieza y dónde termina? Casi nadie lo logra. ({kind})\n\n"
             "👇 Dime cuántas veces seguidas lo viste. Sé honesto. 😅",
             f"Mira esto una vez... y verás cómo se repite solo. Son {D:.0f} segundos de {kind} sin cortes.\n\n"
             "👇 ¿Cuántas veces lo repetiste? Escribe el número.")
    extra = [f"Tipo de bucle: {kind}", f"Periodo: {P:.1f}s ({sc.loop_k} vueltas por video)"]
    return titles, descs, extra


def _mix(sc, tl):
    n = len(sc.acts)
    names = [TYPES[a.type].menu.lower() for a in sc.acts]
    listing = ", ".join(names)
    titles = (f"{n} mini-retos en 1 video: ¿cuántos aciertas?",
              f"Test de cerebro: {n} pruebas rápidas, {n} trucos distintos",
              f"Mira bien: {names[0]}, {names[1]} y {n - 2} retos más",
              f"¿Cuántos de estos {n} retos logras resolver?")
    descs = (f"{n} retos distintos en un solo video: {listing}. 🧠\n\n"
             f"👇 Comenta tu puntaje de 0 a {n} y cuál fue el más difícil.",
             f"Hoy: {listing}. Cada reto es diferente y la respuesta llega al final de cada uno. 👀\n\n"
             f"👇 ¿Cuántos acertaste? Escríbelo y reta a un amigo a superarte.",
             f"Un reto nuevo cada pocos segundos. Sin trampas. ⏱️\n\n"
             f"👇 Dime tu puntaje (0 a {n}) y etiqueta a quien crea que sacaría más.")
    extra = ["Retos: " + "; ".join(f"{a.index + 1}) {TYPES[a.type].menu}" for a in sc.acts)]
    return titles, descs, extra


_BUILDERS = {"anomaly": _anomaly, "illusion": _illusion, "sync": _sync, "ishihara": _ishihara, "swarm": _swarm,
             "magiceye": _magiceye, "contrast": _contrast, "count": _count, "flicker": _flicker, "memory": _memory,
             "stroop": _stroop, "math": _math, "sequence": _sequence, "riddle": _riddle, "loop": _loop, "mix": _mix,
             "cups": _cups, "simon": _simon, "digits": _digits}


# --------------------------------------------------------------------------- texto de publicacion
# Guia de Meta para subtitulos: sin enlaces, pocas mayusculas y no mas de cinco hashtags. Los pies de compartir/seguir
# y la frase de busqueda rotan para que dos publicaciones del mismo tipo no lleven el mismo texto.
SEO = {
    "anomaly": ("Reto visual para entrenar la atención: encuentra la diferencia.",
                "Test de vista y atención con la respuesta al final de cada reto."),
    "illusion": ("Ilusiones ópticas que engañan al cerebro, con la explicación al final.",
                 "Trucos visuales para ver cómo te engaña tu propia mente."),
    "ishihara": ("Test de visión para jugar con amigos (es un juego, no sustituye un examen médico).",
                 "Prueba de vista y colores: ¿qué ves? Es un juego, no un diagnóstico."),
    "magiceye": ("Ojo mágico: imágenes 3D ocultas (autoestereogramas) para ver sin gafas.",
                 "Imagen 3D escondida: enfoca la vista y espera a que aparezca."),
    "contrast": ("Ilusión de contraste: lo que ves no siempre es lo que es.",
                 "Ilusiones ópticas de color y brillo que engañan a tus ojos."),
    "sync": ("Reto de reflejos: pausa el video justo en el instante exacto.",
             "Test de reflejos y tiempo de reacción en cada prueba."),
    "swarm": ("Reto de atención: sigue el punto rojo entre muchas figuras en movimiento.",
              "Test de seguimiento visual con la respuesta al final."),
    "count": ("Reto de conteo: cuenta bien las figuras sin perder la atención.",
              "Test de atención y concentración contando figuras."),
    "flicker": ("¿Qué cambia? Test de atención para detectar diferencias entre dos imágenes.",
                "Detecta el cambio: reto de atención visual."),
    "memory": ("Test de memoria visual: recuerda dónde estaba cada figura.",
               "Entrena tu memoria con retos cortos y respuesta al final."),
    "stroop": ("Efecto Stroop: test de atención y control mental con colores.",
               "Reto de colores y palabras que confunde a tu cerebro."),
    "math": ("Cálculo mental con trampa: ¿te fías del primer resultado?",
             "Retos de matemáticas y orden de operaciones sin calculadora."),
    "sequence": ("Secuencias numéricas: adivina el número que sigue con lógica.",
                 "Test de lógica y razonamiento con series de números."),
    "riddle": ("Acertijos con respuesta para entrenar tu mente.",
               "Adivinanzas y preguntas trampa de lógica con la solución al final."),
    "cups": ("Juego de los vasos: sigue la bola con los ojos.",
             "Reto de atención y seguimiento visual: ¿dónde está la bola?"),
    "simon": ("Juego de memoria tipo Simón: recuerda el orden de las luces.",
              "Test de memoria de secuencias con luces y números."),
    "digits": ("Encuentra el número distinto: test de vista y atención.",
               "Reto de atención visual con números casi idénticos."),
    "loop": ("Bucle perfecto y relajante, ideal para ver una y otra vez.",
             "Video hipnótico en bucle: ¿dónde empieza y dónde termina?"),
    "mix": ("Mini-retos de atención, memoria y lógica en un solo video.",
            "Test de cerebro con retos variados y la respuesta al final."),
}
# (infinitivo para «¿Puedes ...?», plural para «5 ...»)
ACTION = {
    "anomaly": ("encontrar la figura distinta", "retos visuales"), "illusion": ("no caer en estas ilusiones", "ilusiones ópticas"),
    "ishihara": ("ver lo que hay escondido", "test de visión"), "magiceye": ("ver la figura 3D", "figuras 3D escondidas"),
    "contrast": ("decir qué color es más claro", "pruebas de contraste"), "sync": ("pausar en el instante exacto", "pruebas de reflejos"),
    "swarm": ("seguir el punto rojo", "rondas de seguimiento"), "count": ("contar bien las figuras", "retos de conteo"),
    "flicker": ("ver qué cambia", "retos de atención"), "memory": ("recordar dónde estaba cada figura", "retos de memoria"),
    "stroop": ("decir el color y no la palabra", "pruebas Stroop"), "math": ("resolver estas cuentas sin calculadora", "cuentas con trampa"),
    "sequence": ("adivinar el número que sigue", "secuencias"), "riddle": ("resolver estos acertijos", "acertijos"),
    "cups": ("seguir la bola", "rondas de vasos"), "simon": ("recordar el orden de las luces", "secuencias de luces"),
    "digits": ("encontrar el número distinto", "retos de números"), "mix": ("superar estos retos", "mini-retos"),
}
AI_LABEL_NOTE = ("Activa «Etiqueta de IA» al publicar: la voz del video es sintética y Meta pide declarar el audio realista "
                 "creado digitalmente (puede penalizar si no se declara).")


def _generic_titles(sc) -> list:
    """Titulos con estructura distinta a los de cada tipo; se mezclan con ellos para que haya mas rotacion."""
    if sc.mode == "loop" or sc.mode not in ACTION:
        return []
    act, plural = ACTION[sc.mode]
    n = len(sc.acts)
    rng = random.Random(sc.seed ^ 0x7171)
    p = rng.choice((1, 3, 5, 10))
    return [f"Solo el {p}% logra {act}", f"{n} {plural}: ¿cuántos aciertas?", f"¿Puedes {act}? El último casi nadie lo logra",
            f"Nadie acierta los {n} {plural} a la primera", f"¿Eres capaz de {act}? Compruébalo en {n} pruebas",
            f"{n} {plural} para poner a prueba tu cerebro"]


MAX_REROLL = 64        # intentos de recomponer el texto hasta que no coincida con una publicacion reciente


def post_hash(paste: str) -> str:
    """Huella corta del texto a pegar: sirve para no repetir nunca la misma publicacion."""
    return hashlib.sha1(paste.encode("utf-8")).hexdigest()[:12]


def _compose(sc: Scene, tl: Timeline, rng: random.Random, avoid) -> dict:
    """Una version del texto de publicacion, armada con fragmentos elegidos con `rng` (ver copy_es.py)."""
    pick = _Pick(rng, avoid)
    titles, descs, extra = _BUILDERS[sc.mode](sc, tl)
    n, loop = len(sc.acts), sc.mode == "loop"
    act, plural = ACTION.get(sc.mode, ("", ""))
    own_title = loop or sc.mode == "riddle" or rng.random() < 0.5        # el acertijo siempre lleva el primer acertijo
    title = pick.title(list(titles) + ([] if sc.mode == "riddle" else _generic_titles(sc))) if own_title \
        else copy_es.make_title(rng, act, plural, n)
    head, _, rest = pick.choice(descs).partition("\n\n")
    if not loop and sc.mode != "riddle" and rng.random() < 0.5:
        head = copy_es.make_desc_open(rng, act, plural, n)
    if sc.mode not in ("riddle", "ishihara") and rng.random() < 0.5:     # ishihara conserva su aviso de «solo un juego»
        rest = copy_es.make_ask(rng, n, loop)
    seo = pick.choice(SEO[sc.mode])
    if not loop and rng.random() < 0.5:
        seo += " " + copy_es.make_seo_tail(rng)
    desc = head + "\n" + seo + (("\n\n" + rest) if rest else "")
    footer = copy_es.make_share(rng) + "\n" + copy_es.make_follow(rng)
    tags = copy_es.make_tags(rng, sc.mode, [a.type for a in sc.acts])
    pinned = copy_es.make_pinned(rng, n, loop)
    paste = f"{title}\n\n{desc}\n\n{footer}\n\n{' '.join(tags)}"      # exactamente lo que se pega en la publicacion
    return dict(title=title, desc=desc, footer=footer, tags=tags, pinned=pinned, paste=paste, extra=extra)


def build_post(sc: Scene, tl: Timeline, avoid=(), avoid_posts=()) -> dict:
    """Todo el texto de publicacion de un video. Determinista por semilla y por historial: `avoid` = titulos usados hace
    poco y `avoid_posts` = huellas de publicaciones recientes; se recompone (otra sal) hasta que el texto sea nuevo."""
    avoid_posts = set(avoid_posts)
    post = {}
    for salt in range(MAX_REROLL):
        rng = random.Random(sc.seed ^ 0xCAFE ^ (salt * 0x9E3779B1))
        post = _compose(sc, tl, rng, avoid)
        post["salt"], post["hash"] = salt, post_hash(post["paste"])
        if post["hash"] not in avoid_posts and (post["title"] not in avoid or salt >= MAX_REROLL // 2):
            break
    return post


def write_metadata(path: Path, sc: Scene, tl: Timeline, video_name: str, avoid=(), avoid_posts=()) -> tuple:
    """Escribe el .txt de publicacion (y `<nombre>_publicar.txt`, solo con el texto a pegar).
    Devuelve (ruta, titulo, huella del texto)."""
    post = build_post(sc, tl, avoid, avoid_posts)
    variables = [f"Semilla: {sc.seed}", f"Paleta: {sc.palette.name.capitalize()}"]
    if sc.mode != "loop":
        variables.append(f"Estructura: {len(sc.acts)} retos de {', '.join(sorted({TYPES[a.type].menu for a in sc.acts}))}")
        variables.append("Respuestas (control interno): " + _answers_text(sc))
    variables += [f"Duración: {tl.spec.duration:.0f}s a {tl.spec.fps} fps", *post["extra"]]
    stem = video_name.rsplit(".", 1)[0]
    text = (
        "=== COPIAR Y PEGAR TODO JUNTO EN LA PUBLICACIÓN (título + descripción + hashtags) ===\n"
        f"{post['paste']}\n"
        "=== FIN DEL TEXTO A PEGAR ===\n\n"
        f"ARCHIVO: {video_name}\n\n"
        f"TIPO DE VIDEO: {MODE_LABEL[sc.mode]}\n\n"
        f"ANTES DE PUBLICAR: {AI_LABEL_NOTE}\n"
        f"Portada: sube {stem}_portada.jpg como miniatura del Reel (lleva el gancho a pantalla completa).\n\n"
        "VARIABLES (control interno):\n" + "\n".join(f"  - {v}" for v in variables) + "\n\n"
        f"TÍTULO SUGERIDO:\n{post['title']}\n\n"
        f"DESCRIPCIÓN (COPY):\n{post['desc']}\n\n{post['footer']}\n\n"
        f"COMENTARIO FIJADO (publícalo tú justo después y fíjalo: los comentarios sencillos de una cifra son los que más se responden):\n"
        f"{post['pinned']}\n\n"
        f"HASHTAGS:\n{' '.join(post['tags'])}\n"
    )
    path.write_text(text, encoding="utf-8-sig")
    path.with_name(f"{path.stem}_publicar.txt").write_text(post["paste"] + "\n", encoding="utf-8-sig")
    return path, post["title"], post["hash"]
