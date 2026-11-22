"""Pruebas de la logica pura (sin GPU, sin FFmpeg y sin red): escena, actos, guion, metadata y catalogo."""
from pathlib import Path

import numpy as np
import pytest

from paradoja import catalog
from paradoja.config import ANSWER_TOP, BOTTOM_SAFE, CAPTION_Y, COUNT_TOP_Y, HUD_Y, SAFE_Y, SUB_BAND, TOP_SAFE, VideoSpec
from paradoja.metadata import MODE_SLUG, video_slug, write_metadata
from paradoja.scene import MODES, TYPES, _swarm_positions, blocked_rows, build_scene, swarm_clock
from paradoja.script_es import build_script
from paradoja.texts_es import NAMED_COLORS, STROOP_COLORS, num_es
from paradoja.timeline import Timeline

SPEC = VideoSpec()
SEEDS = (1, 42, 101, 998877, 3380163066)
ACT_MODES = [m for m in MODES if m != "loop"]


def _make(mode, seed):
    sc = build_scene(seed, mode, SPEC)
    return sc, Timeline(SPEC, sc)


def test_spec_defaults_and_monetization_range():
    assert (SPEC.width, SPEC.height, SPEC.fps, SPEC.duration) == (1080, 1920, 60, 63.0)
    assert SPEC.frames == 3780
    for bad in (60.0, 66.0):
        with pytest.raises(ValueError):
            VideoSpec(duration=bad)


def test_catalog_has_many_challenge_types():
    assert len(TYPES) >= 14 and set(TYPES) | {"loop", "mix"} == set(MODES)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("seed", SEEDS)
def test_scene_is_deterministic(mode, seed):
    a, b = build_scene(seed, mode, SPEC), build_scene(seed, mode, SPEC)
    assert video_slug(a) == video_slug(b)
    assert [(x.type, x.answer, x.voice, x.items) for x in a.acts] == [(x.type, x.answer, x.voice, x.items) for x in b.acts]


@pytest.mark.parametrize("mode", ACT_MODES)
def test_different_seeds_give_different_content(mode):
    sigs = {tuple(a.answer for a in build_scene(i, mode, SPEC).acts) for i in range(40)}
    assert len(sigs) > 20


@pytest.mark.parametrize("mode", ACT_MODES)
@pytest.mark.parametrize("seed", SEEDS)
def test_acts_are_contiguous_and_fill_duration(mode, seed):
    sc, tl = _make(mode, seed)
    assert sc.acts[0].start == 0.0
    for a, b in zip(sc.acts, sc.acts[1:]):
        assert a.end == pytest.approx(b.start)
    assert sc.acts[-1].end + sc.outro_len == pytest.approx(SPEC.duration)
    assert all(a.search >= 4.7 and a.length - a.search == pytest.approx(TYPES[a.type].reveal) for a in sc.acts)
    assert tl.outro_start == pytest.approx(sc.acts[-1].end)


@pytest.mark.parametrize("seed", SEEDS)
def test_mix_combines_distinct_types(seed):
    sc, _ = _make("mix", seed)
    types = [a.type for a in sc.acts]
    assert 5 <= len(types) <= 7 and len(set(types)) == len(types)


@pytest.mark.parametrize("mode", [m for m in TYPES])
def test_single_type_videos_repeat_one_type(mode):
    sc, _ = _make(mode, 7)
    assert {a.type for a in sc.acts} == {mode} and 3 <= len(sc.acts) <= 8


@pytest.mark.parametrize("mode", MODES)
def test_timeline_uniforms_are_well_formed(mode):
    _, tl = _make(mode, 5)
    for t in (0.0, 10.0, 31.5, 62.98):
        u = tl.uniforms(t)
        assert 0.0 <= u["u_mix"] <= 1.0 and 0.0 <= u["u_pop"] <= 1.0 and isinstance(u["u_scene"], int)


