"""Pruebas del autopiloto con la API de Meta y los generadores simulados (sin red, sin GPU y sin publicar nada)."""
import logging
import random
import subprocess
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import autopiloto
from paradoja.autopilot import core, media
from paradoja.autopilot.envfile import Config, load_env, parse_env, redact
from paradoja.autopilot.graph import GraphClient, GraphError

TOKEN = "EAAB" + "x1y2z3" * 12
PAGE = "1234567890123"
GOOD_VIDEO = {"streams": [{"codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920, "r_frame_rate": "60/1"},
                          {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 2}],
              "format": {"duration": "63.0"}}


# --------------------------------------------------------------------------- dobles de prueba
class Resp:
    def __init__(self, status=200, body=None, text=""):
        self.status_code, self._body, self.text = status, body if body is not None else {}, text

    def json(self):
        return self._body


def err(code, msg="error", status=400, **extra):
    return Resp(status, {"error": {"code": code, "message": msg, "type": "OAuthException", **extra}})


class ConnectTimeout(Exception):
    pass


class ReadTimeout(Exception):
    pass


class FakeHttp:
    """`handler(method, url, kw) -> Resp | Exception`. Guarda las llamadas (y el cuerpo binario de las subidas)."""

    def __init__(self, handler):
        self.handler, self.calls = handler, []

    def request(self, method, url, **kw):
        body = kw["data"].read() if hasattr(kw.get("data"), "read") else None
        self.calls.append(SimpleNamespace(method=method, url=url, kw=kw, body=body))
        out = self.handler(method, url, kw)
        if isinstance(out, Exception):
            raise out
        return out

    post = lambda self, url, **kw: self.request("POST", url, **kw)    # noqa: E731


def is_finish(call) -> bool:
    d = call.kw.get("data")
    return isinstance(d, dict) and d.get("upload_phase") == "finish"


def client(handler, sleeps=None):
    http = FakeHttp(handler)
    return GraphClient(PAGE, TOKEN, "v26.0", http=http, sleep=(sleeps.append if sleeps is not None else lambda s: None)), http


def make_files(tmp_path, kind, copy="Hola 👇\n\n#Reto #ParadojaInfinita", n=1):
    day = Path(tmp_path) / "salida" / "2026-11-23"
    day.mkdir(parents=True, exist_ok=True)
    stem = f"{kind}_prueba_{n}"
    path = day / (stem + (".png" if kind == "foto" else ".mp4"))
    path.write_bytes(bytes(range(256)) * 40)
    (day / f"{stem}_publicar.txt").write_text(copy, "utf-8-sig")
    (day / f"{stem}.txt").write_text(f"=== COPIAR Y PEGAR EN LA PUBLICACIÓN ===\n{copy}\n=== FIN ===\n\nTEXTO ALTERNATIVO "
                                     "(accesibilidad):\nImagen de un reto.\n\nAVISO: x\n", "utf-8-sig")
    return path


# --------------------------------------------------------------------------- .env y configuracion
def test_parse_env_handles_comments_quotes_and_exports(tmp_path):
    text = ("# comentario\nPAGE_ID=123\nexport PAGE_ACCESS_TOKEN = \"abc def\"  \nFOTO_HORA=11:30 # mañana\n"
            "VACIA=\nmal linea\n1MALA=x\n'QUOTED'=y\nVIDEO_HORA='18:00'\n")
    assert parse_env(text) == {"PAGE_ID": "123", "PAGE_ACCESS_TOKEN": "abc def", "FOTO_HORA": "11:30", "VACIA": "",
                               "VIDEO_HORA": "18:00"}
    p = tmp_path / ".env"
    p.write_text("﻿PAGE_ID=999\n", "utf-8")
    assert load_env(p) == {"PAGE_ID": "999"} and load_env(tmp_path / "no_existe") == {}


def test_config_defaults_overrides_and_validation(tmp_path):
    cfg = Config.from_sources({"PAGE_ID": PAGE, "PAGE_ACCESS_TOKEN": TOKEN}, environ={}, root=tmp_path)
    assert (cfg.photo_time, cfg.video_time, cfg.jitter_min, cfg.jitter_max, cfg.max_per_day) == ("11:30", "18:00", 1, 15, 2)
    assert cfg.ai_label is True and cfg.dry_run is False and cfg.version == "v26.0" and cfg.problems() == []
    over = Config.from_sources({"PAGE_ID": PAGE, "PAGE_ACCESS_TOKEN": TOKEN, "FOTO_HORA": "09:05", "JITTER_MAX": "7",
                                "IA_ETIQUETA": "0", "DRY_RUN": "1", "SALIDA_IMAGENES": "imgs"},
                               environ={"FOTO_HORA": "10:00", "OTRA": "x"}, root=tmp_path)
    assert over.photo_time == "10:00" and over.jitter_max == 7 and not over.ai_label and over.dry_run   # el entorno manda
    assert over.image_out == tmp_path / "imgs"
    bad = Config.from_sources({"PAGE_ID": "abc", "PAGE_ACCESS_TOKEN": "PEGA_AQUI_TU_TOKEN_DE_PAGINA_DE_LARGA_DURACION",
                               "FOTO_HORA": "25:00", "JITTER_MIN": "20", "JITTER_MAX": "5", "MAX_POSTS_DIA": "99",
                               "GRAPH_VERSION": "26"}, environ={}, root=tmp_path)
    problems = " ".join(bad.problems())
    for needle in ("PAGE_ID", "PAGE_ACCESS_TOKEN", "FOTO_HORA", "JITTER", "MAX_POSTS_DIA", "GRAPH_VERSION"):
        assert needle in problems
    assert Config.from_sources({}, environ={}, root=tmp_path).problems(need_credentials=False) == []


def test_token_is_never_exposed(tmp_path):
    cfg = Config.from_sources({"PAGE_ID": PAGE, "PAGE_ACCESS_TOKEN": TOKEN}, environ={}, root=tmp_path)
    assert TOKEN not in repr(cfg) and TOKEN not in str(cfg)
    text = f"fallo en https://x/y?access_token={TOKEN}&a=1 con Authorization: OAuth {TOKEN} y {TOKEN}"
    assert TOKEN not in redact(text, TOKEN) and "access_token=***" in redact(text, TOKEN)


# --------------------------------------------------------------------------- cliente Graph: comprobacion y fotos
def test_check_and_error_classification():
    c, http = client(lambda m, u, kw: Resp(200, {"id": PAGE, "name": "Mi página"}))
    assert c.check()["name"] == "Mi página" and http.calls[0].url == f"https://graph.facebook.com/v26.0/{PAGE}"
    c, _ = client(lambda m, u, kw: err(190, "Invalid OAuth access token"))
    with pytest.raises(GraphError) as e:
        c.check()
    assert e.value.code == 190 and not e.value.retry and "token" in str(e.value).lower() and TOKEN not in str(e.value)
    c, _ = client(lambda m, u, kw: err(4, "Application request limit reached"))
    with pytest.raises(GraphError) as e:
        c.check()
    assert e.value.retry and not e.value.ambiguous


def test_post_photo_sends_file_caption_and_alt(tmp_path):
    img = make_files(tmp_path, "foto")
    c, http = client(lambda m, u, kw: Resp(200, {"id": "111", "post_id": f"{PAGE}_111"}))
    out = c.post_photo(img, "Mi copy 👇", "Texto alternativo")
    call = http.calls[0]
    assert call.method == "POST" and call.url == f"https://graph.facebook.com/v26.0/{PAGE}/photos"
    assert call.kw["data"] == {"caption": "Mi copy 👇", "published": "true", "access_token": TOKEN,
                               "alt_text_custom": "Texto alternativo"}
    assert call.kw["files"]["source"][0] == img.name and out == {"id": "111", "post_id": f"{PAGE}_111"}


def test_post_photo_retries_once_without_alt_if_the_api_rejects_it(tmp_path):
    img = make_files(tmp_path, "foto")

    def handler(m, u, kw):
        return err(100, "Invalid parameter alt_text_custom") if "alt_text_custom" in kw["data"] else Resp(200, {"id": "5"})

    c, http = client(handler)
    assert c.post_photo(img, "x", "alt")["id"] == "5" and len(http.calls) == 2
    c, http = client(lambda m, u, kw: err(100, "Invalid parameter"))
    with pytest.raises(GraphError):
        c.post_photo(img, "x", "alt")
    assert len(http.calls) == 1                                  # otros errores 100 no se reintentan


def test_photo_network_failures_are_classified_to_avoid_duplicates(tmp_path):
    img = make_files(tmp_path, "foto")
    c, _ = client(lambda m, u, kw: ConnectTimeout(f"no conecta {TOKEN}"))
    with pytest.raises(GraphError) as e:
        c.post_photo(img, "x")
    assert e.value.retry and not e.value.ambiguous and TOKEN not in str(e.value)       # nunca salio: se puede reintentar
    c, _ = client(lambda m, u, kw: ReadTimeout("se agotó la espera"))
    with pytest.raises(GraphError) as e:
        c.post_photo(img, "x")
    assert e.value.ambiguous                                                           # pudo publicarse: no reintentar
    c, _ = client(lambda m, u, kw: Resp(500, {}, "boom"))
    with pytest.raises(GraphError) as e:
        c.post_photo(img, "x")
    assert e.value.ambiguous and e.value.retry


# --------------------------------------------------------------------------- cliente Graph: Reels
def reel_handler(state, upload_fail_first=False, statuses=None, finish=None):
    statuses = list(statuses or [{"video_status": "ready", "publishing_phase": {"status": "complete", "publish_status": "published"}}])

    def handler(m, u, kw):
        if u.endswith("/video_reels"):
            phase = kw["data"]["upload_phase"]
            state.setdefault("phases", []).append(phase)
            if phase == "start":
                return Resp(200, {"video_id": "777", "upload_url": "https://rupload.facebook.com/video-upload/v26.0/777"})
            return finish() if finish else Resp(200, {"success": True})
        if "rupload" in u:
            state["uploads"] = state.get("uploads", 0) + 1
            if upload_fail_first and state["uploads"] == 1:
                return ConnectionError("conexión cortada")
            return Resp(200, {"success": True})
        if u.endswith("/777"):                                  # estado
            if state.get("uploads", 0) == 1 and upload_fail_first:
                return Resp(200, {"status": {"uploading_phase": {"status": "in_progress", "bytes_transfered": 100}}})
            return Resp(200, {"status": statuses.pop(0) if len(statuses) > 1 else statuses[0]})
        raise AssertionError(u)

    return handler


def test_post_reel_runs_the_three_phases(tmp_path):
    mp4, state = make_files(tmp_path, "video"), {}
    c, http = client(reel_handler(state, statuses=[{"video_status": "processing", "processing_phase": {"status": "in_progress"}},
                                                   {"video_status": "ready", "publishing_phase": {"status": "complete",
                                                                                                  "publish_status": "published"}}]))
    out = c.post_reel(mp4, "Descripción #tag", ai_generated=True)
    assert state["phases"] == ["start", "finish"] and out["video_id"] == "777" and out["status"]["publish_status"] == "published"
    start, up, fin = http.calls[0], next(x for x in http.calls if "rupload" in x.url), next(
        x for x in http.calls if is_finish(x))
    assert start.url == f"https://graph.facebook.com/v26.0/{PAGE}/video_reels" and start.kw["data"]["access_token"] == TOKEN
    assert up.url == "https://rupload.facebook.com/video-upload/v26.0/777"
    assert up.kw["headers"] == {"Authorization": f"OAuth {TOKEN}", "offset": "0", "file_size": str(mp4.stat().st_size),
                                "Content-Type": "application/octet-stream"}
    assert up.body == mp4.read_bytes()
    assert fin.kw["data"] == {"upload_phase": "finish", "video_id": "777", "video_state": "PUBLISHED",
                              "description": "Descripción #tag", "is_ai_generated": "true", "access_token": TOKEN}


def test_reel_upload_resumes_from_the_bytes_meta_already_has(tmp_path):
    mp4, state, sleeps = make_files(tmp_path, "video"), {}, []
    c, http = client(reel_handler(state, upload_fail_first=True), sleeps)
    c.post_reel(mp4, "x")
    ups = [x for x in http.calls if "rupload" in x.url]
    assert len(ups) == 2 and ups[0].kw["headers"]["offset"] == "0" and ups[1].kw["headers"]["offset"] == "100"
    assert ups[1].body == mp4.read_bytes()[100:] and sleeps                      # reanuda donde se quedó y espera un poco


def test_reel_errors_are_reported_with_their_phase(tmp_path):
    mp4 = make_files(tmp_path, "video")
    c, _ = client(lambda m, u, kw: err(200, "(#200) Permissions error"))
    with pytest.raises(GraphError) as e:
        c.post_reel(mp4, "x")
    assert e.value.phase == "inicio" and not e.value.retry and "pages_manage_posts" in str(e.value)
    c, _ = client(reel_handler({}, statuses=[{"video_status": "error", "processing_phase": {"status": "error",
                                                                                           "error": {"message": "mala codificación"}}}]))
    with pytest.raises(GraphError) as e:
        c.post_reel(mp4, "x")
    assert e.value.phase == "proceso" and "mala codificación" in str(e.value)
    c, _ = client(reel_handler({}, finish=lambda: ReadTimeout("sin respuesta")))
    with pytest.raises(GraphError) as e:
        c.post_reel(mp4, "x")
    assert e.value.phase == "finalizar" and e.value.ambiguous                  # el «finish» pudo publicar: no repetir


def test_reel_still_processing_returns_a_timeout_flag(tmp_path):
    mp4 = make_files(tmp_path, "video")
    c, _ = client(reel_handler({}, statuses=[{"video_status": "processing"}]))
    out = c.post_reel(mp4, "x")
    assert out["status"]["timeout"] is True


# --------------------------------------------------------------------------- generacion y busqueda de archivos
def test_find_artifact_picks_the_newest_and_reads_copy_and_alt(tmp_path):
    import os
    old = make_files(tmp_path, "foto", "viejo", n=1)
    os.utime(old, (1, 1))
    for f in old.parent.glob("foto_prueba_1*"):
        os.utime(f, (1, 1))
    new = make_files(tmp_path, "foto", "Texto nuevo\n\n#Tag", n=2)
    art = media.find_artifact(tmp_path / "salida", "foto", since=1000)
    assert art.media == new and art.copy == "Texto nuevo\n\n#Tag" and art.alt == "Imagen de un reto."
    with pytest.raises(media.GenerationError):
        media.find_artifact(tmp_path / "salida", "video", since=1000)           # no hay .mp4
    assert media.fallback_copy(new.with_suffix(".txt")) == "Texto nuevo\n\n#Tag"


def test_run_generator_reports_failures_and_timeouts():
    ok = media.run_generator(["x"], 5, lambda *a, **k: SimpleNamespace(returncode=0, stdout=b"hecho \xc3\xa1", stderr=b""))
    assert "hecho á" in ok
    with pytest.raises(media.GenerationError, match="código 3"):
        media.run_generator(["x"], 5, lambda *a, **k: SimpleNamespace(returncode=3, stdout=b"", stderr=b"Traceback boom"))

    def slow(*a, **k):
        raise subprocess.TimeoutExpired("x", 1)

    with pytest.raises(media.GenerationError, match="tardó"):
        media.run_generator(["x"], 90, slow)


def test_reel_and_photo_requirements():
    assert media.check_reel(GOOD_VIDEO) == ([], [])
    bad = {"streams": [{"codec_type": "video", "codec_name": "h264", "width": 480, "height": 640, "r_frame_rate": "15/1"}],
           "format": {"duration": "120"}}
    errors, warns = media.check_reel(bad)
    assert len(errors) == 3 and any("9:16" in w for w in warns) and any("sin audio" in w or "no tiene audio" in w for w in warns)
    assert media.check_reel(None)[1]
    small, big = Path(__file__), None
    assert media.check_photo(small) == ([], [])
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".png") as f:
        f.write(b"0" * 4_100_000)
        f.flush()
        assert media.check_photo(Path(f.name))[0]


