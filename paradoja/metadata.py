"""Nombre de archivo descriptivo + borrador de publicacion (.txt) para cada video."""
import random
import unicodedata
from pathlib import Path

import numpy as np

from .scene import ANOMALY_KINDS, ILLUSIONS, SHAPES, Scene, _swarm_positions, swarm_clock
from .script_es import NUMS
from .timeline import Timeline

MODE_LABEL = {"anomaly": "Reto de Anomalía", "illusion": "Ilusión Óptica", "loop": "Bucle",
              "sync": "Reto de Sincronización (Pausa)", "ishihara": "Test de Visión (Ishihara)",
              "swarm": "Seguimiento de Enjambre", "magiceye": "Ojo Mágico (Autoestereograma)",
              "contrast": "Ilusión de Contraste Simultáneo"}
MODE_SLUG = {"anomaly": "anomalia", "illusion": "ilusion", "loop": "bucle", "sync": "sincronia",
             "ishihara": "ishihara", "swarm": "enjambre", "magiceye": "ojomagico", "contrast": "contraste"}
CONTRAST_KINDS = ("gradiente vertical", "gradiente radial", "campo dividido")
LOOP_KINDS = (("poligonos", "zoom de polígonos sin fin"), ("anillos", "anillos de figuras orbitando"),
              ("ondas", "ondas hipnóticas"))
# nombre en archivo, nombre legible, pregunta para los comentarios
ILL_INFO = {
    "ouchi": ("ouchi", "ilusión de Ouchi", "¿Viste moverse el círculo del centro?"),
    "cafe": ("cafewall", "ilusión del Café Wall", "¿Te parecieron torcidas las líneas?"),
    "ebbinghaus": ("ebbinghaus", "ilusión de Ebbinghaus", "¿Cuál círculo del centro viste más grande: el izquierdo o el derecho?"),
    "scintillating": ("rejilla", "rejilla centelleante", "¿Cuántos puntos negros alcanzaste a ver?"),
    "spiral": ("espiral", "espiral hipnótica", "Después de mirarla, ¿se movió tu mano?"),
    "moire": ("muare", "efecto muaré", "¿Cuántas capas viste moverse?"),
}
KIND_DESC = {  # sufijo segun genero -> descripcion de la diferencia
    "hue": "de otro color", "size": "más pequeñ{o}", "bright": "más brillante",
    "dot": "con el punto fuera de lugar", "rotate": "girad{o}",
}


def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().replace(" ", "")


def _g(shape: int) -> dict:
    noun, fem = SHAPES[shape]
    return dict(noun=noun, el="la" if fem else "el", un="una" if fem else "un", o="a" if fem else "o",
                pl=noun + "s")


def video_slug(sc: Scene) -> str:
    """anomalia_estrella_<semilla> | ilusion_espiral_<semilla> | bucle_anillos_<semilla>"""
    if sc.mode == "anomaly":
        detail = _ascii(SHAPES[sc.shape][0])
    elif sc.mode == "illusion":
        detail = ILL_INFO[ILLUSIONS[sc.acts[0].kind]][0]
    elif sc.mode == "ishihara":
        a = sc.acts[0]
        detail = str(a.sym) if a.sym >= 0 else _ascii(SHAPES[a.shape][0])
    elif sc.mode == "magiceye":
        detail = _ascii(SHAPES[sc.acts[0].shape][0])
    elif sc.mode in ("sync", "swarm", "contrast"):
        detail = _ascii(SHAPES[sc.shape][0])
    else:
        detail = LOOP_KINDS[sc.loop_kind][0]
    return f"{MODE_SLUG[sc.mode]}_{detail}_{sc.seed}"