@pytest.mark.parametrize("seed", SEEDS)
def test_sync_hit_is_frame_aligned_and_tau_zero(seed):
    sc, tl = _make("sync", seed)
    for a in sc.acts:
        frame = round(a.hit * SPEC.fps)
        assert a.hit == frame / SPEC.fps
        assert tl.uniforms(frame / SPEC.fps)["u_tau"] == 0.0
        assert tl.uniforms((frame - 1) / SPEC.fps)["u_tau"] != 0.0
        assert a.search - 4.5 - 1e-9 <= a.hit - a.start <= a.search - 0.9 + 1e-9  # dentro de la cuenta atras visible


def test_swarm_clock_stops_before_reveal_and_is_monotonic():
    S, vmax = 8.0, 4.0
    vals = [swarm_clock(i / 100, S, vmax) for i in range(0, 1200)]
    assert all(b >= a - 1e-12 for a, b in zip(vals, vals[1:]))
    assert swarm_clock(S - 1.0, S, vmax) == pytest.approx(swarm_clock(S + 2.0, S, vmax))


@pytest.mark.parametrize("seed", SEEDS)
def test_swarm_target_is_visible_when_swarm_stops(seed):
    sc, tl = _make("swarm", seed)
    for a in sc.acts:
        pa = np.frombuffer(a.arrays["u_pa"], "f4").reshape(-1, 4)
        pb = np.frombuffer(a.arrays["u_pb"], "f4").reshape(-1, 4)
        pos = _swarm_positions(pa, pb, a.n, swarm_clock(a.search, a.search, a.q[0]))
        assert abs(pos[0, 1]) > 0.1
        assert np.linalg.norm(pos[1:] - pos[0], axis=1).min() > 0.06


@pytest.mark.parametrize("mode", ["anomaly", "flicker", "memory"])
@pytest.mark.parametrize("seed", SEEDS)
def test_grid_targets_avoid_subtitle_band(mode, seed):
    sc, _ = _make(mode, seed)
    for a in sc.acts:
        cols, rows, cell, _hex = a.grid
        top = (SPEC.height - rows * cell) / 2
        y0, y1 = top + a.target[1] * cell, top + (a.target[1] + 1) * cell
        assert not (y0 < SUB_BAND[1] and y1 > SUB_BAND[0]) and a.target[1] not in blocked_rows(rows, cell)


@pytest.mark.parametrize("seed", SEEDS)
def test_count_answer_matches_the_items_on_screen(seed):
    sc, _ = _make("count", seed)
    for a in sc.acts:
        pb = np.frombuffer(a.arrays["u_pb"], "f4").reshape(-1, 4)[: a.n]
        shape_f, hue_f = a.q
        match = np.ones(a.n, bool)
        if shape_f >= 0:
            match &= np.abs(pb[:, 2] - shape_f) < 0.5
        if hue_f >= 0:
            match &= np.abs(pb[:, 3] - hue_f) < 0.02
        assert match.sum() == int(a.answer.split()[0]) and 10 <= a.n <= 18
        assert any(abs(h - c[2]) < 0.02 for h in [hue_f] for c in NAMED_COLORS) or hue_f < 0


@pytest.mark.parametrize("seed", SEEDS)
def test_math_answer_is_correct_and_has_a_trap(seed):
    sc, _ = _make("math", seed)
    for a in sc.acts:
        expr, rest = a.answer.split(" = ")
        value, trap = int(rest.split()[0]), int(rest.split("trampa: ")[1].rstrip(")"))
        assert eval(expr.replace("×", "*")) == value and trap != value and value > 0


@pytest.mark.parametrize("seed", SEEDS)
def test_stroop_ink_never_matches_the_word(seed):
    sc, _ = _make("stroop", seed)
    names = {c[0] for c in STROOP_COLORS}
    for a in sc.acts:
        words = [it for it in a.items if it[3] == 170]
        inks = a.answer.split(", ")
        assert len(words) == len(inks) >= 3 and set(inks) <= names
        assert all(w[2].lower() != ink for w, ink in zip(words, inks))