# --------------------------------------------------------------------------- orquestador
def build(tmp_path, handler=None, *, dry=False, kinds=("foto", "video"), **cfg_kw):
    """Autopilot con generadores y API simulados. -> (auto, http, calls_del_generador)."""
    cfg = Config(page_id=PAGE, token=TOKEN, dry_run=dry, image_out=tmp_path / "salida", video_out=tmp_path / "salida",
                 state_file=tmp_path / "estado.json", log_file=tmp_path / "x.log", **cfg_kw)
    gen_calls = []
    counter = iter(range(1, 100))

    def runner(cmd, **kw):
        gen_calls.append(cmd)
        make_files(tmp_path, "foto" if cmd[1].endswith("generador_imagenes.py") else "video", n=next(counter))
        return SimpleNamespace(returncode=0, stdout=b"ok", stderr=b"")

    http = FakeHttp(handler or (lambda m, u, kw: Resp(200, {"id": "9", "post_id": "9_9", "video_id": "777", "success": True,
                                                              "status": {"video_status": "ready"}})))
    cl = GraphClient(PAGE, TOKEN, "v26.0", http=http, sleep=lambda s: None)
    when = [datetime(2026, 11, 23, 11, 40)]
    auto = core.Autopilot(cfg, cl, core.State(cfg.state_file), runner=runner, probe=lambda p: GOOD_VIDEO,
                          now=lambda: when[0], rng=random.Random(1), sleep=lambda s: None)
    auto.when = when
    return auto, http, gen_calls


