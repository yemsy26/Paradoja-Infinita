"""Historial de imagenes (`historial.json` dentro de la carpeta de salida): evita repetir retos y textos."""
from __future__ import annotations

import json
import random
from pathlib import Path

from .puzzles import MODES

HISTORY_FILE = "historial.json"


def load(out_dir: Path) -> list:
    try:
        data = json.loads((Path(out_dir) / HISTORY_FILE).read_text("utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def append(out_dir: Path, entry: dict) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    hist = load(out_dir)
    hist.append(entry)
    (out_dir / HISTORY_FILE).write_text(json.dumps(hist, ensure_ascii=False, indent=1), "utf-8")


def recent_keys(history: list, n: int = 600) -> set:
    """Firmas de los retos ya usados (la misma ecuacion, apilamiento, fraccion o pregunta no se repite)."""
    return {e["key"] for e in history[-n:] if e.get("key")}


def recent_posts(history: list, n: int = 1000) -> set:
    return {e["post"] for e in history[-n:] if e.get("post")}


def pick_mode(history: list, rng: random.Random, window: int = 16) -> str:
    """Aleatorio inteligente: el tipo menos usado entre las ultimas imagenes (empates al azar)."""
    used = [e.get("mode") for e in history[-window:]]
    counts = {m: used.count(m) for m in MODES}
    low = min(counts.values())
    return rng.choice([m for m in MODES if counts[m] == low])


def stats(history: list) -> list:
    if not history:
        return ["Todavía no has generado imágenes."]
    lines = [f"Imágenes generadas: {len(history)}"]
    for m in MODES:
        lines.append(f"  {m:<11} {sum(e.get('mode') == m for e in history)}")
    lines.append("Últimas: " + ", ".join(e.get("slug", "?") for e in history[-5:]))
    return lines