@pytest.mark.parametrize("seed", SEEDS)
def test_riddles_do_not_repeat_inside_a_video(seed):
    sc, _ = _make("riddle", seed)
    ids = [a.sym for a in sc.acts if a.sym >= 0]            # -1 = acertijo generado con numeros
    assert len(set(ids)) == len(ids)
    assert len({a.question for a in sc.acts}) == len(sc.acts)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("seed", SEEDS)
def test_script_fits_timeline(mode, seed):
    sc, tl = _make(mode, seed)
    segs = build_script(sc, tl)
    starts = [s.start for s in segs]
    assert starts == sorted(starts) and starts[0] < 1.0 and starts[-1] < SPEC.duration - 2.0
    assert all(s.text.strip() for s in segs)
    for a in sc.acts:
        assert all(0 <= t < a.length - 0.1 for t, _ in a.voice)
    if sc.mode != "loop":
        assert segs[0].start < 1.0                       # el reto empieza de inmediato (sin gancho largo)


def test_spanish_numbers():
    assert [num_es(n) for n in (0, 10, 21, 38, 90, 99, 100, 101, 250, 999)] == [
        "cero", "diez", "veintiuno", "treinta y ocho", "noventa", "noventa y nueve", "cien", "ciento uno",
        "doscientos cincuenta", "novecientos noventa y nueve"]


@pytest.mark.parametrize("mode", MODES)
def test_slug_and_metadata_file(mode, tmp_path):
    sc, tl = _make(mode, 2024)
    slug = video_slug(sc)
    assert slug.startswith(MODE_SLUG[mode] + "_") and slug.endswith("_2024")
    assert slug == slug.lower() and " " not in slug and slug.isascii()
    path, title = write_metadata(tmp_path / f"{slug}.txt", sc, tl, f"{slug}.mp4")
    text = path.read_text("utf-8-sig")
    for header in ("TIPO DE VIDEO:", "VARIABLES", "TÍTULO SUGERIDO:", "DESCRIPCIÓN (COPY):", "HASHTAGS:"):
        assert header in text
    assert title in text
    tags = text.split("HASHTAGS:")[1].split()
    assert 3 <= len(tags) <= 5 and "#ParadojaInfinita" in tags and all(t.startswith("#") for t in tags)
    assert "👇" in text                                   # llamada a comentar


def test_metadata_avoids_recently_used_titles(tmp_path):
    sc, tl = _make("anomaly", 11)
    _, first = write_metadata(tmp_path / "a.txt", sc, tl, "a.mp4")
    _, second = write_metadata(tmp_path / "b.txt", sc, tl, "b.mp4", avoid=[first])
    assert first != second


def test_history_roundtrip_and_stats(tmp_path):
    assert catalog.load_history(tmp_path) == []
    sc, _ = _make("mix", 5)
    catalog.append_history(tmp_path, catalog.entry_for(sc, video_slug(sc), "titulo"))
    hist = catalog.load_history(tmp_path)
    assert hist[0]["seed"] == 5 and hist[0]["types"] == sorted({a.type for a in sc.acts})
    assert any("Videos generados: 1" in line for line in catalog.stats(hist))


def test_smart_choice_penalizes_repetition():
    sc_math, _ = _make("math", 3)
    hist = [catalog.entry_for(sc_math, "x", "t")] * 5
    other, _ = _make("sequence", 3)
    assert catalog.novelty(other, hist) > catalog.novelty(sc_math, hist)
    seed, mode = catalog.choose("random", hist, SPEC, tries=12)
    assert mode in MODES and isinstance(seed, int)


def test_smart_random_covers_every_format_over_time():
    hist, seen = [], set()
    for i in range(60):
        seed, mode = catalog.choose("random", hist, SPEC, tries=8)
        sc = build_scene(seed, mode, SPEC)
        hist.append(catalog.entry_for(sc, video_slug(sc), f"t{i}"))
        seen.add(mode)
    assert len(seen) >= 12