def test_photo_task_generates_publishes_and_records_the_day(tmp_path):
    auto, http, gen = build(tmp_path)
    out = auto.execute("foto")
    assert out.status == "ok" and gen[0][1].endswith("generador_imagenes.py") and "aleatorio" in gen[0] and "--no-copy" in gen[0]
    assert http.calls[0].url.endswith(f"/{PAGE}/photos") and http.calls[0].kw["data"]["caption"].startswith("Hola 👇")
    assert http.calls[0].kw["data"]["alt_text_custom"] == "Imagen de un reto."
    assert auto.state.done(datetime(2026, 11, 23).date(), "foto")
    assert auto.execute("foto").status == "skipped" and len(http.calls) == 1        # no se duplica al repetir el dia
    assert core.State(tmp_path / "estado.json").done(datetime(2026, 11, 23).date(), "foto")   # y sobrevive al reinicio


def test_video_task_uses_main_py_in_random_mode(tmp_path):
    auto, http, gen = build(tmp_path)
    out = auto.execute("video")
    assert out.status == "ok" and gen[0][1].endswith("main.py") and gen[0][gen[0].index("--mode") + 1] == "random"
    assert "--no-copy" in gen[0] and any(c.url.endswith("/video_reels") for c in http.calls)


def test_video_publishing_flow_end_to_end(tmp_path):
    state = {}
    auto, http, _ = build(tmp_path, reel_handler(state))
    out = auto.execute("video")
    assert out.status == "ok" and out.post_id == "777" and state["phases"] == ["start", "finish"]
    fin = next(c for c in http.calls if is_finish(c))
    assert fin.kw["data"]["is_ai_generated"] == "true" and fin.kw["data"]["description"].startswith("Hola")
    auto2, http2, _ = build(tmp_path / "otro", reel_handler({}), ai_label=False)
    auto2.execute("video")
    assert next(c for c in http2.calls if is_finish(c)).kw["data"]["is_ai_generated"] == "false"


