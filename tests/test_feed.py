"""Pruebas del generador de imagenes del feed: logica de los retos, dibujo, textos de publicacion, archivos y menu."""
import random
import re
from fractions import Fraction
from types import SimpleNamespace

import pytest

pytest.importorskip("PIL")

import numpy as np  # noqa: E402

import generador_imagenes as gi  # noqa: E402
from paradoja.feed import copy_feed, history as hist, puzzles as P  # noqa: E402
from paradoja.feed.canvas import PALETTES, contrast  # noqa: E402
from paradoja.feed.fonts import FontKit, covers  # noqa: E402
from paradoja.feed.render import render  # noqa: E402
from paradoja.feed.studio import generate_one  # noqa: E402
from paradoja.spin import expand_all  # noqa: E402

SEEDS = (1, 7, 42, 123, 998877)


@pytest.fixture(scope="module")
def kit():
    return FontKit()


# --------------------------------------------------------------------------- 1. PEMDAS
def test_pemdas_example_from_the_brief():
    toks = [7, "÷", 7, "−", 7, "×", 7]
    assert P.evaluate(toks) == -48 and P.evaluate(toks, ltr=True) == -42
    assert P.steps(toks) == "7 ÷ 7 − 7 × 7 = 1 − 7 × 7 = 1 − 49 = −48"
    assert P.evaluate([8, "−", "(", 2, "+", 3, ")", "×", 2]) == -2             # los parentesis mandan
    assert P.evaluate([6, "÷", 2, "×", 3]) == 9 and P.evaluate([6, "÷", 2, "×", 3], ltr=True) == 9   # × y ÷ van de izq. a der.


@pytest.mark.parametrize("seed", range(1, 151))
def test_pemdas_puzzles_are_valid_and_have_a_real_trap(seed):
    p = P.generate("pemdas", seed)
    toks = p.data["tokens"]
    right, naive = P.evaluate(toks), P.evaluate(toks, ltr=True)
    assert right != naive and right.denominator == 1 and naive.denominator == 1
    assert p.answer == str(int(right)).replace("-", "−") and p.trap == str(int(naive)).replace("-", "−")
    assert abs(right) <= 999 and p.data["eq"] == P.fmt_tokens(toks)
    assert set(p.data["eq"]) & set("×÷") and set(p.data["eq"]) & set("+−")
    assert P.steps(toks).endswith(p.answer)


def test_pemdas_is_deterministic_and_avoids_used_equations():
    a, b = P.generate("pemdas", 5), P.generate("pemdas", 5)
    assert a == b
    c = P.generate("pemdas", 5, {a.key})
    assert c.key != a.key


# --------------------------------------------------------------------------- 2. cubos
def test_cube_visibility_known_cases():
    one = P.analyse(((1,),))
    assert one["area"][(0, 0, 0)] >= 0.99 * one["face"] * 3                    # un cubo suelto: se ven sus 3 caras
    solid = P.analyse(((2, 2), (2, 2)))
    assert solid["area"][(0, 0, 0)] < 0.12 * solid["face"]                     # el cubo del fondo y abajo queda oculto
    assert solid["area"][(1, 1, 1)] > 2.9 * solid["face"]                      # el de delante y arriba se ve entero


@pytest.mark.parametrize("seed", range(1, 41))
def test_cube_puzzles_have_hidden_cubes_and_every_column_visible(seed):
    p = P.generate("cubos", seed)
    h = p.data["heights"]
    info = P.analyse(h)
    total = sum(map(sum, h))
    assert p.answer == str(total) and 8 <= total <= 26 and len(info["order"]) == total
    assert p.extra["hidden"] >= 1 and p.extra["visible"] + p.extra["hidden"] == total
    assert p.trap == str(p.extra["visible"]) and p.trap != p.answer           # la trampa: contar solo los que se ven
    for y, row in enumerate(h):
        for x, height in enumerate(row):
            if height:
                assert info["area"][(x, y, height - 1)] >= 0.55 * info["face"]    # cada columna se ve por arriba


# --------------------------------------------------------------------------- 3. fracciones
@pytest.mark.parametrize("seed", range(1, 61))
def test_fraction_puzzles_are_consistent(seed):
    p = P.generate("fracciones", seed)
    n, states = p.data["n"], p.data["states"]
    assert len(states) == n and n in (4, 6, 8)
    gray = sum(4 if s == "G" else (sum(s) if isinstance(s, tuple) else 0) for s in states)
    right = Fraction(gray, 4 * n)
    assert p.answer == f"{right.numerator}/{right.denominator}" and 0 < right < 1
    subs = [s for s in states if isinstance(s, tuple)]
    assert subs and all(len(s) == 4 and 0 < sum(s) < 4 for s in subs)           # hay triangulos partidos y mezclan colores
    assert any(not isinstance(s, tuple) for s in states)                       # y triangulos enteros (ahi esta el truco)
    naive = Fraction(p.extra["gray_pieces"], p.extra["pieces"])
    assert p.trap == f"{naive.numerator}/{naive.denominator}" and naive != right
    assert p.extra["total"] == 4 * n and p.extra["gray"] == gray