def test_shader_digits_and_shapes_are_flipped_for_y_down():
    """Regresion: sdDigit usa y hacia arriba y la imagen y hacia abajo; sin el volteo los numeros salian invertidos."""
    src = (Path(__file__).parent.parent / "paradoja" / "shaders" / "scene.frag").read_text("utf-8")
    num = src[src.index("float numSD"): src.index("float symbolSD")]
    assert "q.y = -q.y" in num
    assert "p.y = -p.y" in src[src.index("float shapeSDi"): src.index("float shapeSD(vec2")]


# --------------------------------------------------------------------------- v1.1.1: calidad de los retos
@pytest.mark.parametrize("seed", SEEDS)
def test_count_frozen_figures_are_countable(seed):
    """Al detenerse las figuras: las que se cuentan estan fuera de la franja de subtitulos y nada se solapa."""
    sc, _ = _make("count", seed)
    for a in sc.acts:
        pa = np.frombuffer(a.arrays["u_pa"], "f4").reshape(-1, 4)
        pb = np.frombuffer(a.arrays["u_pb"], "f4").reshape(-1, 4)
        spd = 0.35 + 0.15 * (1.0 - a.delta)
        pos = _swarm_positions(pa, pb, a.n, (a.search - 2.0) * spd)
        shape_f, hue_f = a.q
        match = np.ones(a.n, bool)
        if shape_f >= 0:
            match &= np.abs(pb[:a.n, 2] - shape_f) < 0.5
        if hue_f >= 0:
            match &= np.abs(pb[:a.n, 3] - hue_f) < 0.02
        assert ((pos[match, 1] <= -0.10) | (pos[match, 1] >= 0.17)).all() and (np.abs(pos[:, 1]) > 0.09).all()
        assert (pos[match, 1] >= COUNT_TOP_Y).all() and (pos[match, 1] <= SAFE_Y[1]).all()   # fuera de pregunta y de la app
        d = np.linalg.norm(pos[:, None] - pos[None], axis=2) + np.eye(a.n) * 9
        assert d.min() > 0.085 and d[match].min() > 0.12


@pytest.mark.parametrize("mode", ACT_MODES)
def test_every_visual_challenge_pins_its_question_and_answer(mode):
    from paradoja.acts import CAPTION_TYPES, HOOK_END
    sc, _ = _make(mode, 42)
    for a in sc.acts:
        if a.type in CAPTION_TYPES:
            top = [it for it in a.items if it[5] == CAPTION_Y and it[0] > 0.0]       # sin el gancho del primer segundo
            first_start = HOOK_END if a.index == 0 else 0.5
            assert top and top[0][0] < first_start + 0.3 and top[0][1] == pytest.approx(a.search)   # pregunta en la busqueda
            assert any(it[0] == pytest.approx(a.search) for it in top)               # respuesta al revelar
            assert all(it[1] <= a.length for it in top)


@pytest.mark.parametrize("mode", ACT_MODES)
def test_first_frame_has_a_hook_and_the_challenge_is_already_on_screen(mode):
    """Las miniaturas salian oscuras: el primer fotograma debe llevar gancho y el reto ya formado (u_pop = 1)."""
    sc, tl = _make(mode, 7)
    hook = [it for it in sc.acts[0].items if it[0] == 0.0]
    assert len(hook) == 1 and hook[0][5] == CAPTION_Y and hook[0][1] >= 2.0
    assert hook[0][2].replace(chr(92) + "N", " ").isupper() or any(c.isdigit() for c in hook[0][2])
    assert tl.uniforms(0.0)["u_pop"] == pytest.approx(1.0)
    assert tl.uniforms(sc.acts[1].start + 0.0)["u_pop"] < 0.01            # los demas actos si entran con transicion