def test_daily_cap_and_dry_run(tmp_path):
    auto, http, _ = build(tmp_path, max_per_day=1)
    assert auto.execute("foto").status == "ok"
    out = auto.execute("video")
    assert out.status == "skipped" and out.detail == "límite diario" and len(http.calls) == 1
    assert auto.execute("video", force=True).status == "ok"                           # --ahora ignora el limite
    auto, http, gen = build(tmp_path / "d", dry=True)
    out = auto.execute("foto")
    assert out.status == "dry" and not http.calls and gen and not auto.state.done(datetime(2026, 11, 23).date(), "foto")


def test_generator_failure_is_logged_and_the_program_survives(tmp_path):
    auto, http, _ = build(tmp_path)
    auto.runner = lambda cmd, **kw: SimpleNamespace(returncode=1, stdout=b"", stderr=b"CUDA fuera de memoria")
    out = auto.execute("video")
    assert out.status == "error" and "CUDA" in out.detail and not http.calls
    assert auto.state.data["dias"]["2026-11-23"]["video"]["estado"] == "error"
    assert auto.execute("video").status == "error"                                    # un error no bloquea el siguiente intento
    auto.runner = lambda cmd, **kw: (_ for _ in ()).throw(RuntimeError("explotó"))
    assert auto._guard(auto.execute, "foto").status == "error"                         # ni siquiera una excepcion inesperada


