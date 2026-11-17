"""Nombre de archivo descriptivo + borrador de publicacion (.txt) para cada video."""
import random
import unicodedata
from pathlib import Path

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
}
MODE_SLUG = {
    "anomaly": "anomalia", "illusion": "ilusion", "ishihara": "ishihara", "magiceye": "ojomagico", "contrast": "contraste",
    "sync": "sincronia", "swarm": "enjambre", "count": "conteo", "flicker": "cambio", "memory": "memoria",
    "stroop": "stroop", "math": "calculo", "sequence": "secuencia", "riddle": "acertijo", "loop": "bucle", "mix": "mixto",
}
TAGS = {
    "anomaly": ["#RetoVisual", "#EncuentraLaDiferencia", "#TestVisual"],
    "illusion": ["#IlusionOptica", "#IlusionesOpticas", "#TuCerebroTeEngana"],
    "ishihara": ["#TestDeVision", "#Ishihara", "#PruebaVisual", "#RetoVisual"],
    "magiceye": ["#OjoMagico", "#Autoestereograma", "#Imagen3D", "#RetoVisual"],
    "contrast": ["#IlusionOptica", "#ContrasteSimultaneo", "#TuCerebroTeEngana"],
    "sync": ["#RetoDeReflejos", "#PausaElVideo", "#RetoVisual"],
    "swarm": ["#RetoDeAtencion", "#SigueElPunto", "#RetoVisual"],
    "count": ["#CuentaLasFiguras", "#RetoDeAtencion", "#RetoVisual"],
    "flicker": ["#QueCambio", "#RetoDeAtencion", "#RetoVisual"],
    "memory": ["#TestDeMemoria", "#Memoria", "#RetoMental"],
    "stroop": ["#EfectoStroop", "#RetoMental", "#TuCerebro"],
    "math": ["#RetoMatematico", "#Matematicas", "#RetoMental"],
    "sequence": ["#QueNumeroSigue", "#RetoDeLogica", "#Matematicas"],
    "riddle": ["#Acertijos", "#Adivinanzas", "#RetoMental"],
    "loop": ["#BucleInfinito", "#PerfectLoop", "#Hipnotico", "#Satisfying"],
    "mix": ["#RetoMental", "#TestDeCerebro", "#RetoVisual"],
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
        detail = ("ouchi", "cafewall", "ebbinghaus", "rejilla", "espiral", "muare")[a0.kind]
    elif sc.mode == "ishihara":
        detail = str(a0.sym) if a0.sym >= 0 else _ascii(SHAPES[a0.shape][0])
    elif sc.mode == "magiceye":
        detail = _ascii(SHAPES[a0.shape][0])
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
    n, q = len(sc.acts), sc.acts[0].question
    short = f"Acertijo: {q}" if len(q) <= 48 else f"Acertijo: {q[:44].rsplit(' ', 1)[0]}..."
    titles = (short, f"{n} acertijos y preguntas trampa: ¿cuántos aciertas?",
              "Solo 1 de cada 10 resuelve estos acertijos a la primera",
              "Acertijos que engañan a tu cerebro. ¿Te atreves?")
    descs = ("Acertijos y preguntas trampa. Piensa antes de responder. 🧩\n\n"
             "👇 Comenta tu respuesta al último acertijo (sin hacer trampa).",
             f"{n} acertijos. Algunos son más fáciles de lo que parecen. 😏\n\n"
             f"👇 Escribe cuántos acertaste (0 a {n}) y cuál te sorprendió.",
             "Tu primera respuesta suele ser la equivocada. 🤔\n\n"
             "👇 ¿Cuál fue tu respuesta al primero? Cuéntamelo.")
    return titles, descs, []


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
             "stroop": _stroop, "math": _math, "sequence": _sequence, "riddle": _riddle, "loop": _loop, "mix": _mix}


def write_metadata(path: Path, sc: Scene, tl: Timeline, video_name: str, avoid=()) -> tuple:
    """Escribe el .txt de publicacion. Devuelve (ruta, titulo elegido). `avoid` = titulos usados recientemente."""
    rng = random.Random(sc.seed ^ 0xCAFE)
    pick = _Pick(rng, avoid)
    titles, descs, extra = _BUILDERS[sc.mode](sc, tl)
    title = pick.title(titles)
    desc = pick.choice(descs)
    specific = TAGS[sc.mode]
    if sc.mode == "mix":
        specific = specific + [t for ty in dict.fromkeys(a.type for a in sc.acts) for t in TAGS[ty][:1]]
    tags = list(dict.fromkeys(specific))[:4] + ["#ParadojaInfinita"]

    variables = [f"Semilla: {sc.seed}", f"Paleta: {sc.palette.name.capitalize()}"]
    if sc.mode != "loop":
        variables.append(f"Estructura: {len(sc.acts)} retos de {', '.join(sorted({TYPES[a.type].menu for a in sc.acts}))}")
        variables.append("Respuestas (control interno): " + _answers_text(sc))
    variables += [f"Duración: {tl.spec.duration:.0f}s a {tl.spec.fps} fps", *extra]
    text = (
        f"ARCHIVO: {video_name}\n\n"
        f"TIPO DE VIDEO: {MODE_LABEL[sc.mode]}\n\n"
        "VARIABLES (control interno):\n" + "\n".join(f"  - {v}" for v in variables) + "\n\n"
        f"TÍTULO SUGERIDO:\n{title}\n\n"
        f"DESCRIPCIÓN (COPY):\n{desc}\n\n"
        f"HASHTAGS:\n{' '.join(tags)}\n"
    )
    path.write_text(text, encoding="utf-8-sig")
    return path, title