# --------------------------------------------------------------------------- 4. opcion multiple
def test_roman_numerals_roundtrip_and_reject_bad_forms():
    assert to_r(348) == "CCCXLVIII" and to_r(1994) == "MCMXCIV" and to_r(4) == "IV"
    assert all(P.from_roman(to_r(n)) == n for n in range(1, 4000))
    assert P.from_roman("IIX") is None and P.from_roman("XXXX") is None and P.from_roman("ABC") is None


def to_r(n):
    return P.to_roman(n)


@pytest.mark.parametrize("seed", range(1, 121))
def test_multiple_choice_has_exactly_one_correct_option(seed):
    p = P.generate("opciones", seed)
    d = p.data
    opts, ok = d["options"], d["correct"]
    assert len(opts) == 4 == len(set(opts)) and 0 <= ok < 4
    assert p.answer == f"{P.LETTERS[ok]}) {opts[ok]}"
    if d["sub"] == "roman":
        n = int(re.search(r"\d+", d["question"]).group())
        vals = [P.from_roman(o) for o in opts]
        assert None not in vals and vals.count(n) == 1 and vals[ok] == n          # todas validas, solo una vale n
        assert sorted(set(vals)) == sorted(vals)
    elif d["sub"] == "sequence":
        assert d["display"].endswith(", ?") and sum(o == opts[ok] for o in opts) == 1
        assert p.trap is None or p.trap in opts
    else:
        assert p.trap in opts and p.trap != opts[ok]


def test_roman_options_look_alike():
    import difflib
    rng = random.Random(3)
    for n in (348, 449, 677, 194, 289):
        right = to_r(n)
        sims = [difflib.SequenceMatcher(None, to_r(c), right).ratio() for c in P.roman_distractors(rng, n)]
        assert len(sims) == 3 and min(sims) >= 0.55                            # opciones disenadas para confundir


def test_every_kind_is_deterministic_and_avoids_repeats():
    for kind in P.MODES:
        a = P.generate(kind, 9)
        assert a == P.generate(kind, 9)
        assert P.generate(kind, 9, {a.key}).key != a.key


# --------------------------------------------------------------------------- fuentes y paletas
def test_font_fallback_when_nothing_is_installed():
    empty = FontKit(index={})
    assert not empty.found and "Pillow" in empty.describe()
    assert empty.get("black", 60).getbbox("Hola ×÷") is not None               # sigue dibujando con la fuente por defecto
    with pytest.raises(FileNotFoundError):
        FontKit(forced="no_existe_esta_fuente.ttf", index={})


def test_discovered_fonts_cover_the_needed_glyphs(kit):
    for path in kit.paths.values():
        if path:
            assert covers(path)


def test_palettes_keep_white_and_yellow_text_readable():
    ink = PALETTES[0].ink
    for pal in PALETTES:
        assert contrast((255, 255, 255), pal.c1) >= 3.0 and contrast((255, 255, 255), pal.c2) >= 3.0, pal.name
        assert contrast(pal.accent, pal.ink) >= 7 and contrast(pal.accent, pal.c2) >= 2.0
    assert contrast((255, 255, 255), ink) >= 12


# --------------------------------------------------------------------------- dibujo
@pytest.mark.parametrize("kind", P.MODES)
def test_images_render_at_feed_size_with_content(kind, kit):
    for seed in SEEDS[:3]:
        img, pal = render(P.generate(kind, seed), kit, seed)
        assert img.size == (1080, 1350) and img.mode == "RGB"
        arr = np.asarray(img, "f4")
        assert arr.std() > 30                                                    # no es un fondo liso
        bright = (arr.min(axis=2) > 235).mean()                                  # hay texto/figuras blancas
        assert bright > 0.005, (kind, seed, bright)


def test_render_is_deterministic_and_changes_with_the_seed(kit):
    p = P.generate("cubos", 4)
    a, _ = render(p, kit, 4)
    b, _ = render(p, kit, 4)
    c, _ = render(p, kit, 5)
    assert np.array_equal(np.asarray(a), np.asarray(b)) and not np.array_equal(np.asarray(a), np.asarray(c))


def test_text_stays_inside_the_side_margins(kit):
    """Las franjas laterales de 24 px solo llevan fondo: ninguna letra ni borde se sale de la imagen."""
    for kind in P.MODES:
        for seed in SEEDS[:3]:
            img, _ = render(P.generate(kind, seed), kit, seed)
            arr = np.asarray(img, "i2")
            for strip in (arr[:, :20], arr[:, -20:]):
                bright = (strip.min(axis=2) > 240).mean()
                assert bright < 0.01, (kind, seed)


# --------------------------------------------------------------------------- textos
def test_copy_pools_are_clean_and_have_no_bait_wording():
    pools = [*copy_feed.HOOKS.values(), *copy_feed.ASKS.values(), copy_feed.SHARE, copy_feed.FOLLOW]
    for pool in pools:
        for tpl in pool:
            for text in expand_all(tpl.replace("<trap>", "X").replace("<eq>", "Y")):
                assert not re.search(r"[{}|<>]", text) and "  " not in text
                assert not re.search(r"\b(gana|ganar|premio|sorteo|etiqueta|comenta (s[ií]|no))\b", text, re.I), text
    for pool in copy_feed.ASKS.values():
        assert all("👇" in t for t in pool)
    assert all(t.startswith("➕") for t in copy_feed.FOLLOW)