@pytest.mark.parametrize("seed", SEEDS)
def test_answers_stay_inside_the_app_safe_zone(seed):
    """Los botones y el pie de la app tapan la parte alta y baja: las respuestas se colocan entre TOP_SAFE y BOTTOM_SAFE."""
    for mode in ("anomaly", "flicker", "memory"):
        sc, _ = _make(mode, seed)
        for a in sc.acts:
            cols, rows, cell, _h = a.grid
            top = (1920 - rows * cell) / 2
            centre = top + (a.target[1] + 0.5) * cell
            assert ANSWER_TOP + 0.4 * cell <= centre <= BOTTOM_SAFE, (mode, centre)
    sc, _ = _make("swarm", seed)
    for a in sc.acts:
        pa = np.frombuffer(a.arrays["u_pa"], "f4").reshape(-1, 4)
        pb = np.frombuffer(a.arrays["u_pb"], "f4").reshape(-1, 4)
        y = _swarm_positions(pa, pb, a.n, swarm_clock(a.search, a.search, a.q[0]))[0, 1]
        assert SAFE_Y[0] <= y <= SAFE_Y[1]


@pytest.mark.parametrize("mode", ["anomaly", "mix", "stroop"])
def test_screen_text_never_sits_under_the_app_header(mode):
    from paradoja.subtitles import build_ass
    sc, tl = _make(mode, 5)
    for a in sc.acts:
        assert all(it[5] >= TOP_SAFE for it in a.items)
    assert HUD_Y - 12 >= TOP_SAFE and CAPTION_Y > HUD_Y


def test_outro_asks_for_score_share_and_follow(tmp_path):
    from paradoja.subtitles import build_ass
    sc, tl = _make("anomaly", 11)
    ass = build_ass(tmp_path / "s.ass", [], tl, SPEC).read_text("utf-8")
    for needle in ("COMENTA TU NOTA", "ENVÍASELO A QUIEN NO LO ACIERTE", "SÍGUENOS", f"¿CUÁNTOS DE {len(sc.acts)} ACERTASTE?", "FINAL"):
        assert needle in ass


@pytest.mark.parametrize("seed", SEEDS)
def test_ishihara_keeps_a_readable_contrast(seed):
    sc, _ = _make("ishihara", seed)
    assert all(a.delta >= 0.7 for a in sc.acts)


@pytest.mark.parametrize("mode", ACT_MODES)
@pytest.mark.parametrize("seed", SEEDS)
def test_spoken_lines_fit_before_the_next_one(seed, mode):
    """La voz de cada linea debe poder terminar antes de la siguiente: hueco minimo segun el largo del texto."""
    sc, tl = _make(mode, seed)
    segs = build_script(sc, tl)
    for cur, nxt in zip(segs, segs[1:]):
        words = len(cur.text.split())
        assert nxt.start - cur.start >= 0.25 + 0.30 * words * 0.62, (cur.text, nxt.start - cur.start)


@pytest.mark.parametrize("mode", ACT_MODES)
def test_pinned_captions_are_single_line_and_fit(mode):
    """El HUD y la barra de tiempo rodean la pregunta fija: una sola linea y que quepa en el ancho."""
    for seed in SEEDS:
        sc, _ = _make(mode, seed)
        for a in sc.acts:
            for t0, t1, text, size, _c, y in a.items:
                if y == CAPTION_Y and t0 > 0.0:
                    assert chr(92) + "N" not in text and size >= 34 and len(text) * 0.62 * size <= 1020, (text, size)


# --------------------------------------------------------------------------- v1.2.0: retos nuevos
def test_new_challenges_are_registered():
    for name, scene_id in (("cups", 11), ("simon", 12), ("digits", 13)):
        assert name in TYPES and name in MODES and TYPES[name].scene_id == scene_id


