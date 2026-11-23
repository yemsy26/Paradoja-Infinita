"""Pruebas del text spinning: gancho, llamada a seguir, debate en acertijos/calculo y texto de publicacion unico."""
import random
import re
from pathlib import Path

import pytest

from paradoja import catalog, copy_es
from paradoja.config import VideoSpec
from paradoja.metadata import MAX_REROLL, build_post, post_hash
from paradoja.scene import MODES, build_scene
from paradoja.script_es import build_script
from paradoja.spin import count_variants, expand_all, fill, pick, spin
from paradoja.texts_es import num_es
from paradoja.timeline import Timeline

SPEC = VideoSpec()
ACT_MODES = [m for m in MODES if m != "loop"]
FOLLOW = re.compile(r"[Ss]íg|[Ss]igue la cuenta|[Ss]eguir|[Ss]eguirme")


def _make(mode, seed):
    sc = build_scene(seed, mode, SPEC)
    return sc, Timeline(SPEC, sc)


def _all(pool, **slots):
    return sorted({fill(v, **slots) for t in pool for v in expand_all(t)})


# --------------------------------------------------------------------------- motor
def test_spin_is_deterministic_and_uses_every_option():
    tpl = "{Hola|Buenas}, <n> {retos|pruebas}."
    assert spin(random.Random(3), tpl, n=5) == spin(random.Random(3), tpl, n=5)
    seen = {spin(random.Random(s), tpl, n=5) for s in range(200)}
    assert seen == {f"{a}, 5 {b}." for a in ("Hola", "Buenas") for b in ("retos", "pruebas")}


def test_spin_handles_nesting_slots_and_punctuation():
    assert spin(random.Random(1), "{a|{b|c} d}", ) in {"a", "b d", "c d"}
    assert fill("Hay <n> y <otro>", n=3) == "Hay 3 y <otro>"            # los huecos desconocidos se dejan
    assert spin(random.Random(1), "{¿Listo?|¿Seguro?}.") in {"¿Listo?", "¿Seguro?"}   # sin «?.»
    assert spin(random.Random(1), "Hola , mundo !") == "Hola, mundo!"
    assert "{N}" in spin(random.Random(1), "plantilla {N}")                   # sin '|' no es un grupo
    assert len(expand_all("{a|b} {c|d|e}")) == 6 and count_variants(["{a|b}", "{b|c}"]) == 3
    assert pick(random.Random(2), ("x", "y")) in ("x", "y")


# --------------------------------------------------------------------------- ganchos
def test_hook_pool_is_large_clean_and_has_the_requested_examples():
    hooks = _all(copy_es.HOOKS_GENERIC, n=5)
    assert len(hooks) >= 500
    for pool in [copy_es.HOOKS_GENERIC, *copy_es.HOOKS_BY_CATEGORY.values(), copy_es.HOOKS_LOOP]:
        for h in _all(pool, n=5):
            assert h.strip() and not re.search(r"[{}|<>]", h) and "  " not in h and ".." not in h.replace("...", "")
            assert 1 <= len(h.split()) <= 12 and len(h) <= 80, h
    for example in ("El 99% de las personas falla este nivel.", "Solo si tienes un IQ alto podrás resolver esto.",
                    "No parpadees o perderás el juego.", "Te apuesto a que no puedes encontrar el error.",
                    "Pon a prueba tu cerebro en 10 segundos."):
        assert example in hooks


def test_hook_lead_is_bounded_and_grows_with_length():
    assert copy_es.hook_lead("Atento.") == 2.5
    assert copy_es.hook_lead("a " * 30) == 4.4
    assert copy_es.hook_lead("uno dos tres cuatro cinco seis") < copy_es.hook_lead("uno dos tres cuatro cinco seis siete ocho")


@pytest.mark.parametrize("mode", MODES)
def test_every_video_opens_with_its_seeded_hook(mode):
    sc, tl = _make(mode, 31)
    assert sc.hook and "<" not in sc.hook and "{" not in sc.hook
    segs = build_script(sc, tl)
    assert segs[0].text == sc.hook and segs[0].start == pytest.approx(0.3 if mode == "loop" else 0.15)
    if mode == "loop":
        assert sc.lead == 0.0
    else:
        assert segs[0].start + 0.5 < sc.lead <= 4.4 and sc.acts[0].start == pytest.approx(sc.lead)