# ----------------------------------------------------------------------------- textos
def _anomaly(sc, tl, rng):
    g, n = _g(sc.shape), len(sc.acts)
    diffs = [KIND_DESC[ANOMALY_KINDS[a.kind]].format(o=g["o"]) for a in sc.acts]
    title = rng.choice((
        f"¿Puedes encontrar {g['el']} {g['noun']} diferente? Solo el 1% lo logra",
        f"Reto visual: {n} retos y {g['un']} {g['noun']} distinto escondido",
        f"Tu cerebro no es tan rápido como crees: encuentra {g['el']} {g['noun']} que no encaja",
        f"{n} retos, 1 {g['noun']} diferente en cada uno. ¿Cuántos aciertas?",
    ))
    desc = rng.choice((
        f"Hay {g['un']} {g['noun']} distinto escondido en cada reto, y cada vez es más difícil. 🔍\n\n"
        f"👇 Comenta en qué segundo lo notaste en el reto {NUMS[n - 1]} (el último). "
        f"¿Llegaste a ver los {n}?\n\nSi lo lograste sin pausar, eres de los pocos. Sígueme para más retos visuales.",
        f"Mira bien: entre decenas de figuras hay {g['un']} {g['noun']} que no es igual a las demás. "
        f"Tienes pocos segundos por reto.\n\n"
        f"👇 Escribe en qué segundo lo encontraste. ¡El último reto es casi imposible!\n\n"
        f"Etiqueta a alguien que crea que tiene mejor vista que tú.",
        f"{n} retos. {g['el'].capitalize()} {g['noun']} diferente se esconde cada vez mejor. 👀\n\n"
        f"👇 Cuéntame en los comentarios: ¿en qué segundo lo notaste? ¿Cuántos retos acertaste?\n\n"
        f"Sígueme para un reto nuevo cada día.",
    ))
    tags = ["#RetoVisual", "#EncuentraLaDiferencia", "#TestVisual", f"#{_ascii(g['pl']).capitalize()}", "#ParadojaInfinita"]
    reveals = ", ".join(f"reto {a.index + 1}: {tl.act_start(a.index) + tl.search_len:.1f}s" for a in sc.acts)
    extra = [f"Figura: {g['noun'].capitalize()}", f"Retos ({n}): " + "; ".join(
        f"{i + 1}) {d}" for i, d in enumerate(diffs)), f"Se revela la respuesta en: {reveals}"]
    return title, desc, tags, extra


def _illusion(sc, tl, rng):
    names = [ILL_INFO[ILLUSIONS[a.kind]] for a in sc.acts]
    n, first = len(names), names[0]
    listing = ", ".join(x[1] for x in names)
    title = rng.choice((
        f"Tu cerebro te miente: {first[1]} y {n - 1} ilusiones más",
        f"{n} ilusiones ópticas que engañan a casi todos. ¿Y a ti?",
        f"Lo que ves no es real: {first[1]}",
        f"¿Caes en las {n} ilusiones? Empieza con la {first[1]}",
    ))
    desc = rng.choice((
        f"Cada ilusión usa un truco distinto de tu cerebro: {listing}. 🧠\n\n"
        f"👇 {first[2]} Cuéntame en los comentarios cuántas de las {n} te engañaron.\n\n"
        f"Sígueme para más ilusiones ópticas.",
        f"Mira con calma: nada de esto es lo que parece ({listing}).\n\n"
        f"👇 Pregunta rápida: {first[2]} ¿Y cuántas ilusiones viste funcionar, de 0 a {n}?\n\n"
        f"Comparte con alguien que crea que no se deja engañar.",
        f"Tu cerebro rellena huecos... y se equivoca. 👁️ Hoy: {listing}.\n\n"
        f"👇 {first[2]} Escribe tu resultado (0 a {n}) y descubre quién se engaña más.",
    ))
    tags = ["#IlusionOptica", "#IlusionesOpticas", "#TuCerebroTeEngana", "#ParadojaInfinita"]
    extra = [f"Ilusiones ({n}): " + "; ".join(f"{i + 1}) {x[1]}" for i, x in enumerate(names)),
             "Preguntas por ilusión: " + " | ".join(f"{i + 1}) {x[2]}" for i, x in enumerate(names))]
    return title, desc, tags, extra