@pytest.mark.parametrize("seed", SEEDS)
def test_cups_answer_matches_the_shuffle(seed):
    sc, _ = _make("cups", seed)
    for a in sc.acts:
        pa = np.frombuffer(a.arrays["u_pa"], "f4").reshape(-1, 4)[: a.n]
        nc, ball = int(a.q[0]), int(a.q[1])
        slot, last_end = ball, 0.0
        for t0, dur, x, y in pa:
            x, y = int(x), int(y)
            assert t0 >= last_end - 1e-3 and t0 >= 2.0 - 1e-3 and t0 + dur <= a.search - 2.2 + 1e-3
            assert x != y and 0 <= x < nc and 0 <= y < nc
            slot = y if slot == x else x if slot == y else slot
            last_end = t0 + dur
        assert a.n >= 4 and a.answer.startswith(f"vaso {slot + 1} de {nc}")
        assert 3 <= nc <= 4 and a.p[0] < a.search                    # los numeros aparecen antes de revelar


@pytest.mark.parametrize("seed", SEEDS)
def test_simon_sequence_and_question_are_consistent(seed):
    sc, tl = _make("simon", seed)
    for a in sc.acts:
        pa = np.frombuffer(a.arrays["u_pa"], "f4").reshape(-1, 4)[: a.n]
        seq = [int(x) for x in pa[:, 0]]
        period, t0 = a.q
        assert 3 <= a.n <= 6 and all(0 <= x < 4 for x in seq)
        assert t0 + a.n * period <= a.search - 2.4 + 1e-3           # la secuencia termina antes de la pregunta
        asked = int(a.p[0])
        assert 2 <= asked <= a.n and a.answer.endswith(f"fue el {seq[asked - 1] + 1}")
    assert len([e for e in tl.sfx() if e[1] == "tick"]) >= sum(a.n for a in sc.acts)


@pytest.mark.parametrize("seed", SEEDS)
def test_digits_odd_differs_and_gets_harder(seed):
    from paradoja.acts import DIGIT_PAIRS
    sc, _ = _make("digits", seed)
    pairs = [set(p) for tier in DIGIT_PAIRS for p in tier]
    for a in sc.acts:
        assert a.sym != a.shape and {a.sym, a.shape} in pairs and a.grid[3] == 0
        assert a.target[1] not in blocked_rows(a.grid[1], a.grid[2])
    assert {sc.acts[-1].sym, sc.acts[-1].shape} in [set(p) for p in DIGIT_PAIRS[2]]   # el ultimo, 1 segmento de diferencia
    assert {sc.acts[0].sym, sc.acts[0].shape} in [set(p) for p in DIGIT_PAIRS[0]]


# --------------------------------------------------------------------------- contenido: reservas amplias
def test_riddle_pool_is_large_valid_and_has_no_duplicates():
    from paradoja.acts import RIDDLES_PATH, load_riddles
    pool = load_riddles()
    assert len(pool) >= 120 and RIDDLES_PATH.exists()
    qs = [r["q"] for r in pool]
    assert len(set(qs)) == len(qs)
    assert all(r["q"].strip() and r["a"].strip() and len(r["q"]) <= 115 and len(r["a"]) <= 45 for r in pool)


def test_generated_riddles_have_the_right_answers():
    import random
    from paradoja.acts import _RIDDLE_FAMILIES, _riddle_layout
    rng = random.Random(7)
    for fam in _RIDDLE_FAMILIES:
        for _ in range(60):
            q, a = fam(rng)
            assert q.endswith("?") and a and "{" not in q and "{" not in a
            assert _riddle_layout(q)[1] >= 58
    # comprobaciones de cuentas
    import re
    for _ in range(60):
        q, a = _RIDDLE_FAMILIES[0](rng)                                    # padre e hijo
        tot, diff = map(int, re.findall(r"\d+", q))
        son = (tot - diff) // 2
        assert (tot - diff) % 2 == 0 and son >= 3 and a.lower().startswith(num_es(son))
        q, a = _RIDDLE_FAMILIES[4](rng)                                    # campanadas
        n, t, m = map(int, re.findall(r"\d+", q))
        assert int(a.split()[0]) == t * (m - 1) // (n - 1) and t % (n - 1) == 0
        q, a = _RIDDLE_FAMILIES[7](rng)                                    # numero de dos cifras
        s_, d_ = map(int, re.findall(r"\d+", q))
        num = int(a.rstrip("."))
        hi, lo = divmod(num, 10)
        assert hi + lo == s_ and num - (10 * lo + hi) == d_ and 1 <= lo < hi