def test_hooks_use_the_challenge_category_and_the_real_number_of_challenges():
    texts = set()
    for seed in range(1, 300):
        sc = build_scene(seed, "anomaly", SPEC)
        texts.add(sc.hook)
        assert not re.search(r"<\w+>", sc.hook)
    assert len(texts) >= 120                                       # cientos de semillas, cientos de ganchos distintos
    assert any(str(len(build_scene(s, "mix", SPEC).acts)) in build_scene(s, "mix", SPEC).hook for s in range(1, 200))


# --------------------------------------------------------------------------- llamadas a seguir
def test_cta_pool_always_asks_to_follow_and_has_the_requested_examples():
    ctas = _all(copy_es.CTAS)
    assert len(ctas) >= 250
    for pool in (copy_es.CTAS, copy_es.CTAS_LOOP):
        for c in _all(pool):
            assert FOLLOW.search(c), c                                 # todas exigen seguir la cuenta
            assert not re.search(r"[{}|<>]|http", c) and len(c.split()) <= 14 and len(c) <= 80, c
    for example in ("¿Perdiste? Sígueme para tu revancha mañana.", "Si lo lograste, sígueme y comenta tu tiempo.",
                    "Únete al 1% que gana. Sígueme para más retos.", "¿Te engañó tu mente? Sígueme para el nivel 2."):
        assert example in ctas


@pytest.mark.parametrize("mode", MODES)
def test_every_video_closes_with_its_seeded_cta_spoken_and_burned(mode, tmp_path):
    from paradoja.subtitles import build_ass
    sc, tl = _make(mode, 5)
    segs = build_script(sc, tl)
    assert segs[-1].text == sc.cta and FOLLOW.search(sc.cta)
    assert segs[-1].start == pytest.approx(SPEC.duration - sc.outro_len + 0.2) and 4.0 <= sc.outro_len <= 5.0
    ass = build_ass(tmp_path / "s.ass", [], tl, SPEC).read_text("utf-8")
    first, starts = sc.cta.upper().split()[0], []
    for ln in ass.splitlines():
        if ",Cap," in ln and first in ln:
            h, m, sec = ln.split(",")[1].split(":")
            starts.append(int(h) * 3600 + int(m) * 60 + float(sec))
    assert starts and max(starts) >= SPEC.duration - sc.outro_len        # la misma frase que se narra, en pantalla


def test_ctas_vary_across_videos():
    ctas = {build_scene(s, "mix", SPEC).cta for s in range(1, 200)}
    assert len(ctas) >= 90


# --------------------------------------------------------------------------- debate
def test_debate_with_a_trap_confronts_both_answers_and_never_invents_numbers():
    rng = random.Random(4)
    for _ in range(300):
        line = copy_es.make_debate(rng, "Siete segundos.", "8 segundos")
        assert "8 segundos" in line and "siete segundos" in line and not re.search(r"[{}<>]|\d+\s?%", line), line
        assert line.rstrip().endswith("?") and len(line.split()) <= 16
        assert "8 SEGUNDOS" in copy_es.make_debate_screen(rng, "8 segundos")


def test_debate_without_a_trap_only_asks_the_viewer():
    rng = random.Random(9)
    seen = set()
    for _ in range(200):
        line = copy_es.make_debate(rng, "Las tijeras.", None)
        seen.add(line)
        assert line.startswith(("Las tijeras.", "La respuesta es las tijeras.", "Respuesta: las tijeras.",
                                "Solución: las tijeras."))
        assert line.endswith("?"), line
    assert len(seen) >= 15


def test_riddles_with_a_known_trap_have_a_distinct_wrong_answer():
    from paradoja.acts import load_riddles
    pool = load_riddles()
    traps = [r for r in pool if r.get("t")]
    assert len(traps) >= 20
    for r in traps:
        assert r["t"].strip().lower() != r["a"].strip().rstrip(".").lower()
        assert not r["t"].endswith(".") and len(r["t"]) <= 30
    assert [r["q"] for r in pool][:3] == ["¿Qué sube y nunca baja?", "Cuanto más seca, más moja. ¿Qué es?",
                                            "Siempre viene, pero nunca llega. ¿Qué es?"]       # el orden (historial) no cambia