def test_requirements_failure_blocks_publication(tmp_path):
    auto, http, _ = build(tmp_path)
    auto.probe = lambda p: {"streams": [{"codec_type": "video", "width": 300, "height": 300, "r_frame_rate": "30/1"}],
                            "format": {"duration": "10"}}
    out = auto.execute("video")
    assert out.status == "error" and "no cumple" in out.detail and not http.calls


def test_transient_api_failures_are_retried_but_ambiguous_ones_are_not(tmp_path):
    seq = iter([err(4, "rate limit"), Resp(200, {"id": "1", "post_id": "1_1"})])
    auto, http, gen = build(tmp_path, lambda m, u, kw: next(seq), retries=2, retry_minutes=20)
    sleeps = []
    auto.sleep = sleeps.append
    out = auto.run_now("foto")
    assert out.status == "ok" and sleeps == [1200] and len(gen) == 1 and len(http.calls) == 2   # no se vuelve a renderizar
    auto, http, _ = build(tmp_path / "b", lambda m, u, kw: ReadTimeout("sin respuesta"))
    out = auto.execute("foto")
    assert out.status == "ambiguous" and auto.state.done(datetime(2026, 11, 23).date(), "foto")   # cuenta como publicado
    auto, http, _ = build(tmp_path / "c", lambda m, u, kw: err(190, "token caducado"))
    assert auto.run_now("foto").status == "error" and len(http.calls) == 1                       # error fatal: sin reintentos
    auto, http, _ = build(tmp_path / "d", lambda m, u, kw: err(4, "limite"), retries=1)
    out = auto.run_now("foto")                                                                    # agota los reintentos
    assert out.status == "error" and len(http.calls) == 2                                         # 1 intento + 1 reintento
    assert auto.state.data["dias"]["2026-11-23"]["foto"]["estado"] == "error"


