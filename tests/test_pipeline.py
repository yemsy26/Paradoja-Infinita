"""Pruebas de la logica pura (sin GPU, sin FFmpeg y sin red): escena, linea de tiempo, guion y metadata."""
import numpy as np
import pytest

from paradoja.config import SUB_BAND, VideoSpec
from paradoja.metadata import MODE_SLUG, video_slug, write_metadata
from paradoja.scene import MODES, _swarm_positions, build_scene, swarm_clock
from paradoja.script_es import build_script, num_es
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


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("seed", SEEDS)
def test_scene_is_deterministic(mode, seed):
    a, b = build_scene(seed, mode, SPEC), build_scene(seed, mode, SPEC)
    assert video_slug(a) == video_slug(b)
    assert [(x.kind, x.sym, x.shape, x.hit, x.p) for x in a.acts] == [(x.kind, x.sym, x.shape, x.hit, x.p) for x in b.acts]


@pytest.mark.parametrize("mode", MODES)
def test_different_seeds_give_different_videos(mode):
    sigs = {(s.palette.name, s.shape, s.hook_kind, s.cell, s.speed) for s in (build_scene(i, mode, SPEC) for i in range(40))}
    assert len(sigs) > 10


@pytest.mark.parametrize("mode", ACT_MODES)
def test_act_structure_fills_duration(mode):
    sc, tl = _make(mode, 7)
    assert len(sc.acts) in (4, 5)
    assert tl.search_len >= 7.3
    assert tl.hook_len + len(sc.acts) * tl.act_len + sc.outro_len == pytest.approx(SPEC.duration)


@pytest.mark.parametrize("mode", MODES)
def test_timeline_uniforms_are_well_formed(mode):
    _, tl = _make(mode, 5)
    for t in (0.0, 10.0, 31.5, 62.98):
        u = tl.uniforms(t)
        assert 0.0 <= u["u_mix"] <= 1.0 and 0.0 <= u["u_pop"] <= 1.0


@pytest.mark.parametrize("seed", SEEDS)
def test_sync_hit_is_frame_aligned_and_tau_zero(seed):
    sc, tl = _make("sync", seed)
    for a in sc.acts:
        frame = round(a.hit * SPEC.fps)
        assert a.hit == frame / SPEC.fps
        assert tl.uniforms(frame / SPEC.fps)["u_tau"] == 0.0
        assert tl.uniforms((frame - 1) / SPEC.fps)["u_tau"] != 0.0
        rt = a.hit - tl.act_start(a.index)
        assert tl.search_len - 4.5 - 1e-9 <= rt <= tl.search_len - 0.9 + 1e-9  # dentro de la cuenta atras visible


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
        pos = _swarm_positions(pa, pb, a.n, swarm_clock(tl.search_len, tl.search_len, a.q[0]))
        assert abs(pos[0, 1]) > 0.1                              # fuera de la franja de subtitulos
        assert np.linalg.norm(pos[1:] - pos[0], axis=1).min() > 0.06  # no tapada por otra particula


@pytest.mark.parametrize("seed", SEEDS)
def test_anomaly_targets_avoid_subtitle_band(seed):
    sc, _ = _make("anomaly", seed)
    top = (SPEC.height - sc.rows * sc.cell) / 2
    for a in sc.acts:
        y0, y1 = top + a.target[1] * sc.cell, top + (a.target[1] + 1) * sc.cell
        assert not (y0 < SUB_BAND[1] and y1 > SUB_BAND[0])


@pytest.mark.parametrize("mode", MODES)
def test_script_fits_timeline(mode):
    sc, tl = _make(mode, 11)
    segs = build_script(sc, tl)
    starts = [s.start for s in segs]
    assert starts == sorted(starts)
    assert starts[0] < 1.0 and starts[-1] < SPEC.duration - 2.0
    assert all(s.text.strip() for s in segs)


def test_spanish_numbers():
    assert [num_es(n) for n in (10, 21, 38, 90, 99)] == [
        "diez", "veintiuno", "treinta y ocho", "noventa", "noventa y nueve"]


@pytest.mark.parametrize("mode", MODES)
def test_slug_and_metadata_file(mode, tmp_path):
    sc, tl = _make(mode, 2024)
    slug = video_slug(sc)
    assert slug.startswith(MODE_SLUG[mode] + "_") and slug.endswith("_2024")
    assert slug == slug.lower() and " " not in slug and slug.isascii()
    path = write_metadata(tmp_path / f"{slug}.txt", sc, tl, f"{slug}.mp4")
    text = path.read_text("utf-8-sig")
    for header in ("TIPO DE VIDEO:", "VARIABLES", "TÍTULO SUGERIDO:", "DESCRIPCIÓN (COPY):", "HASHTAGS:"):
        assert header in text
    tags = text.split("HASHTAGS:")[1].split()
    assert 3 <= len(tags) <= 5 and "#ParadojaInfinita" in tags and all(t.startswith("#") for t in tags)
