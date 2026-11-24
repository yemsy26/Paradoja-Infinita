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
- **Autopilot** (`autopiloto.py`): keeps running and publishes by itself to your Page (an image in the morning, a Reel in the
  afternoon) through Meta's Graph API, with random jitter, an error log and no duplicates (see `docs/AUTOPILOTO.md`).
- **Static feed images** (`generador_imagenes.py`): 4 viral 1080x1350 challenges drawn with Pillow (no generative AI),
  each with a paste-ready copy and the hidden correct answer for your own control.
- **Unique text per video (text spinning):** the opening hook, the closing follow call-to-action, the debate lines
  of riddles and math, the title, the description and the hashtags are assembled from fragments picked by the seed (see
  [Unique text](#unique-text-text-spinning)); the post text is never repeated.
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

## Feed images

`generador_imagenes.py` (or `iniciar_imagenes.bat` on Windows) draws **1080x1350 still images** meant to make people
comment their answer and follow the page. They are drawn with Pillow (perfect text, 1-2 s each). Run it without
arguments for a menu, or script it:

```text
python generador_imagenes.py --modo aleatorio --count 5
python generador_imagenes.py --modo cubos --seed 42 --estilo montserrat --formato jpg
```

Modes: `pemdas` (order-of-operations equation, "the answer is NOT 0!"), `cubos` (isometric cube stack with hidden cubes),
`fracciones` (polygon split into triangles, "what fraction is gray?") and `opciones` (look-alike Roman numerals, number
sequences and classic trick questions). Each image goes to `output_imagenes/YYYY-MM-DD/` with a `.txt` holding the copy
to paste, the **correct answer** (internal control), the explanation, the most common wrong answer, a comment to reveal the
solution later and the alt text. Challenge and copy come from the seed and are logged in `output_imagenes/historial.json`
so nothing repeats. Put your `.ttf` fonts (Montserrat, Poppins, Comic Neue, Anton...) in `fonts/` and pick one with
`--estilo` or `--fuente`. The copy asks a question and asks to follow the page; avoid "comment YES/NO", "tag 3 friends" or
"share to win" (Meta treats them as engagement bait).

## Autopilot

`autopiloto.py` generates and **publishes to your Facebook Page** through the official Graph API: images and Reels
in the time slots you configure (`HORARIOS_FOTOS=11:30,17:00`, `HORARIOS_VIDEOS=18:00`, with separate daily caps
`MAX_FOTOS_DIA` / `MAX_VIDEOS_DIA`), each delayed by a random 1-15 minutes. It reads `PAGE_ID` and `PAGE_ACCESS_TOKEN` from a `.env` file (copy
`.env.example`; never commit it). Use `--check` to test the token, `--dry-run --ahora foto` to rehearse without publishing and
no arguments to run the daily schedule. Render or API failures go to `autopiloto.log` and the program keeps running; what was
published each day (files, post ids, executed/skipped slots) is saved atomically in `estado_autopiloto.json`: after a closed
program or a Windows reboot it schedules only the pending slots within the daily caps, so nothing is duplicated
(`--estado` prints today's summary without touching anything). Reels follow the official three-phase
flow (start, resumable upload, finish); the AI label is off by default (`IA_ETIQUETA=0` never sends `is_ai_generated`). Setup and troubleshooting: `docs/AUTOPILOTO.md`
(Spanish). The random delay is cosmetic: it does not protect against Meta's originality and spam policies.

## Unique text (text spinning)

Everything that is spoken or shown comes from template lists in `paradoja/copy_es.py`, expanded by `paradoja/spin.py`
with the seed's `random.Random`: the same seed gives the same video, different seeds give different text. A template
accepts `{option A|option B}` groups (nestable) and slots such as `<n>` or `<ans>`.

| Piece | Where | Variants |
|---|---|---|
| **Opening hook** (2.5-4.4 s) | Narrated from 0.15 s and burned as a large chip while the first challenge sits still and visible | 600+ |
| **Follow call-to-action** (last 4-5 s) | Narrated and burned on screen; every variant asks to follow | 290+ |
| **Debate** (riddles, math) | At the reveal: "Many say X, but it is Y. What do you think?" plus an on-screen chip | dozens per challenge |
| **Title, description, footers, pinned comment, hashtags** | `<name>.txt` and `<name>_publicar.txt` | thousands of combinations |

The debate only states true things: the "X vs Y" confrontation is used when a real trap exists (the typical wrong
answer, optional `"t"` field in `content/acertijos.json`); otherwise the viewer is simply asked. Each post stores a
fingerprint in `output/historial.json` and is recomposed if it would match a recent one.

Varying the text lowers repetition but is not enough by itself for Meta's original-content and spam policies: publishing
many near-identical videos a day can still be treated as repetitive. Keep a sane posting pace, avoid links, use at most
5 hashtags. The generated copy asks neither for comments, shares nor tags and makes no "99% fail" claims
(`paradoja/copy_guard.py`), and the autopilot keeps at least `MIN_INTERVALO_MINUTOS` (180 by default) between any two
posts and avoids repeating the same challenge template the same day.

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