class FakeSched:
    def __init__(self):
        self.jobs = []

    def every(self, n):
        outer = self

        class _J:
            @property
            def seconds(s):
                return s

            def do(s, fn, *args):
                outer.jobs.append((n, fn, args))
        return _J()


def test_jitter_is_random_between_one_and_fifteen_minutes(tmp_path):
    auto, _, _ = build(tmp_path)
    auto.sched, auto.cancel = FakeSched(), object()
    seen = set()
    for seed in range(300):
        auto.rng = random.Random(seed)
        auto.sched.jobs.clear()
        auto.trigger("foto")
        delay = auto.sched.jobs[0][0]
        assert 60 <= delay <= 900
        seen.add(delay)
    assert len(seen) > 150                                                                  # nunca la misma hora exacta
    assert min(seen) < 120 and max(seen) > 840


def test_late_tasks_are_skipped_after_a_long_sleep(tmp_path):
    auto, _, _ = build(tmp_path, tolerance_hours=3.0)
    auto.sched, auto.cancel = FakeSched(), object()
    auto.when[0] = datetime(2026, 11, 23, 15, 0)                    # la tarea era a las 11:30: pasaron 3,5 h
    auto.trigger("foto")
    assert not auto.sched.jobs
    auto.when[0] = datetime(2026, 11, 23, 11, 31)
    auto.trigger("foto")
    assert len(auto.sched.jobs) == 1


def test_real_schedule_runs_the_jittered_job_once(tmp_path):
    pytest.importorskip("schedule")
    auto, http, _ = build(tmp_path)
    sch = core.build_scheduler(auto.cfg, auto)
    assert len(sch.get_jobs()) == 2 and all(j.at_time is not None for j in sch.get_jobs())
    assert len(core.describe_schedule(sch)) == 2
    sch.clear()
    auto.trigger("foto")                                             # programa el retraso aleatorio
    assert len(sch.get_jobs()) == 1 and 60 <= sch.get_jobs()[0].interval <= 900
    sch.run_all()                                                    # llega la hora real
    assert len(http.calls) == 1 and sch.get_jobs() == []             # se ejecuto y la tarea de una sola vez desaparecio


def test_run_forever_survives_scheduler_errors():
    calls = {"n": 0}

    class Sch:
        def run_pending(self):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("fallo raro")

    ticks = []
    core.run_forever(Sch(), stop=lambda: calls["n"] >= 4, sleep=ticks.append)
    assert calls["n"] == 4 and len(ticks) == 4