def _loop(sc, tl, rng):
    g = _g(sc.shape)
    kind = LOOP_KINDS[sc.loop_kind][1]
    if sc.loop_kind == 1:
        kind = f"anillos de {g['pl']} orbitando"
    P, D = sc.loop_period, tl.spec.duration
    title = rng.choice((
        "Este bucle no tiene principio ni final. ¿Dónde empieza?",
        f"Bucle infinito: {kind}. Imposible dejar de mirar",
        "Intenta encontrar el momento exacto donde se repite",
        "Mira fijamente: este video nunca termina",
    ))
    desc = rng.choice((
        f"Un bucle perfecto de {kind}. Se repite cada {P:.0f} segundos y el final conecta con el inicio sin saltos. ♾️\n\n"
        f"👇 Comenta cuántas veces lo repetiste antes de darte cuenta.\n\nSígueme para más bucles hipnóticos.",
        f"¿Puedes ver dónde empieza y dónde termina? Casi nadie lo logra. ({kind})\n\n"
        f"👇 Dime cuántas veces seguidas lo viste. Sé honesto. 😅\n\nDeja un ♾️ si no pudiste dejar de mirar.",
        f"Mira esto una vez... y verás cómo se repite solo. Son {D:.0f} segundos de {kind} sin cortes.\n\n"
        f"👇 ¿Cuántas veces lo repetiste? Escribe el número.",
    ))
    tags = ["#BucleInfinito", "#PerfectLoop", "#Hipnotico", "#Satisfying", "#ParadojaInfinita"]
    extra = [f"Tipo de bucle: {kind}", f"Periodo: {P:.1f}s ({sc.loop_k} vueltas por video)"]
    if sc.loop_kind == 1:
        extra.insert(1, f"Figura: {g['noun'].capitalize()}")
    return title, desc, tags, extra


def _sync(sc, tl, rng):
    g, n, S = _g(sc.shape), len(sc.acts), tl.search_len
    digits = [int(S - (a.hit - tl.act_start(a.index))) + 1 for a in sc.acts]
    title = rng.choice((
        f"¿Puedes pausar justo cuando {g['el']} {g['noun']} encaja? Solo tienes 1 fotograma",
        f"Reto de reflejos: pausa en el instante exacto ({n} intentos)",
        f"El 99% falla: pausa cuando {g['el']} {g['noun']} encaje en la silueta",
        f"{n} pruebas, 1 fotograma para acertar. ¿Cuántas logras?",
    ))
    desc = rng.choice((
        f"{g['el'].capitalize()} {g['noun']} gira a velocidad extrema y solo encaja UN fotograma por prueba. ⏸️\n\n"
        f"👇 Pausa el video y comenta en qué número del contador (5, 4, 3, 2 o 1) lo hiciste en la última prueba. "
        f"¿Acertaste las {n}?\n\nSi pausaste a tiempo, demuéstralo con una captura.",
        f"Pon a prueba tus reflejos: pausa justo cuando {g['el']} {g['noun']} coincida con la silueta. "
        f"Cada prueba es más rápida. ⚡\n\n👇 Comenta cuántas de las {n} pruebas lograste y reta a un amigo a superarte.",
        f"Un solo fotograma. Una sola oportunidad. ⏱️\n\n"
        f"👇 Escribe en comentarios en qué prueba fallaste primero (1 a {n}) y etiqueta a quien tenga mejores reflejos.",
    ))
    tags = ["#RetoDeReflejos", "#PausaElVideo", "#RetoVisual", "#ParadojaInfinita"]
    extra = [f"Figura: {g['noun'].capitalize()}",
             "Encaje por prueba (número del contador): " + "; ".join(f"{i + 1}) {d}" for i, d in enumerate(digits)),
             "Segundo exacto del encaje en el video: " + ", ".join(f"{a.hit:.2f}s" for a in sc.acts),
             "La velocidad sube en cada prueba"]
    return title, desc, tags, extra


