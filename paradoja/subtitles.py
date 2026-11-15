"""Subtitulos ASS: grandes, al centro, palabra activa resaltada (color de la paleta) + HUD."""
import re
from pathlib import Path

from .config import BRAND, VideoSpec
from .scene import HAS_COUNTDOWN, HUD_LABEL
from .timeline import Timeline

_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Arial Black,100,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,9,3,5,50,50,0,1
Style: Hud,Arial Black,62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,5,2,7,0,0,0,1
Style: Title,Arial Black,92,&H00{hl},&H00{hl},&H00000000,&H80000000,0,0,0,0,100,100,2,0,1,7,3,8,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
_WHITE = r"{\c&HFFFFFF&}"
_POP = r"{\fscx78\fscy78\t(0,90,\fscx100\fscy100)}"


def _bgr(rgb) -> str:
    r, g, b = (round(max(0.0, min(1.0, c)) * 255) for c in rgb)
    return f"{b:02X}{g:02X}{r:02X}"


def _ts(t: float) -> str:
    cs = round(max(0.0, t) * 100)
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _line(start, end, style, text, pos=None):
    p = f"{{\\pos({pos[0]},{pos[1]})}}" if pos else ""
    return f"Dialogue: 0,{_ts(start)},{_ts(end)},{style},,0,0,0,,{p}{text}"


def _tokens(clip) -> list:
    """Palabras con puntuacion original alineadas a los tiempos del TTS."""
    orig = clip.text.split()
    if len(orig) == len(clip.words):
        return [(o, w.start, w.end) for o, w in zip(orig, clip.words)]
    return [(w.text, w.start, w.end) for w in clip.words]


def _chunks(tokens, max_words=3, max_chars=13):
    cur, out = [], []
    for tok in tokens:
        if cur and (len(cur) >= max_words or sum(len(x[0]) + 1 for x in cur) + len(tok[0]) > max_chars):
            out.append(cur)
            cur = []
        cur.append(tok)
        if re.search(r"[.?!]$", tok[0]):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def build_ass(path: Path, clips: list, tl: Timeline, spec: VideoSpec) -> Path:
    sc = tl.scene
    hl = _bgr(sc.palette.accent)
    yellow = r"{\c&H" + hl + "&}"
    ev = []
    for clip in clips:
        chunks = _chunks(_tokens(clip))
        for ci, chunk in enumerate(chunks):
            words = [w[0].replace("{", "").replace("}", "").upper() for w in chunk]
            chunk_end = chunk[-1][2]
            if ci + 1 < len(chunks):
                chunk_end = max(chunk_end, chunks[ci + 1][0][1] - 0.02)
            for wi, (_, ws, _we) in enumerate(chunk):
                end = chunk[wi + 1][1] if wi + 1 < len(chunk) else chunk_end + 0.08
                if wi + 1 == len(chunk) and ci + 1 < len(chunks):
                    end = min(end, chunks[ci + 1][0][1])      # sin solapar con el siguiente bloque
                text = " ".join((yellow + w + _WHITE) if k == wi else w for k, w in enumerate(words))
                ev.append(_line(clip.start + ws, clip.start + end, "Sub", (_POP if wi == 0 else "") + text))

    cx = spec.width // 2
    if tl.is_loop:
        ev.append(_line(spec.duration - 3.0, spec.duration - 0.1, "Title", BRAND, (cx, 300)))
    else:
        label = HUD_LABEL[sc.mode]
        n = len(sc.acts)
        ev.append(_line(0.2, tl.hook_len - 0.3, "Title", BRAND, (cx, 300)))
        ev.append(_line(tl.outro_start + 0.2, spec.duration - 0.1, "Title", BRAND, (cx, 300)))
        for a in sc.acts:
            s = tl.act_start(a.index)
            ev.append(_line(s + 0.15, s + tl.act_len - 0.4, "Hud", f"{label} {a.index + 1}/{n}", (70, 110)))
            for k in (range(5, 0, -1) if sc.mode in HAS_COUNTDOWN else ()):  # el numero k dura mientras faltan k s
                t0 = s + tl.search_len - k
                ev.append(_line(t0, t0 + 1, "Hud",
                                r"{\an9\fs130\c&H" + hl + r"&\fscx70\fscy70\t(0,120,\fscx100\fscy100)}" + str(k),
                                (spec.width - 70, 80)))

    path.write_text(_HEADER.format(w=spec.width, h=spec.height, hl=hl) + "\n".join(ev) + "\n", encoding="utf-8")
    return path
