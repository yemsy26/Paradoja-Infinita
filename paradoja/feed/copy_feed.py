"""Texto de publicacion de las imagenes del feed: se arma con fragmentos y plantillas por semilla (ver `spin.py`).

El copy plantea el reto y cierra con una pregunta sobre el propio reto; no pide comentar, compartir, etiquetar ni seguir, ni
promete premios, ni afirma nada sobre lo que hace «la mayoria» (ver `copy_guard.py`). Cada texto lleva una huella para no repetir nunca el mismo copy (ver `history.py`).
"""
from __future__ import annotations

import hashlib
import random

from ..copy_es import BRAND_TAG
from ..spin import fill, pick, spin
from . import puzzles as P

HOOKS = {
    "pemdas": (
        "😲 ¿Es <trap>? {Piénsalo mejor|Revísalo con calma|Mira el orden de las operaciones}.",
        "🤯 {Cuidado|Ojo}: <trap> NO es la respuesta.",
        "🧮 {¿Sin calculadora?|¿A mano?|¿Solo con tu cabeza?} {A ver quién acierta|Demuéstralo|Inténtalo}.",
        "🤔 {El orden de las operaciones|La jerarquía de operaciones} {importa|cambia el resultado}: {¿cuánto da?|¿cuál es el resultado?}",
        "😅 {Parece fácil|Parece sencillo}, pero <trap> no es el resultado.",
    ),
    "cubos": (
        "🧊 {Cuenta bien|Mira con atención|Piensa antes de responder}: {hay cubos que no se ven|algunos cubos están escondidos}.",
        "👀 {Cuenta con calma|Fíjate bien|Mira desde otro ángulo}: ¿cuántos cubos hay {en total|de verdad}?",
        "🤔 ¿Cuántos cubos hay {en total|de verdad}? {No te quedes solo con los que se ven|Cuenta también los escondidos}.",
        "🧠 {Un reto de ingenio|Un reto de lógica espacial}: ¿cuántos cubos hay {en total|contando los escondidos}?",
    ),
    "fracciones": (
        "🔺 {No cuentes piezas|Cuidado|Ojo}: {no todas son del mismo tamaño|los triángulos engañan}.",
        "🧠 ¿Qué fracción {es|representa} la {zona|región} gris? {Parece fácil|Fíjate bien|Piénsalo dos veces}.",
        "📐 {Un reto de fracciones|Una prueba de geometría}: {¿cuánto es la parte gris?|¿qué parte del total es gris?}",
        "🤨 {Contar piezas|Contar triángulos} {no basta|no te llevará a la respuesta}. ¿Qué fracción es la región gris?",
    ),
    "opciones": (
        "📝 {Solo una opción es correcta|Una sola es la buena}... {y las otras están hechas para confundirte|¿cuál será?}",
        "🤨 {Piensa antes de elegir|No te precipites}: {hay trampa|las opciones se parecen mucho}.",
        "🎯 {A, B, C o D: ¿cuál es la correcta?|¿Cuál eliges?} {Cuidado con la trampa.|Fíjate bien en los detalles.|Léelas con calma.}",
        "🧠 {Un reto de lógica|Una pregunta con truco}: {¿te atreves?|¿cuál es la correcta?}",
    ),
}
BODY = {
    "pemdas": ("<eq> = ?",),
    "cubos": ("¿Cuántos cubos hay en total? {Cuenta también los que no se ven.|No olvides los que están escondidos.|Piensa en los que quedan tapados.}",),
    "fracciones": ("¿Qué fracción representa la región gris? {Respóndela simplificada.|Escríbela en su forma más simple.}",),
}
# Cierre de la publicacion: una pregunta o una indicacion sobre el reto. Nunca pide comentar, compartir, etiquetar ni seguir.
ASKS = {
    "pemdas": ("{¿Qué resultado te sale?|¿Cuánto da?|¿Cuál es tu resultado?} {Sin calculadora, si puedes.|Piénsalo con calma.|Revisa el orden de las operaciones.}",
               "{¿Lo resuelves a la primera?|¿Te sale a la primera?} {Sin calculadora.|Sin hacer trampa.}"),
    "cubos": ("{¿Cuántos cubos cuentas?|¿Cuántos cubos hay?|¿Cuál es tu número?} {Piénsalo con calma.|Cuenta por capas.|Incluye los que quedan tapados.}",
              "{¿Los cuentas todos?|¿Cuentas también los escondidos?} {Sin hacer trampa.|Con calma.}"),
    "fracciones": ("{¿Qué fracción es?|¿Cuál es la fracción?} {Simplifícala.|Dala en su forma más simple.|Piénsalo con calma.}",
                   "{¿Lo ves a la primera?|¿Te sale simplificada?} {Sin hacer trampa.|Con calma.}"),
    "opciones": ("{¿Cuál eliges?|¿Qué letra elegirías?|¿Cuál es la correcta?} {Piénsalo con calma.|Fíjate en los detalles.|Descarta las que no encajan.}",
                 "{¿A, B, C o D?|¿Cuál de las cuatro?} {Sin mirar la solución.|Con calma y sin trampa.}"),
}
TAG_POOLS = {
    "pemdas": ("#Matematicas", "#RetoMatematico", "#CalculoMental", "#AcertijosMatematicos", "#JuegosMentales", "#TestDeLogica"),
    "cubos": ("#RetoVisual", "#CuentaLosCubos", "#LogicaEspacial", "#JuegosMentales", "#TestDeIngenio", "#Acertijos"),
    "fracciones": ("#Matematicas", "#Fracciones", "#RetoMatematico", "#JuegosMentales", "#TestDeLogica", "#Geometria"),
    "opciones": ("#Acertijos", "#PreguntasTrampa", "#TestDeLogica", "#JuegosMentales", "#RetoMental", "#EntrenaTuMente"),
}
SUB_TAGS = {"romanos": "#NumerosRomanos", "secuencia": "#QueNumeroSigue", "trampa": "#PreguntasTrampa"}