def _ishihara(sc, tl, rng):
    items = [str(a.sym) if a.sym >= 0 else SHAPES[a.shape][0] for a in sc.acts]
    n = len(items)
    nums = sum(a.sym >= 0 for a in sc.acts)
    what = "números" if nums == n else "figuras" if nums == 0 else "números y figuras"
    title = rng.choice((
        f"Test de visión: ¿qué {what} escondí? Solo 1 de cada 10 los ve",
        f"¿Ves lo que hay escondido? {n} tests, cada uno más difícil",
        f"Entrecierra los ojos: {n} tests con {what} escondidos entre los puntos",
        f"Reto visual: ¿cuántos de los {n} tests logras ver?",
    ))
    note = "(Es solo un juego, no un test médico.)"
    desc = rng.choice((
        f"Hay {what} escondidos entre los puntos y cada test es más difícil. 👀\n\n"
        f"👇 Escribe en los comentarios lo que viste en cada test (1, 2, 3...). Sin trampas. "
        f"Si no ves nada en alguno, comenta NO VEO.\n\n{note}",
        f"Tu cerebro busca patrones en el caos. ¿Puedes encontrarlos? 🧠\n\n"
        f"👇 Comenta cuántos de los {n} tests lograste ver y cuál fue el más difícil.\n\n{note}",
        f"Aleja el teléfono, entrecierra los ojos y mira bien. {n} tests con {what} escondidos. 🔍\n\n"
        f"👇 ¿Qué viste en el último? Escríbelo antes de ver la respuesta.\n\n{note}",
    ))
    tags = ["#TestDeVision", "#Ishihara", "#RetoVisual", "#PruebaVisual", "#ParadojaInfinita"]
    extra = ["Respuestas: " + "; ".join(f"{i + 1}) {x}" for i, x in enumerate(items)),
             "El contraste de color baja en cada test"]
    return title, desc, tags, extra


def _quadrant(x, y):
    return ("arriba" if y < 0 else "abajo") + "-" + ("izquierda" if x < 0 else "derecha")  # y<0 = parte alta


def _swarm(sc, tl, rng):
    g, n, S = _g(sc.shape), len(sc.acts), tl.search_len
    finals = []
    for a in sc.acts:
        pa = np.frombuffer(a.arrays["u_pa"], "f4").reshape(-1, 4)
        pb = np.frombuffer(a.arrays["u_pb"], "f4").reshape(-1, 4)
        x, y = _swarm_positions(pa, pb, a.n, swarm_clock(S, S, a.q[0]))[0]
        finals.append(_quadrant(x, y))
    title = rng.choice((
        "Sigue el punto rojo: solo los mejores no lo pierden",
        f"¿Dónde quedó el punto rojo? {n} retos de atención",
        "Tu atención contra el caos: no pierdas de vista el punto rojo",
        f"Reto de seguimiento: {n} rondas y cada vez más rápido",
    ))
    desc = rng.choice((
        f"Un {g['noun']} rojo se mezcla con decenas más... y todos se detienen. ¿Sabes cuál era? 🔴\n\n"
        f"👇 Comenta en qué parte quedó en el último reto: ARRIBA, ABAJO, IZQUIERDA o DERECHA. "
        f"La respuesta está al final de cada ronda.\n\nSi lo seguiste las {n} veces, eres de los pocos.",
        f"No parpadees. El punto rojo desaparece entre el caos y cada ronda hay más figuras. 👁️\n\n"
        f"👇 Escribe cuántas rondas acertaste (0 a {n}) y etiqueta a alguien con buena vista.",
        f"{n} rondas, un solo objetivo. Sigue el punto rojo con los ojos. 🎯\n\n"
        f"👇 ¿En qué ronda lo perdiste? Cuéntamelo en los comentarios.",
    ))
    tags = ["#RetoDeAtencion", "#SigueElPunto", "#RetoVisual", "#ParadojaInfinita"]
    extra = [f"Figura de las partículas: {g['noun'].capitalize()}",
             "Partículas por ronda: " + ", ".join(str(a.n) for a in sc.acts),
             "Posición final del punto rojo: " + "; ".join(f"{i + 1}) {q}" for i, q in enumerate(finals))]
    return title, desc, tags, extra


