"""Filtro de los textos que acaban en Facebook: ni menciones a la IA ni cebos de interaccion.

Meta reduce el alcance de lo que *pide* reacciones, comentarios, comparticiones o etiquetas («comenta X si...», «etiqueta a...»)
y de los ganchos con estadisticas inventadas o afirmaciones sobre «la mayoria» («el 99 % falla», «casi nadie acierta»). Este
modulo reune esos patrones en un solo sitio para:

* las pruebas (`tests/`): ningun gancho, titulo, descripcion, narracion ni ficha en pantalla puede coincidir con ellos;
* el autopiloto: ultima barrera antes de publicar; si el texto generado los contiene, se descarta y se genera otro.

`find_issues(texto)` devuelve la lista de problemas (vacia = texto limpio). Los patrones son deliberadamente estrictos: una frase
legitima que coincida se reescribe, no se relaja el filtro.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

_FLAGS = re.I | re.U
_W = r"[\wÁ-ú]"                                    # caracteres de palabra (incluye tildes y ñ)

# --------------------------------------------------------------------------- menciones a la IA
AI_PATTERNS = {
    "IA": rf"(?<!{_W})(?:IA|AI|A\.I\.)(?!{_W})",
    "inteligencia artificial": r"inteligencia\s+artificial|artificial(?:es|mente)?\b|machine\s+learning",
    "voz sintética": r"sint[eé]tic[oa]s?\b|neuronal(?:es)?\b|voz\s+(?:generada|robot)",
    "modelo": r"chat\s?gpt|\bgpt\b|midjourney|deepfake|\brobots?\b|\bbots?\b",
    "generado": r"generad[oa]s?\s+(?:por|con|mediante)\s+(?:ia|ai|inteligencia|ordenador|computadora|algoritmo|m[aá]quina)",
}

# --------------------------------------------------------------------------- cebos de interaccion y ganchos engañosos
BAIT_PATTERNS = {
    "estadística inventada": (
        r"\d+\s?%|\bpor\s+ciento\b|\buno\s+por\s+ciento\b|"
        r"\b(?:\d+|uno|una|dos|tres|cuatro|cinco|diez|veinte|cincuenta)\s+de\s+cada\s+(?:\d+|uno|una|dos|tres|cuatro|cinco|diez|veinte|cincuenta)\b"),
    "afirmación sobre la mayoría": (
        r"\bla\s+mayor[ií]a\b|\bcasi\s+(?:nadie|todos|todo\s+el\s+mundo)\b|\bmuy\s+(?:poca\s+gente|pocos|poquit[oa]s)\b|"
        r"\bpoqu[ií]sima\s+gente\b|\bpoca\s+gente\b|\bpocos\s+(?:lo\s+)?(?:consiguen|logran|aciertan|resuelven|pasan|ven|saben)\b|"
        r"\b(?:muchos|mucha\s+gente|la\s+gente|todos|casi\s+todos)\s+(?:dicen|dice|responden?|calculan|resuelven|cuentan|se\s+equivocan?|"
        r"fallan?|caen|piensan|creen|cometen|suman|contestan)\b|"
        r"\bnadie\s+(?:lo\s+)?(?:logra|acierta|resuelve|encuentra|sabe|se\s+libra|se\s+salva|consigue|pasa|llega|ha\s+logrado)\b"),
    "solo los elegidos": (
        rf"\bsolo\s+(?:los|las|el|la|un|una|quien|quienes)\s+(?:m[aá]s\s+)?(?:atent|list|pacient|genio|valient|inteligent|r[aá]pid|"
        rf"observador|agud|capaz|capac)|\bsolo\s+(?:si\s+tienes|un\s+genio|alguien\s+muy)|\bIQ\b|\beres\s+(?:un\s+)?genio\b|"
        r"\beres\s+de\s+los\s+pocos\b|\bde\s+los\s+pocos\b|\beres\s+especial\b"),
    "pide comentar": (
        r"\bcoment(?:a|ar|e|en|alo|arlo|ario|arios)\b|\bcoméntal\w*|\bcomentarios?\b|\bresp[oó]ndeme\b|\bdime\b|\bd[ií]melo\b|"
        r"\bcu[eé]ntame\b|\bcu[eé]ntamelo\b|\bescr[ií]benos\b|(?<!se\s)\bescribe\s+(?:tu|tus|cu[aá]nt\w*|qu[eé]|en\s+los)\b|"
        r"\bresponde\s+(?:solo|con\s+(?:un|una|el|tu|s[ií]|no)\b|en\s+los|abajo)|\bresp[oó]ndelo\b|\babajo\b.{0,12}\b(?:tu|su)\b"),
    "pide compartir o enviar": (
        r"\bcomp[aá]rt(?:elo|ela|elos|elas|e|ir|id|an)\b|\bcomparte\b|\bm[aá]nd[aá]\w*(?:elo|ela|selo|sela)\b|"
        r"\benv[ií][aá]\w*(?:elo|ela|selo|sela)\b|"
        r"\breta\s+a\b|\bretal[eo]\b|\bpasa(?:selo|lo)\s+a\b"),
    "pide etiquetar o mencionar": r"\betiquet\w*|\bmenciona\w*|\btaguea\w*|\btag\s+a\b",
    "pide guardar, dar like o suscribirse": (
        r"\bguárdal\w*|\bguarda\s+(?:este|esto|el\s+(?:video|reto|post)|esta)\b|\bdale\s+(?:a\s+)?(?:like|me\s+gusta|al\s+corazón)\b|\bme\s+gusta\b|"
        r"\blikes?\b|\bsuscr[ií]b\w*|\bcampanita\b|\breacciona\w*|\bvota\b|\bvotad?\b"),
    "icono de cebo": r"[👇📤➕❤👍🔔]",
}
# Pedir seguir la pagina no es un cebo, pero se descarta en el texto de las publicaciones (lo que se publica va centrado en el reto).
FOLLOW_PATTERNS = {
    "pide seguir": (r"\bs[ií]gueme\b|\bs[ií]guenos\b|\bs[ií]guenos\b|\bsigue\s+(?:la|esta|mi|nuestra)\s+(?:p[aá]gina|cuenta)\b|"
                    r"\bsegu[ií]r(?:me|nos)\b|\bdale\s+a\s+seguir\b|\bpulsa\s+seguir\b|\bno\s+te\s+vayas\s+sin\b"),
}


def _compile(table: dict) -> dict:
    return {name: re.compile(rx, _FLAGS | re.S) for name, rx in table.items()}


_AI, _BAIT, _FOLLOW = _compile(AI_PATTERNS), _compile(BAIT_PATTERNS), _compile(FOLLOW_PATTERNS)


def find_issues(text: str, *, allow_follow: bool = False) -> list:
    """Problemas de un texto: lista de `(categoria, fragmento)`. Con `allow_follow` se admite una invitacion simple a seguir."""
    out = []
    tables = [_AI, _BAIT] + ([] if allow_follow else [_FOLLOW])
    for table in tables:
        for name, rx in table.items():
            out += [(name, m.group(0)) for m in rx.finditer(text or "")]
    return out


def first_issue(texts: Iterable[str], *, allow_follow: bool = False) -> str | None:
    """Descripcion corta del primer problema que haya en una coleccion de textos (None = todo limpio)."""
    for text in texts:
        found = find_issues(text, allow_follow=allow_follow)
        if found:
            name, frag = found[0]
            return f"{name}: «{frag}»"
    return None
