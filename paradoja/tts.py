"""TTS neuronal gratuito (edge-tts) con tiempos por palabra y ajuste de velocidad al hueco disponible."""
import asyncio
import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import edge_tts

from .script_es import Segment

MAX_RATE = 45  # % maximo de aceleracion


@dataclass
class Word:
    text: str
    start: float   # relativo al clip
    end: float


@dataclass
class Clip:
    path: Path
    start: float   # absoluto en el video
    duration: float
    words: list
    text: str


def _probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def _estimate_words(text: str, duration: float) -> list:
    toks = text.split()
    total = sum(len(t) for t in toks) or 1
    words, t = [], 0.0
    for tok in toks:
        d = duration * len(tok) / total
        words.append(Word(tok, t, t + d))
        t += d
    return words


async def _synth(text: str, voice: str, rate: int, cache: Path) -> tuple:
    key = hashlib.sha1(f"{voice}|{rate}|{text}".encode()).hexdigest()[:16]
    mp3, meta = cache / f"{key}.mp3", cache / f"{key}.json"
    if mp3.exists() and meta.exists():
        return mp3, [Word(**w) for w in json.loads(meta.read_text("utf-8"))]

    for attempt in range(4):
        try:
            comm = edge_tts.Communicate(text, voice, rate=f"{rate:+d}%", boundary="WordBoundary")
            words = []
            with mp3.open("wb") as f:
                async for ch in comm.stream():
                    if ch["type"] == "audio":
                        f.write(ch["data"])
                    elif ch["type"] == "WordBoundary":
                        s = ch["offset"] / 1e7
                        words.append(Word(ch["text"], s, s + ch["duration"] / 1e7))
            break
        except Exception:
            if attempt == 3:
                raise
            await asyncio.sleep(1.5 * (attempt + 1))
    if not words:
        words = _estimate_words(text, _probe_duration(mp3))
    meta.write_text(json.dumps([w.__dict__ for w in words]), "utf-8")
    return mp3, words


async def _build(segments: list, voice: str, cache: Path, end_time: float) -> list:
    sem = asyncio.Semaphore(4)
    inflight = {}

    async def get(text, rate):
        k = (text, rate)
        if k not in inflight:
            async def run():
                async with sem:
                    return await _synth(text, voice, rate, cache)
            inflight[k] = asyncio.ensure_future(run())
        return await inflight[k]

    def effective(mp3, words):  # edge-tts añade silencio al final: medir hasta la ultima palabra
        return min(_probe_duration(mp3), words[-1].end + 0.25)

    async def one(i, seg):
        slot = (segments[i + 1].start if i + 1 < len(segments) else end_time) - seg.start - 0.12
        mp3, words = await get(seg.text, 0)
        dur = effective(mp3, words)
        rate = 0
        while dur > slot and rate < MAX_RATE:  # re-sintetizar mas rapido para caber en el hueco
            rate = min(MAX_RATE, rate + int((dur / slot - 1) * 100) + 5)
            mp3, words = await get(seg.text, rate)
            dur = effective(mp3, words)
            if dur > slot:
                print(f"  aviso: '{seg.text[:30]}...' dura {dur:.2f}s > hueco {slot:.2f}s")
        return Clip(mp3, seg.start, dur, words, seg.text)

    return await asyncio.gather(*(one(i, s) for i, s in enumerate(segments)))


def synthesize_all(segments: list[Segment], voice: str, cache_dir: Path, end_time: float) -> list:
    cache_dir.mkdir(parents=True, exist_ok=True)
    return asyncio.run(_build(segments, voice, cache_dir, end_time))