def _magiceye(sc, tl, rng):
    names = [SHAPES[a.shape][0] for a in sc.acts]
    n = len(names)
    title = rng.choice((
        "Ojo mágico: ¿qué figura en 3D está escondida?",
        f"Desenfoca la vista: {n} figuras 3D escondidas en el ruido",
        "Solo 1 de cada 5 ve la figura 3D. ¿Y tú?",
        f"Reto de ojo mágico: ¿cuántas de las {n} figuras logras ver?",
    ))
    desc = rng.choice((
        "Relaja la vista, mira a través de la pantalla y espera: una figura 3D flota en el ruido. 👁️\n\n"
        "👇 Escribe qué figura viste en cada prueba. ¿No ves nada? Comenta NO VEO y te cuento el truco.",
        f"Mira a través de la imagen, como si enfocaras algo detrás de la pantalla. {n} pruebas. 🧠\n\n"
        "👇 Comenta qué figura viste en la última y cuánto tardaste en verla.",
        f"No es ruido: hay una figura escondida. Desenfoca y espera unos segundos. ✨\n\n"
        f"👇 Dime qué figura apareció (1 a {n}) y comparte con quien tenga paciencia.",
    ))
    tags = ["#OjoMagico", "#Autoestereograma", "#Imagen3D", "#RetoVisual", "#ParadojaInfinita"]
    extra = ["Figuras ocultas: " + "; ".join(f"{i + 1}) {x}" for i, x in enumerate(names)),
             "Truco: mirar 'a través' de la pantalla hasta que los dos puntos rojos se fusionen y aparezcan tres"]
    return title, desc, tags, extra


def _contrast(sc, tl, rng):
    g, n = _g(sc.shape), len(sc.acts)
    kinds = [CONTRAST_KINDS[a.kind] for a in sc.acts]
    title = rng.choice((
        f"¿Cambia de color {g['el']} {g['noun']}? Tus ojos mienten",
        f"Ilusión de contraste: {g['el']} {g['noun']} nunca cambió de color",
        f"{n} pruebas: ¿cambia o no cambia de color?",
        "Mira el bloque del centro: ¿qué color tiene realmente?",
    ))
    desc = rng.choice((
        f"{g['el'].capitalize()} {g['noun']} del centro parece cambiar de tono. ¿Cambia de verdad? 🎨\n\n"
        "👇 Vota en los comentarios: SÍ CAMBIÓ o NUNCA CAMBIÓ. La respuesta llega al final de cada prueba.",
        "Solo cambia el fondo... pero tu cerebro jura que la figura también. 🧠\n\n"
        f"👇 Comenta cuántas de las {n} pruebas te engañaron (0 a {n}).",
        "Mira con atención el centro. ¿Es siempre el mismo color? 👁️\n\n"
        "👇 Escribe tu respuesta antes de ver el final y etiqueta a alguien que crea que no se deja engañar.",
    ))
    tags = ["#IlusionOptica", "#ContrasteSimultaneo", "#TuCerebroTeEngana", "#ParadojaInfinita"]
    extra = [f"Figura: {g['noun'].capitalize()}",
             "Fondo por prueba: " + "; ".join(f"{i + 1}) {k}" for i, k in enumerate(kinds)),
             "El bloque central nunca cambia de color (se funde con el fondo al revelar)"]
    return title, desc, tags, extra


_BUILDERS = {"anomaly": _anomaly, "illusion": _illusion, "loop": _loop, "sync": _sync, "ishihara": _ishihara,
             "swarm": _swarm, "magiceye": _magiceye, "contrast": _contrast}


def write_metadata(path: Path, sc: Scene, tl: Timeline, video_name: str) -> Path:
    rng = random.Random(sc.seed ^ 0xCAFE)
    title, desc, tags, extra = _BUILDERS[sc.mode](sc, tl, rng)
    tags = tags[:5]
    variables = [f"Semilla: {sc.seed}", f"Paleta: {sc.palette.name.capitalize()}"]
    if not tl.is_loop:
        variables.append(f"Gancho: {('túnel en espiral', 'túnel de polígonos', 'caleidoscopio')[sc.hook_kind]}")
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
    return path
