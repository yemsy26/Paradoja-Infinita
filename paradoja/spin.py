"""Text spinning determinista.

Una plantilla puede llevar grupos ``{opcion A|opcion B|opcion C}`` (anidables) y huecos ``<nombre>``. ``spin`` elige
una opcion de cada grupo con un ``random.Random`` ya sembrado (la semilla del video), asi que la misma semilla da
siempre el mismo texto y semillas distintas dan combinaciones distintas.

    >>> import random
    >>> spin(random.Random(7), "{Hola|Buenas}, <n> {retos|pruebas}.", n=5) in {
    ...     f"{a}, 5 {b}." for a in ("Hola", "Buenas") for b in ("retos", "pruebas")}
    True

Los grupos sin ``|`` (por ejemplo ``{N}``) no se tocan: no chocan con ``str.format``.
"""
import random
import re

_GROUP = re.compile(r"\{([^{}]*\|[^{}]*)\}")      # grupo mas interno que contiene al menos un '|'
_SLOT = re.compile(r"<(\w+)>")


def fill(text: str, **slots) -> str:
    """Sustituye los huecos <nombre> por su valor (los desconocidos se dejan igual)."""
    return _SLOT.sub(lambda m: str(slots.get(m.group(1), m.group(0))), text)


def spin(rng: random.Random, template: str, **slots) -> str:
    """Expande los grupos {a|b|c} con `rng.choice` y rellena los huecos."""
    while True:
        m = _GROUP.search(template)
        if not m:
            break
        template = template[:m.start()] + rng.choice(m.group(1).split("|")) + template[m.end():]
    out = re.sub(r"\s+([,.;:!?])", r"\1", fill(template, **slots))
    return re.sub(r"([?!])\.", r"\1", out).strip()


def pick(rng: random.Random, pool, **slots) -> str:
    """Elige una plantilla de la lista con `rng.choice` y la expande."""
    return spin(rng, rng.choice(pool), **slots)


def expand_all(template: str, limit: int = 50000) -> list:
    """Todas las variantes de una plantilla (para contarlas en las pruebas); se corta en `limit`."""
    out = [template]
    while True:
        nxt, done = [], True
        for t in out:
            m = _GROUP.search(t)
            if not m:
                nxt.append(t)
                continue
            done = False
            nxt += [t[:m.start()] + opt + t[m.end():] for opt in m.group(1).split("|")]
        out = nxt[:limit]
        if done:
            return out


def count_variants(pool) -> int:
    """Variantes distintas (ya expandidas) de todas las plantillas de una lista."""
    return len({v for t in pool for v in expand_all(t)})