def post_hash(paste: str) -> str:
    return hashlib.sha1(paste.encode("utf-8")).hexdigest()[:12]


def _compose(puz: P.Puzzle, rng: random.Random) -> dict:
    kind = puz.kind
    slots = dict(trap=puz.trap or "", eq=puz.data.get("eq", ""))
    hook = spin(rng, rng.choice(HOOKS[kind]), **slots)
    if kind == "opciones":
        data = puz.data
        head = data["question"] + (f"\n{data['display']}" if data["display"] else "")
        body = head + "\n" + "\n".join(f"{P.LETTERS[i]}) {o}" for i, o in enumerate(data["options"]))
    else:
        body = rng.choice(BODY[kind])
        body = fill(body, **slots) if kind == "pemdas" else spin(rng, body, **slots)     # «= ?» no debe pegarse
    ask = pick(rng, ASKS[kind])
    tags = list(rng.sample(TAG_POOLS[kind], rng.choice((3, 3, 4))))
    if kind == "opciones" and puz.detail in SUB_TAGS and SUB_TAGS[puz.detail] not in tags:
        tags[-1] = SUB_TAGS[puz.detail]
    tags = list(dict.fromkeys(tags))[:4] + [BRAND_TAG]
    paste = f"{hook}\n\n{body}\n\n{ask}\n\n{' '.join(tags)}"
    reveal = f"✅ Respuesta: {puz.answer}\n{puz.explanation}"
    return dict(paste=paste, hook=hook, body=body, ask=ask, tags=tags, alt=puz.alt, reveal=reveal)


def build_post(puz: P.Puzzle, seed: int, avoid_posts=(), max_reroll: int = 64) -> dict:
    """Copy para pegar junto a la imagen. Determinista por (reto, semilla, historial): si la huella coincide con una
    publicacion reciente se recompone con otra «sal»."""
    avoid_posts = set(avoid_posts)
    post = {}
    for salt in range(max_reroll):
        post = _compose(puz, random.Random(seed ^ 0xC0DE ^ (salt * 0x9E3779B1)))
        post["salt"], post["hash"] = salt, post_hash(post["paste"])
        if post["hash"] not in avoid_posts:
            break
    return post