def test_state_pruning_and_single_instance(tmp_path):
    st = core.State(tmp_path / "e.json")
    from datetime import date, timedelta
    for i in range(60):
        st.mark(date(2026, 1, 1) + timedelta(days=i), "foto", "ok")
    assert len(core.State(tmp_path / "e.json").data["dias"]) == 45
    a, b = core.SingleInstance(tmp_path / "l.lock"), core.SingleInstance(tmp_path / "l.lock")
    assert a.acquire() and not b.acquire()
    a.release()
    assert b.acquire()
    b.release()


def test_log_file_never_contains_the_token(tmp_path):
    log = core.setup_logging(tmp_path / "a.log", secrets=(TOKEN,), console=False)
    log.error("fallo con %s y access_token=%s", TOKEN, TOKEN)
    try:
        raise RuntimeError(f"url ...access_token={TOKEN}")
    except RuntimeError:
        log.exception("boom")
    for h in log.handlers:
        h.flush()
    text = (tmp_path / "a.log").read_text("utf-8")
    assert "fallo con" in text and "boom" in text and TOKEN not in text
    core.setup_logging(tmp_path / "b.log", console=False)             # deja el logger sin handlers del archivo anterior


# --------------------------------------------------------------------------- linea de comandos
def env_file(tmp_path, **extra):
    lines = {"PAGE_ID": PAGE, "PAGE_ACCESS_TOKEN": TOKEN, "LOG_ARCHIVO": str(tmp_path / "auto.log"),
             "ESTADO_ARCHIVO": str(tmp_path / "estado.json"), "SALIDA_IMAGENES": str(tmp_path / "salida"),
             "SALIDA_VIDEOS": str(tmp_path / "salida"), **extra}
    p = tmp_path / ".env"
    p.write_text("\n".join(f"{k}={v}" for k, v in lines.items()), "utf-8")
    return p


def test_cli_rejects_a_bad_configuration(tmp_path, monkeypatch):
    p = tmp_path / ".env"
    p.write_text(f"LOG_ARCHIVO={tmp_path / 'a.log'}\n", "utf-8")
    assert autopiloto.main(["--env", str(p), "--silencioso"]) == 2
    assert "PAGE_ID" in (tmp_path / "a.log").read_text("utf-8")


def test_cli_check_reports_the_page(tmp_path, monkeypatch):
    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def check(self):
            return {"id": PAGE, "name": "Paradoja"}

    monkeypatch.setattr(autopiloto, "GraphClient", FakeClient)
    assert autopiloto.main(["--env", str(env_file(tmp_path)), "--check", "--silencioso"]) == 0
    log = (tmp_path / "auto.log").read_text("utf-8")
    assert "Paradoja" in log and TOKEN not in log

    class Broken(FakeClient):
        def check(self):
            raise GraphError("token inválido", code=190)

    monkeypatch.setattr(autopiloto, "GraphClient", Broken)
    assert autopiloto.main(["--env", str(env_file(tmp_path)), "--check", "--silencioso"]) == 1


def test_cli_dry_run_now_needs_no_credentials_and_publishes_nothing(tmp_path, monkeypatch):
    p = tmp_path / ".env"
    p.write_text(f"LOG_ARCHIVO={tmp_path / 'auto.log'}\nESTADO_ARCHIVO={tmp_path / 'e.json'}\nSALIDA_IMAGENES={tmp_path / 'salida'}\n", "utf-8")
    monkeypatch.setattr(autopiloto, "LOCK_FILE", tmp_path / "x.lock")

    def fake_generator(cmd, timeout_s, runner=None, cwd=None):
        make_files(tmp_path, "foto")
        return "ok"

    monkeypatch.setattr(core.media, "run_generator", fake_generator)
    assert autopiloto.main(["--env", str(p), "--dry-run", "--ahora", "foto", "--silencioso"]) == 0
    assert "[PRUEBA]" in (tmp_path / "auto.log").read_text("utf-8")


def test_cli_refuses_a_second_instance(tmp_path, monkeypatch):
    monkeypatch.setattr(autopiloto, "LOCK_FILE", tmp_path / "x.lock")
    first = core.SingleInstance(tmp_path / "x.lock")
    assert first.acquire()
    try:
        assert autopiloto.main(["--env", str(env_file(tmp_path)), "--silencioso"]) == 3
    finally:
        first.release()
    logging.getLogger("autopiloto").handlers.clear()