@pytest.mark.parametrize("seed", (1, 2, 3, 4, 5, 6))
def test_math_reveal_debates_the_real_order_of_operations_trap(seed):
    sc, _ = _make("math", seed)
    for a in sc.acts:
        text, _eq, rest = a.answer.partition(" = ")
        value, _s, wrong = rest.partition(" (trampa: ")
        wrong = wrong.rstrip(")")
        reveal = a.voice[-1][1]
        assert num_es(int(value)) in reveal and num_es(int(wrong)) in reveal and "?" in reveal
        assert any(it[2].endswith(wrong) and it[0] > a.search for it in a.items)         # ficha en pantalla con la trampa


def test_riddle_scenes_end_with_a_debate_line_and_a_burned_chip():
    from paradoja.config import CAPTION_Y
    for seed in range(1, 40):
        sc, _ = _make("riddle", seed)
        for a in sc.acts:
            assert a.voice[-1][0] == pytest.approx(a.search + 0.25) and a.voice[-1][1].rstrip().endswith("?")
            chips = [it for it in a.items if it[5] == CAPTION_Y and it[0] > a.search]
            assert len(chips) == 1 and chips[0][1] <= a.length and chips[0][4]               # ficha de color de acento
            pre = [t for t, _x in a.voice if abs(t - (a.search - 2.0)) < 1e-6]
            assert len(pre) <= 1


def test_debate_lines_are_not_the_same_for_two_riddle_videos():
    lines = {sc.acts[0].voice[-1][1] for sc in (build_scene(s, "riddle", SPEC) for s in range(1, 120))}
    assert len(lines) >= 40


# --------------------------------------------------------------------------- publicacion
@pytest.mark.parametrize("mode", MODES)
def test_post_pieces_are_clean(mode):
    sc, tl = _make(mode, 8)
    seen = set()
    for _ in range(25):                                   # 25 versiones distintas del mismo video
        post = build_post(sc, tl, avoid_posts=seen)
        seen.add(post["hash"])
        paste = post["paste"]
        assert not re.search(r"[{}|<>]", paste) and "http" not in paste and "  " not in paste and "¿¿" not in paste
        assert 3 <= len(post["tags"]) <= 5 and post["tags"][-1] == copy_es.BRAND_TAG and len(set(post["tags"])) == len(post["tags"])
        assert post["tags"][0] in copy_es.TAG_POOLS[mode] or mode == "mix"
        assert len(post["title"]) <= 110 and post["title"].strip()


def test_post_never_repeats_for_the_same_video_when_history_has_it():
    sc, tl = _make("anomaly", 11)
    first = build_post(sc, tl)
    assert first["salt"] == 0 and first["hash"] == post_hash(first["paste"])
    assert build_post(sc, tl)["paste"] == first["paste"]                       # determinista
    seen = {first["hash"]}
    for _ in range(40):                                                         # se renderiza 40 veces la MISMA semilla
        nxt = build_post(sc, tl, avoid_posts=seen)
        assert nxt["hash"] not in seen and nxt["salt"] > 0
        seen.add(nxt["hash"])
    assert len(seen) == 41


def test_post_text_has_enormous_variety_across_seeds_and_modes():
    pastes, titles = set(), set()
    for mode in ACT_MODES:
        for seed in range(1, 31):
            post = build_post(*_make(mode, seed))
            pastes.add(post["paste"])
            titles.add(post["title"])
    assert len(pastes) == len(ACT_MODES) * 30                                   # ni un solo texto repetido
    assert len(titles) >= 0.7 * len(ACT_MODES) * 30


def test_titles_are_assembled_from_fragments_too():
    rng = random.Random(5)
    titles = {copy_es.make_title(rng, "encontrar la figura distinta", "retos visuales", 5) for _ in range(400)}
    assert len(titles) >= 150 and all(t.endswith(("?", ".")) and "<" not in t for t in titles)


