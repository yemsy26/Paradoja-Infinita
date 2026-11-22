# Paradoja Infinita

[![CI](https://github.com/yemsy26/Paradoja-Infinita/actions/workflows/ci.yml/badge.svg)](https://github.com/yemsy26/Paradoja-Infinita/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Platform](https://img.shields.io/badge/tested%20on-Windows%2011-lightgrey.svg)

**Procedural short-form vertical video generator** (1080×1920, 60 fps, 63 s) built on GLSL shaders, neural
text-to-speech and NVENC hardware encoding. Designed for visual-challenge, optical-illusion and geometric-loop channels
(Facebook Reels / In-Stream and similar).

Every run starts from a **seed** that decides palette, shapes, timing structure, challenge type, narration script and
audio, so each video is structurally different yet fully **reproducible**.

> Language: [Español](README.md) · English

## Features

- **100 % GPU rendering** (headless OpenGL via [moderngl](https://github.com/moderngl/moderngl)); frames are piped
  straight into FFmpeg, nothing is written to disk as images.
- **NVENC encoding** (`h264_nvenc` / `hevc_nvenc`) with automatic fallback to `libx264`.
- **Free neural voice** via [edge-tts](https://github.com/rany2/edge-tts) with per-word timing for large, centered,
  karaoke-style subtitles.
- **Procedural audio** (drone + effects) synthesized with NumPy: no copyrighted music.
- **17 challenge types + mixed video + perfect loop**, with a smart picker that avoids repeating challenges, an
  interactive menu and a scriptable CLI.
- **Publish-ready metadata**: each video produces a `.txt` with title, description (with a comment call-to-action),
  hashtags and the challenge answers.
- Fixed **63 s** duration (valid range 61.5–65 s) to meet the In-Stream monetization minimum.

## Challenges

A **single-type** video repeats one challenge (4-7 rounds of rising difficulty). The **mixed** video combines 5-7
*different* challenges. Every video starts with the challenge at second 0, reveals each answer at the end of its round
and closes with a call to comment the score.

| Category | Challenge | Mechanic |
|---|---|---|
| Visual | Anomaly | Grid of shapes where one differs (color, size, brightness, dot, rotation) |
| Visual | Optical illusion | 10 illusions: Ouchi, café wall, Ebbinghaus, scintillating grid, spiral, moiré, Hermann, Müller-Lyer, Kanizsa and Zöllner; unmasked at the end |
| Visual | Vision test | Fluctuating Voronoi field hiding a number or shape through a slight tint difference |
| Visual | Magic eye | Real autostereogram, a different hidden 3D shape or two-digit number per round |
| Visual | Contrast | 4 variants (does it change? lighter or darker? which is darker? which is lighter?); the truth differs per round |
| Reflexes | Synchronization | A shape spins at extreme speed and fits a silhouette for **exactly one frame** |
| Attention | Swarm tracker | One red particle for 2 s, it blends in, the swarm mixes and stops |
| Attention | Counting | "How many blue triangles?" among moving shapes; the reveal numbers the right ones |
| Attention | Cups | The shell game: a ball under one cup, the cups swap faster and faster, the reveal shows where it ended |
| Attention | What changed | Two images flicker and one shape changes (color, size, rotation, disappears...) |
| Visual | Odd number | Grid of near-identical digits (8/0, 6/5, 9/3...) with one different; pairs get closer each round |
| Memory | Simon | Four numbered pads light up in sequence (3-6 steps); one step is asked and the reveal replays the sequence |
| Memory | Memory | Memorize for 3 s, blank screen, one shape changed |
| Mind | Stroop effect | Color words printed in a different ink: say the ink color |
| Mind | Math | Generated expressions with an order-of-operations trap |
| Mind | Sequence | "Which number comes next?" (17 families: arithmetic, geometric, squares, cubes, Fibonacci, interleaved, primes...; thousands of distinct series) |
| Mind | Riddle | 120+ riddles and trick questions from `content/acertijos.json` (editable) plus generated number riddles (ages, bat and ball, chimes...) that never repeat |
| Special | Infinite loop | Perfect geometric loop (last frame matches the first, audio included) |
| Special | Mixed | 5-7 different challenges in one video |

### Variety and anti-saturation

- **Generated content, not templates:** every expression, sequence, count, word set or board is new.
  Riddles come from `content/acertijos.json`; add your own as `{"q": "question", "a": "answer"}`.
- **Smart random:** for each video 24 candidate seeds are scored against `output/historial.json` and the one most
  different from recent uploads wins (challenge, format, palette, shape, riddle and title are all considered).
- The same seed + format always reproduces the same video.

## Requirements

| Component | Requirement |
|---|---|
| OS | Windows 10/11 (tested on Windows 11). Linux/macOS not verified |
| Python | 3.10+ (tested with 3.14) |
| FFmpeg / FFprobe | Recent version on `PATH`; NVENC needs a build with `nvenc` support (e.g. a *full build*) |
| GPU | Any OpenGL 3.3 GPU. NVIDIA RTX recommended for NVENC; otherwise `libx264` is used |
| Network | Only to synthesize speech with edge-tts (results are cached locally) |

## Installation

**Automatic (Windows):** double-click `iniciar.bat`. On first run it installs Python and FFmpeg through `winget` when
missing, creates `.venv`, installs `requirements.txt` and opens the menu. If `winget` installs something, close the
window and run it again so `PATH` refreshes.

**Manual:**

```powershell
git clone https://github.com/yemsy26/Paradoja-Infinita.git
cd Paradoja-Infinita
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
winget install -e --id Gyan.FFmpeg
```

## Usage

```powershell
python main.py                                    # interactive menu (option 1 = smart random, recommended)
python main.py --mode random --count 5            # five varied videos (smart pick)
python main.py --mode mix --count 3               # three mixed videos
python main.py --mode math --seed 12345           # one specific challenge, reproducible
python main.py --mode loop --duration 64 --voice en-US-GuyNeural --codec hevc_nvenc
```

| Option | Description | Default |
|---|---|---|
| `--mode` | `random`, `mix`, `loop` or a challenge: `anomaly`, `illusion`, `ishihara`, `magiceye`, `contrast`, `sync`, `swarm`, `count`, `flicker`, `memory`, `stroop`, `math`, `sequence`, `riddle`; skips the menu | menu |
| `--count` | Videos to generate with `--mode` | `1` |
| `--seed` | Integer seed; same seed + format = same video | most novel |
| `--duration` | Seconds (61.5–65) | `63` |
| `--voice` | edge-tts voice (`edge-tts --list-voices`) | `es-MX-JorgeNeural` |
| `--codec` | `auto`, `h264_nvenc`, `hevc_nvenc`, `libx264` | `auto` |
| `--out` | Output folder | `output` |
| `--keep-work` | Keep intermediate audio, subtitles and FFmpeg log | off |

> The narration scripts are written in Spanish. Other languages require adding a script module (see
> [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md)).

## Output

```text
output/<YYYY-MM-DD>/<mode>_<detail>_<seed>/<mode>_<detail>_<seed>.mp4
output/<YYYY-MM-DD>/<mode>_<detail>_<seed>/<mode>_<detail>_<seed>.txt   # title, description, hashtags, answers
```

## Development

```powershell
pip install -r requirements-dev.txt
python -m pytest
```

Tests cover the pure logic and need no GPU, FFmpeg or network. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Disclaimer

Provided "as is" without warranty. Speech is synthesized through the third-party, unofficial `edge-tts` library; review
its terms before commercial use. You are responsible for complying with the target platform's policies. This project is
not affiliated with Meta, Microsoft, NVIDIA or FFmpeg.

## License

[MIT](LICENSE). Created by [yemsy26](https://github.com/yemsy26).
