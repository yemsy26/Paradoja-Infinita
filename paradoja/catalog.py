"""Historial de videos y eleccion inteligente: evita saturar el canal repitiendo el mismo tipo de reto."""
import json
import random
import secrets
from collections import Counter
from datetime import date
from pathlib import Path

from .config import VideoSpec
from .scene import MODES, TYPES, Scene, build_scene

HISTORY_FILE = "historial.json"
MIX_BONUS = 1.1
WEIGHTS = {"mix": 3.0, "loop": 0.7}   # el video mixto sale mas a menudo; el bucle, menos


def load_history(out_dir: Path) -> list:
    try:
        data = json.loads((out_dir / HISTORY_FILE).read_text("utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def entry_for(sc: Scene, slug: str, title: str, post: str = "") -> dict:
    return {"date": date.today().isoformat(), "seed": sc.seed, "mode": sc.mode, "slug": slug, "title": title, "post": post,
            "types": sorted({a.type for a in sc.acts}) or ["loop"], "palette": sc.palette.name, "shape": sc.shape,
            "riddles": [a.sym for a in sc.acts if a.type == "riddle" and a.sym >= 0]}   # -1 = acertijo generado


def append_history(out_dir: Path, entry: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    hist = load_history(out_dir)
    hist.append(entry)
    (out_dir / HISTORY_FILE).write_text(json.dumps(hist, ensure_ascii=False, indent=1), "utf-8")


def recent_titles(history: list, n: int = 80) -> list:
    return [e.get("title", "") for e in history[-n:]]


def recent_posts(history: list, n: int = 1000) -> set:
    """Huellas de los textos de publicacion ya usados (para no repetir nunca el mismo copy)."""
    return {e["post"] for e in history[-n:] if e.get("post")}


def pick_mode(mode: str, seed: int) -> str:
    """'random' -> el formato lo decide la semilla (reproducible)."""
    if mode != "random":
        return mode
    return random.Random(seed ^ 0xA5A5).choices(MODES, [WEIGHTS.get(m, 1.0) for m in MODES])[0]


def novelty(sc: Scene, history: list) -> float:
    """Cuanto mas alto, mas distinto de lo publicado recientemente."""
    recent = history[-30:]
    uses = Counter(t for e in recent for t in e.get("types", []))
    types = {a.type for a in sc.acts} or {"loop"}
    score = 3.0 * sum(1.0 / (1 + uses[t]) for t in types) / len(types)
    if sc.mode == "mix":
        score += MIX_BONUS   # los videos mixtos retienen mejor y combinan mas: se prefieren
    last_modes = [e["mode"] for e in recent[-3:]]
    if last_modes and sc.mode == last_modes[-1]:
        score -= 3.0
    elif sc.mode in last_modes:
        score -= 1.5
    if recent and sc.palette.name == recent[-1].get("palette"):
        score -= 1.0
    if recent and sc.shape == recent[-1].get("shape"):
        score -= 0.5
    used = {r for e in history[-100:] for r in e.get("riddles", [])}
    score -= 4.0 * sum(a.sym in used for a in sc.acts if a.type == "riddle")
    return score


def choose(mode: str, history: list, spec: VideoSpec, tries: int = 24, avoid=()) -> tuple:
    """Entre `tries` semillas candidatas elige la mas novedosa. -> (semilla, formato). Los formatos de `avoid` (p. ej. los ya
    publicados hoy) se descartan al sortear las candidatas; solo si no hay ninguna otra posible se usan igualmente."""
    avoid = set(avoid)
    cands = []
    for _ in range(tries * 60):                           # sortea candidatas que no repitan formato
        seed = secrets.randbits(32)
        m = pick_mode(mode, seed)
        if m not in avoid:
            cands.append((seed, m))
            if len(cands) >= tries:
                break
    while not cands:                                      # todos los formatos posibles estaban evitados
        seed = secrets.randbits(32)
        cands = [(seed, pick_mode(mode, seed))]
    best, best_score = None, -1e9
    for seed, m in cands:
        score = novelty(build_scene(seed, m, spec), history) + random.random() * 0.3
        if score > best_score:
            best, best_score = (seed, m), score
    return best


def stats(history: list) -> list:
    if not history:
        return ["Aún no hay videos generados."]
    counts = Counter(t for e in history for t in e.get("types", []))
    lines = [f"Videos generados: {len(history)}", "Retos usados (actos por tipo, de más a menos):"]
    for t, c in counts.most_common():
        lines.append(f"   {TYPES[t].menu if t in TYPES else t:<18} {c}")
    never = [TYPES[t].menu for t in TYPES if t not in counts]
    if never:
        lines.append("Sin usar todavía: " + ", ".join(never))
    lines.append("Últimos videos:")
    for e in history[-8:]:
        lines.append(f"   {e['date']}  {e['slug']}")
    return lines
