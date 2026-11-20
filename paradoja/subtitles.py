"""Subtitulos ASS: grandes, al centro, palabra activa resaltada + HUD, texto de los retos y llamada a comentar."""
import re
from pathlib import Path

from .config import BRAND, CAPTION_Y, HUD_Y, VideoSpec
from .scene import TYPES
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
Style: Big,Arial Black,120,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,10,3,5,40,40,0,1
Style: Cap,Arial Black,50,&H00FFFFFF,&H00FFFFFF,&H99000000,&H00000000,0,0,0,0,100,100,0,0,3,12,0,5,40,40,0,1
Style: Cta,Arial Black,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,8,3,5,40,40,0,1

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


def _outro(start: float, end: float, cx: int, hl: str, question: str) -> list:
    """Cierre: nota (comentarios), compartir (envios privados) y seguir; aparecen escalonados."""
    accent = r"\c&H" + hl + "&"
    rows = ((0.0, "Title", "", BRAND, 340),
            (0.0, "Cta", r"\fs54", question, 520),
            (0.35, "Cta", r"\fs72" + accent, "COMENTA TU NOTA", 650),
            (1.0, "Cta", r"\fs40", "ENVÍASELO A QUIEN NO LO ACIERTE", 770),
            (1.6, "Cta", r"\fs40" + accent, "SÍGUENOS · RETO NUEVO CADA DÍA", 840))
    return [_line(min(start + dt, end - 0.3), end, style, "{" + over + r"\fad(150,0)}" + text, (cx, y))
            for dt, style, over, text, y in rows]


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
        ev += _outro(spec.duration - 3.3, spec.duration - 0.1, cx, hl, r"¿CUÁNTAS VECES\NLO REPETISTE?")
    else:
        n = len(sc.acts)
        ev += _outro(tl.outro_start + 0.2, spec.duration - 0.1, cx, hl, f"¿CUÁNTOS DE {n} ACERTASTE?")
        for a in sc.acts:
            info = TYPES[a.type]
            label = f"{info.hud} {a.index + 1}/{n}" + (" · FINAL" if a.index == n - 1 and n > 1 else "")
            ev.append(_line(a.start + 0.15, a.end - 0.4, "Hud", r"{\fs46}" + label, (70, HUD_Y)))
            if info.countdown:
                for k in range(min(5, int(a.search)), 0, -1):  # el numero k dura mientras faltan k segundos
                    t0 = a.start + a.search - k
                    ev.append(_line(t0, t0 + 1, "Hud",
                                    r"{\an9\fs96\c&H" + hl + r"&\fscx70\fscy70\t(0,120,\fscx100\fscy100)}" + str(k),
                                    (spec.width - 50, HUD_Y - 12)))
            for t0, t1, text, size, bgr, y in a.items:           # texto del reto (calculo, secuencia, palabras...)
                color = r"\c&H" + bgr + "&" if bgr else ""
                fade = r"\fad(120,0)" if t0 > 0.05 else r"\fad(0,150)"    # el primer fotograma ya lleva texto
                ev.append(_line(a.start + t0, a.start + t1, "Cap" if y <= CAPTION_Y else "Big",
                                "{\\fs" + str(size) + color + fade + "}" + text, (cx, y)))

    path.write_text(_HEADER.format(w=spec.width, h=spec.height, hl=hl) + "\n".join(ev) + "\n", encoding="utf-8")
    return path
