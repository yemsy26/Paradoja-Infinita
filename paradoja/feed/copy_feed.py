"""Texto de publicacion de las imagenes del feed: se arma con fragmentos y plantillas por semilla (ver `spin.py`).

El copy pide la respuesta en comentarios (una pregunta, que es lo permitido) y seguir la pagina; no promete premios ni pide
reacciones a cambio de nada. Cada texto lleva una huella para no repetir nunca el mismo copy (ver `history.py`).
"""
from __future__ import annotations

import hashlib
import random

from ..copy_es import BRAND_TAG
from ..spin import fill, pick, spin
from . import puzzles as P

HOOKS = {
    "pemdas": (
        "😲 {Muchos responden|Mucha gente responde|Muchos calculan|Mucha gente calcula} <trap>... y se equivoca. ¿Y tú?",
        "🤯 {Cuidado|Ojo}: <trap> NO es la respuesta.",
        "🧮 {¿Sin calculadora?|¿A mano?|¿Solo con tu cabeza?} {A ver quién acierta|Demuéstralo|Inténtalo}.",
        "🤔 {Muchos calculan|Muchos resuelven|Mucha gente calcula|Mucha gente resuelve} de izquierda a derecha... y {fallan|se equivocan}. ¿Y tú?",
        "😅 {Parece fácil|Parece sencillo}, pero <trap> no es el resultado.",
    ),
    "cubos": (
        "🧊 {Cuenta bien|Mira con atención|Piensa antes de responder}: {hay cubos que no se ven|algunos cubos están escondidos}.",
        "👀 {Solo los más atentos aciertan|Muy pocos aciertan|Casi nadie acierta} {cuántos cubos hay|el total de cubos}.",
        "🤔 ¿Cuántos cubos hay {en total|de verdad}? {Muchos cuentan solo los que se ven|Mucha gente cuenta mal}.",
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
        "🎯 {A, B, C o D: ¿cuál es la correcta?|¿Cuál eliges?} {Casi nadie acierta a la primera.|Cuidado con la trampa.|Fíjate bien en los detalles.}",
        "🧠 {Un reto de lógica|Una pregunta con truco}: {¿te atreves?|¿cuál es la correcta?}",
    ),
}
BODY = {
    "pemdas": ("<eq> = ?",),
    "cubos": ("¿Cuántos cubos hay en total? {Cuenta también los que no se ven.|No olvides los que están escondidos.|Piensa en los que quedan tapados.}",),
    "fracciones": ("¿Qué fracción representa la región gris? {Respóndela simplificada.|Escríbela en su forma más simple.}",),
}
ASKS = {
    "pemdas": ("👇 {Dime|Escribe} qué resultado te sale {sin calculadora|y cómo lo calculaste|antes de mirar los comentarios}.",
               "👇 {Comenta tu respuesta|Escribe tu resultado} {sin hacer trampa|y cuéntame cómo lo pensaste}."),
    "cubos": ("👇 Escribe cuántos cubos hay {en total|y cómo los contaste|antes de mirar los comentarios}.",
              "👇 {Comenta tu número|Dime tu respuesta} {sin hacer trampa|y cuéntame cómo lo contaste}."),
    "fracciones": ("👇 Escribe la fracción {simplificada|en su forma más simple|antes de mirar los comentarios}.",
                   "👇 {Comenta tu respuesta|Dime qué fracción es} {sin hacer trampa|y cuéntame cómo la calculaste}."),
    "opciones": ("👇 Elige {A, B, C o D|una letra} {y cuéntame por qué|sin mirar los comentarios|y no hagas trampa}.",
                 "👇 {Comenta tu respuesta|Escribe tu letra} {antes de mirar los comentarios|y dime cómo lo pensaste}."),
}
SHARE = ("📤 {Mándaselo a quien crea que lo sabe.|Reta a un amigo: envíale esta imagen.|Compártelo con alguien a quien le "
         "encanten los retos.|Envíaselo a ese amigo que presume de listo.|Guárdalo y reta a alguien de tu familia.}",)
FOLLOW = ("➕ {Sigue la página|Sígueme|Sigue esta página} para {más retos como este|el reto de mañana|no perderte el "
          "siguiente}.", "➕ {Un reto nuevo cada día|Retos nuevos todos los días}: {sígueme|sigue la página} {y entrena tu "
          "mente|para no perdértelos}.")
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
    paste = f"{hook}\n\n{body}\n\n{ask}\n\n{pick(rng, SHARE)}\n{pick(rng, FOLLOW)}\n\n{' '.join(tags)}"
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