def test_sequences_have_a_huge_variety_and_valid_next_terms():
    import random
    from paradoja.acts import _SEQ_LEVELS, _gen_seq
    rng = random.Random(3)
    for level, fams in enumerate(_SEQ_LEVELS):
        seen = set()
        for _ in range(3000):
            shown, nxt, rule = _gen_seq(rng, level)
            assert len(shown) == 5 and len(set(shown + [nxt])) == 6 and rule.endswith(".")
            seen.add(tuple(shown))
        assert len(seen) >= 500                                             # el nivel dificil ya no son 24 secuencias
    for fam in (f for fams in _SEQ_LEVELS for f in fams):                   # reglas exactas de algunas familias
        seq, _rule = fam(rng)
        assert len(seq) == 6


# --------------------------------------------------------------------------- v1.3.0: ilusiones nuevas, ojo magico con numeros, texto de publicacion
def test_illusion_pool_has_ten_with_texts_for_each():
    from paradoja.scene import ILLUSIONS
    from paradoja.texts_es import ILL_ASK, ILL_NAME, ILL_TEXT
    assert len(ILLUSIONS) == 10 == len(ILL_NAME) == len(ILL_ASK) == len(ILL_TEXT)
    for kind in range(10):
        instr, mid, rev = ILL_TEXT[kind]
        assert instr and mid and rev


def test_new_illusions_are_reachable_and_their_shader_exists():
    src = (Path(__file__).parent.parent / "paradoja" / "shaders" / "scene.frag").read_text("utf-8")
    for fn in ("illHermann", "illMullerLyer", "illKanizsa", "illZollner"):
        assert f"vec3 {fn}(" in src
    kinds = {a.kind for seed in range(1, 80) for a in _make("illusion", seed)[0].acts}
    assert kinds == set(range(10))


@pytest.mark.parametrize("seed", SEEDS)
def test_magiceye_numbers_are_valid_two_digit_values(seed):
    nums = [a.sym for seed2 in range(seed, seed + 25) for a in _make("magiceye", seed2)[0].acts if a.sym >= 0]
    assert nums and all(10 <= n <= 99 for n in nums)


def test_publish_block_is_clean_and_ready_to_paste(tmp_path):
    from paradoja.metadata import AI_LABEL_NOTE, build_post
    for mode in ACT_MODES + ["loop"]:
        sc, tl = _make(mode, 77)
        post = build_post(sc, tl)
        paste = post["paste"]
        assert "HASHTAGS" not in paste and "TÍTULO" not in paste and "http" not in paste       # sin etiquetas ni enlaces
        assert paste.startswith(post["title"]) and paste.endswith(" ".join(post["tags"]))
        assert 3 <= len(post["tags"]) <= 5 and post["tags"][-1] == "#ParadojaInfinita"             # Meta: maximo 5 hashtags
        assert len(post["title"]) <= 110 and "📤" in paste and "➕" in paste
    sc, tl = _make("riddle", 5)
    path, title = write_metadata(tmp_path / "x.txt", sc, tl, "x.mp4")
    only = (tmp_path / "x_publicar.txt").read_text("utf-8-sig").strip()
    full = path.read_text("utf-8-sig")
    assert only in full and full.index("COPIAR Y PEGAR") < full.index("TIPO DE VIDEO:") and AI_LABEL_NOTE in full
    assert title == only.split("\n", 1)[0]


def test_post_text_changes_between_videos_of_the_same_type():
    from paradoja.metadata import build_post
    pastes = {build_post(*_make("sync", seed))["paste"] for seed in range(1, 41)}
    titles = {p.split("\n", 1)[0] for p in pastes}
    assert len(pastes) >= 35 and len(titles) >= 8                  # antes: 4 titulos x 3 descripciones por tipo
