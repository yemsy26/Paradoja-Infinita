"""Cama sonora procedural (drone + efectos) sin material con copyright."""
import wave
from pathlib import Path

import numpy as np

SR = 48000


def _env(n, decay):
    return np.exp(-np.arange(n) / SR * decay)


def _sfx(kind: str, rng) -> np.ndarray:
    if kind == "tick":
        n = int(0.08 * SR); t = np.arange(n) / SR
        return 0.22 * np.sin(2 * np.pi * 1300 * t) * _env(n, 55)
    if kind == "ding":
        n = int(0.9 * SR); t = np.arange(n) / SR
        return 0.25 * (np.sin(2 * np.pi * 880 * t) + 0.6 * np.sin(2 * np.pi * 1320 * t)) * _env(n, 5)
    if kind == "chime":
        n = int(2.0 * SR); t = np.arange(n) / SR
        return 0.2 * sum(np.sin(2 * np.pi * f * t) for f in (660, 990, 1320)) * _env(n, 2.5)
    n = int(0.55 * SR)  # whoosh: ruido filtrado con envolvente
    noise = np.convolve(rng.standard_normal(n), np.ones(40) / 40, mode="same")
    return 0.9 * noise * np.sin(np.linspace(0, np.pi, n)) ** 2


def build_bed(path: Path, duration: float, sfx_events: list, seed: int, loop: bool = False) -> Path:
    rng = np.random.default_rng(seed)
    n = int(duration * SR)
    t = np.arange(n) / SR
    root = 55.0 * 2 ** (int(rng.integers(0, 12)) / 12)
    # En bucle, todas las frecuencias se ajustan a un nº entero de ciclos en `duration` (audio sin salto)
    snap = (lambda f: round(f * duration) / duration) if loop else (lambda f: f)

    out = np.zeros((n, 2))
    for ch, detune in enumerate((1.0, 1.003)):
        vib = 0.002 * np.sin(2 * np.pi * snap(0.2) * t + ch)
        sig = sum(a * np.sin(2 * np.pi * snap(root * m * detune) * t + m + 40 * vib)
                  for m, a in ((1, 1.0), (1.5, 0.6), (2, 0.5), (3, 0.25)))
        out[:, ch] = 0.05 * sig * (0.75 + 0.25 * np.sin(2 * np.pi * snap(1 / 7.0) * t))

    for when, kind in sfx_events:
        s = _sfx(kind, rng)
        i = int(when * SR)
        j = min(n, i + len(s))
        if j > i:
            out[i:j] += s[: j - i, None] * 0.5

    if not loop:
        out *= np.clip((duration - t) / 1.2, 0, 1)[:, None]  # fade-out final
    out /= max(1.0, np.abs(out).max() / 0.8)
    pcm = (out * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path