@pytest.mark.parametrize("kind", P.MODES)
def test_every_post_is_unique_and_well_formed(kind):
    pastes = set()
    for seed in range(1, 121):
        p = P.generate(kind, seed)
        post = copy_feed.build_post(p, seed)
        paste = post["paste"]
        assert "👇" in paste and "📤" in paste and "➕" in paste and not re.search(r"[{}|<>]|http", paste)
        assert 3 <= len(post["tags"]) <= 5 and post["tags"][-1] == "#ParadojaInfinita" and len(set(post["tags"])) == len(post["tags"])
        if kind != "opciones":                                               # el gancho y la pregunta no regalan la respuesta
            assert not re.search(rf"(?<![\w−-]){re.escape(p.answer)}(?![\w/])", post["hook"] + post["ask"]), post["hook"]
        assert post["reveal"].startswith("✅ Respuesta:") and post["hash"] == copy_feed.post_hash(paste)
        pastes.add(paste)
    assert len(pastes) == 120


def test_post_is_recomposed_when_the_history_already_has_it():
    p = P.generate("pemdas", 3)
    first = copy_feed.build_post(p, 3)
    seen = {first["hash"]}
    for _ in range(25):
        nxt = copy_feed.build_post(p, 3, seen)
        assert nxt["hash"] not in seen and nxt["salt"] > 0
        seen.add(nxt["hash"])
    assert copy_feed.build_post(p, 3)["paste"] == first["paste"]


def test_options_copy_lists_the_question_and_every_option():
    p = P.generate("opciones", 11)
    paste = copy_feed.build_post(p, 11)["paste"]
    assert p.data["question"] in paste
    for i, opt in enumerate(p.data["options"]):
        assert f"{P.LETTERS[i]}) {opt}" in paste


# --------------------------------------------------------------------------- archivos, historial y menu
def test_generate_one_writes_image_copy_and_history(tmp_path, kit):
    res = generate_one("fracciones", 21, kit, tmp_path)
    assert res.image.parent.name == __import__("datetime").date.today().isoformat() and res.image.parent.parent == tmp_path
    assert res.image.suffix == ".png" and res.txt.exists() and res.paste.exists()
    from PIL import Image
    assert Image.open(res.image).size == (1080, 1350)
    text = res.txt.read_text("utf-8-sig")
    for needle in ("COPIAR Y PEGAR", "RESPUESTA CORRECTA (CONTROL INTERNO", res.puzzle.answer, "COMENTARIO PARA REVELAR",
                   "TEXTO ALTERNATIVO", "HASHTAGS:"):
        assert needle in text
    paste = res.paste.read_text("utf-8-sig").strip()
    assert paste == res.post["paste"] and paste in text and res.puzzle.answer not in paste.split("\n\n")[0]
    h = hist.load(tmp_path)
    assert len(h) == 1 and h[0]["seed"] == 21 and h[0]["key"] == res.puzzle.key and h[0]["post"] == res.post["hash"]
    jpg = generate_one("cubos", 22, kit, tmp_path, "jpg")
    assert jpg.image.suffix == ".jpg"


def test_same_seed_twice_does_not_overwrite_or_repeat(tmp_path, kit):
    a = generate_one("pemdas", 5, kit, tmp_path)
    b = generate_one("pemdas", 5, kit, tmp_path)
    assert a.image != b.image and a.image.exists() and b.image.exists()
    assert a.puzzle.key != b.puzzle.key and a.post["paste"] != b.post["paste"]


def test_smart_random_covers_all_four_modes(tmp_path, kit):
    args = SimpleNamespace(out=tmp_path, formato="png", no_copy=True)
    gi.run("aleatorio", 4, 50, args, kit)
    assert {e["mode"] for e in hist.load(tmp_path)} == set(P.MODES)


def test_interactive_menu_generates_and_exits(tmp_path, kit, monkeypatch, capsys):
    answers = iter(["2", "1", "7", "7", "0"])                                   # cubos, 1 imagen, semilla 7, estadisticas, salir
    monkeypatch.setattr("builtins.input", lambda _="": next(answers))
    args = SimpleNamespace(out=tmp_path, formato="png", no_copy=True, estilo="auto", fuente=None)
    assert gi.interactive(args) == 0
    out = capsys.readouterr().out
    assert "cubos_" in out and "Imágenes generadas: 1" in out
    assert len(list(tmp_path.glob("*/cubos_*_7.png"))) == 1


def test_command_line_mode(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["generador_imagenes.py", "--modo", "opciones", "--count", "2", "--seed", "3",
                                     "--out", str(tmp_path), "--no-copy", "--formato", "jpg"])
    assert gi.main() == 0
    assert len(list(tmp_path.glob("*/opciones_*.jpg"))) == 2 and len(list(tmp_path.glob("*/opciones_*_publicar.txt"))) == 2