def test_tag_sets_vary_but_stay_within_meta_limit():
    rng = random.Random(2)
    sets = {tuple(copy_es.make_tags(rng, "riddle")) for _ in range(300)}
    assert len(sets) >= 40 and all(3 <= len(s) <= 5 and s[-1] == copy_es.BRAND_TAG for s in sets)
    mix = copy_es.make_tags(random.Random(1), "mix", ["math", "riddle", "illusion", "math"])
    assert len(mix) <= 5 and mix[-1] == copy_es.BRAND_TAG


def test_history_stores_post_hashes_and_exposes_the_recent_ones(tmp_path):
    sc, tl = _make("sync", 3)
    post = build_post(sc, tl)
    catalog.append_history(tmp_path, catalog.entry_for(sc, "x", post["title"], post["hash"]))
    catalog.append_history(tmp_path, catalog.entry_for(sc, "y", "otro"))                  # entradas antiguas, sin huella
    assert catalog.recent_posts(catalog.load_history(tmp_path)) == {post["hash"]}
    again = build_post(sc, tl, catalog.recent_titles(catalog.load_history(tmp_path)),
                       catalog.recent_posts(catalog.load_history(tmp_path)))
    assert again["paste"] != post["paste"] and again["salt"] >= 1 and MAX_REROLL >= 32


def test_metadata_file_has_the_paste_block_and_returns_the_hash(tmp_path):
    from paradoja.metadata import write_metadata
    sc, tl = _make("riddle", 6)
    path, title, digest = write_metadata(tmp_path / "v.txt", sc, tl, "v.mp4")
    only = (tmp_path / "v_publicar.txt").read_text("utf-8-sig").strip()
    assert title == only.split("\n", 1)[0] and digest == post_hash(only)
    assert only in Path(path).read_text("utf-8-sig")


# --------------------------------------------------------------------------- pantalla
def test_hook_and_cta_chips_fit_their_rows_for_every_variant():
    """Ninguna variante invade la zona superior de la app ni la fila de la marca, ni se sale de los 1080 px de ancho."""
    from paradoja.config import TOP_SAFE
    from paradoja.subtitles import HOOK_Y, _wrap_big
    for hook in [*_all(copy_es.HOOKS_GENERIC, n=7), *[h for p in copy_es.HOOKS_BY_CATEGORY.values() for h in _all(p, n=7)],
                 *_all(copy_es.HOOKS_LOOP)]:
        text, size = _wrap_big(hook)
        lines = text.split(chr(92) + "N")
        assert size >= 44 and max(len(x) for x in lines) * 0.66 * size <= 960, hook
        assert HOOK_Y - len(lines) * size * 1.2 / 2 >= TOP_SAFE, (hook, len(lines), size)
    for cta in [*_all(copy_es.CTAS), *_all(copy_es.CTAS_LOOP)]:
        text, size = _wrap_big(cta, 22, 76, 290)
        lines = text.split(chr(92) + "N")
        assert size >= 44 and max(len(x) for x in lines) * 0.66 * size <= 960, cta
        assert len(lines) * size * 1.2 <= 290, (cta, len(lines), size)           # entre la marca (330) y la pregunta (770)


def test_debate_picks_a_variant_that_fits_the_voice_budget():
    rng = random.Random(12)
    hard = [copy_es.make_debate(rng, "cuarenta y uno", "ciento veinticinco", 12) for _ in range(300)]
    assert max(len(x.split()) for x in hard) <= 14                       # con numeros largos, la variante mas corta de 8
    unbounded = [copy_es.make_debate(rng, "cuarenta y uno", "ciento veinticinco") for _ in range(300)]
    assert sum(len(x.split()) for x in hard) < sum(len(x.split()) for x in unbounded)   # el presupuesto acorta de verdad
    short = [copy_es.make_debate(rng, "Siete segundos.", "8 segundos", 12) for _ in range(200)]
    assert sum(len(x.split()) <= 12 for x in short) >= 0.95 * len(short) and max(len(x.split()) for x in short) <= 13
