"""Subtitulos ASS: grandes, al centro, palabra activa resaltada + HUD, texto de los retos y cierre."""
import re
import textwrap
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
HOOK_Y = CAPTION_Y - 45          # centro de la ficha del gancho: algo mas arriba para no tocar la tarjeta del reto
_WHITE = r"{\c&HFFFFFF&}"
_POP = r"{\fscx78\fscy78\t(0,90,\fscx100\fscy100)}"


def _bgr(rgb) -> str:
    r, g, b = (round(max(0.0, min(1.0, c)) * 255) for c in rgb)
    return f"{b:02X}{g:02X}{r:02X}"


def _luma(bgr: str) -> float:
    """Luminosidad 0-1 de un color BGR en hexadecimal (para elegir texto claro u oscuro sobre una ficha)."""
    b, g, r = (int(bgr[i:i + 2], 16) for i in (0, 2, 4))
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


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


def _chip_color(bgr: str) -> str:
    """Ficha de color de acento con texto de alto contraste (oscuro sobre fondos claros)."""
    return r"\3c&H" + bgr + r"&\3a&H18&\c&H" + ("000000" if _luma(bgr) > 0.55 else "FFFFFF") + "&"


def _wrap_big(text: str, width: int = 24, max_size: int = 72, max_height: int = 230) -> tuple:
    """(texto en mayusculas con saltos ASS, tamaño): prueba varios anchos de linea y se queda con la letra mas grande
    que quepa en ~940 px de ancho y en `max_height` px de alto (asi una frase larga no invade otras filas)."""
    text, best = text.upper(), None
    for w in range(max(12, width - 8), width + 9):
        lines = textwrap.wrap(text, w)
        size = int(min(max_size, 940 / (0.66 * max(len(x) for x in lines))))
        fits = len(lines) * size * 1.2 <= max_height
        key = (fits, size if fits else -len(lines) * size)
        if best is None or key > best[0]:
            best = (key, lines, size)
    return r"\N".join(best[1]), best[2]


def _outro(start: float, end: float, cx: int, hl: str, question: str, cta: str) -> list:
    """Cierre: la llamada a seguir (la misma frase que se narra) en una ficha grande y la pregunta del reto debajo.
    No pide comentar ni compartir (cebo de interaccion): solo pregunta."""
    cta_text, cta_size = _wrap_big(cta, 22, 76, 290)
    rows = ((0.0, "Title", "", BRAND, 330),
            (0.0, "Cap", r"\fs" + str(cta_size) + _chip_color(hl), cta_text, 560),
            (0.5, "Cta", r"\fs64" + r"\c&H" + hl + "&", question, 790))
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
    if sc.hook:                                  # gancho: frase completa en una ficha mientras suena (el reto ya esta visible)
        text, size = _wrap_big(sc.hook)
        ev.append(_line(0.0, sc.lead if sc.lead > 0 else 3.4, "Cap",
                        "{" + r"\fs" + str(size) + _chip_color(hl) + r"\fad(0,150)}" + text, (cx, HOOK_Y)))
    if tl.is_loop:
        ev += _outro(spec.duration - sc.outro_len + 0.2, spec.duration - 0.1, cx, hl,
                     "¿CUÁNTAS VECES LO REPETISTE?", sc.cta)
    else:
        n = len(sc.acts)
        ev += _outro(tl.outro_start + 0.2, spec.duration - 0.1, cx, hl, f"¿CUÁNTOS DE {n} ACERTASTE?", sc.cta)
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
                if bgr and y <= CAPTION_Y:       # respuesta / debate: ficha de color de acento con texto de alto contraste
                    color = _chip_color(bgr)
                else:
                    color = r"\c&H" + bgr + "&" if bgr else ""
                # el enunciado del primer reto (texto central) ya se lee mientras suena el gancho; la pregunta fija y el
                # gancho comparten fila, asi que esa espera a que acabe la apertura
                pulled = a.index == 0 and y > CAPTION_Y and t0 <= 0.5
                fade = r"\fad(120,0)" if t0 > 0.05 and not pulled else r"\fad(0,150)"
                ev.append(_line(0.0 if pulled else a.start + t0, a.start + t1, "Cap" if y <= CAPTION_Y else "Big",
                                "{\\fs" + str(size) + color + fade + "}" + text, (cx, y)))

    path.write_text(_HEADER.format(w=spec.width, h=spec.height, hl=hl) + "\n".join(ev) + "\n", encoding="utf-8")
    return path
