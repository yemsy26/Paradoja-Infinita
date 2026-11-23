"""Pruebas del autopiloto con la API de Meta y los generadores simulados (sin red, sin GPU y sin publicar nada)."""
import dataclasses
import json
import logging
import os
import random
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

import autopiloto
from paradoja.autopilot import core, media
from paradoja.autopilot import state as state_mod
from paradoja.autopilot.envfile import Config, load_env, parse_env, parse_times, redact
from paradoja.autopilot.graph import GraphClient, GraphError
from paradoja.autopilot.state import State, atomic_write

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
    text = ("# comentario\nPAGE_ID=123\nexport PAGE_ACCESS_TOKEN = \"abc def\"  \nHORARIOS_FOTOS=11:30,17:00 # mañana\n"
            "VACIA=\nmal linea\n1MALA=x\n'QUOTED'=y\nHORARIOS_VIDEOS='18:00'\n")
    assert parse_env(text) == {"PAGE_ID": "123", "PAGE_ACCESS_TOKEN": "abc def", "HORARIOS_FOTOS": "11:30,17:00", "VACIA": "",
                               "HORARIOS_VIDEOS": "18:00"}
    p = tmp_path / ".env"
    p.write_text("﻿PAGE_ID=999\n", "utf-8")
    assert load_env(p) == {"PAGE_ID": "999"} and load_env(tmp_path / "no_existe") == {}


def test_parse_times_sorts_dedupes_and_reports_bad_values():
    assert parse_times("17:00, 9:05;11:30 17:00") == (("09:05", "11:30", "17:00"), [])
    assert parse_times("") == ((), []) and parse_times("  ,, ") == ((), [])
    times, errors = parse_times("10:00,25:00,abc,12:75", "HORARIOS_FOTOS")
    assert times == ("10:00",) and len(errors) == 3 and all("HORARIOS_FOTOS" in e for e in errors)


def test_config_defaults_overrides_and_validation(tmp_path):
    cfg = Config.from_sources({"PAGE_ID": PAGE, "PAGE_ACCESS_TOKEN": TOKEN}, environ={}, root=tmp_path)
    assert (cfg.photo_times, cfg.video_times, cfg.jitter_min, cfg.jitter_max) == (("11:30",), ("18:00",), 1, 15)
    assert (cfg.max_photos, cfg.max_videos) == (1, 1) and cfg.state_file == tmp_path / "estado_autopiloto.json"
    assert cfg.ai_label is True and cfg.dry_run is False and cfg.version == "v26.0" and cfg.problems() == []
    over = Config.from_sources({"PAGE_ID": PAGE, "PAGE_ACCESS_TOKEN": TOKEN, "HORARIOS_FOTOS": "09:05", "JITTER_MAX": "7",
                                "IA_ETIQUETA": "0", "DRY_RUN": "1", "SALIDA_IMAGENES": "imgs"},
                               environ={"HORARIOS_FOTOS": "10:00,15:30", "OTRA": "x"}, root=tmp_path)
    assert over.photo_times == ("10:00", "15:30") and over.jitter_max == 7 and not over.ai_label and over.dry_run   # el entorno manda
    assert over.image_out == tmp_path / "imgs"
    bad = Config.from_sources({"PAGE_ID": "abc", "PAGE_ACCESS_TOKEN": "PEGA_AQUI_TU_TOKEN_DE_PAGINA_DE_LARGA_DURACION",
                               "HORARIOS_FOTOS": "25:00", "HORARIOS_VIDEOS": "7pm", "JITTER_MIN": "20", "JITTER_MAX": "5",
                               "MAX_FOTOS_DIA": "99", "MAX_VIDEOS_DIA": "muchos", "GRAPH_VERSION": "26"}, environ={}, root=tmp_path)
    problems = " ".join(bad.problems())
    for needle in ("PAGE_ID", "PAGE_ACCESS_TOKEN", "HORARIOS_FOTOS", "HORARIOS_VIDEOS", "JITTER", "MAX_FOTOS_DIA",
                   "MAX_VIDEOS_DIA", "GRAPH_VERSION"):
        assert needle in problems
    assert Config.from_sources({}, environ={}, root=tmp_path).problems(need_credentials=False) == []


def test_multiple_schedules_and_independent_limits(tmp_path):
    cfg = Config.from_sources({"HORARIOS_FOTOS": "09:00, 13:30,20:00", "HORARIOS_VIDEOS": "12:00,19:00",
                               "MAX_FOTOS_DIA": "2"}, environ={}, root=tmp_path)
    assert cfg.photo_times == ("09:00", "13:30", "20:00") and cfg.video_times == ("12:00", "19:00")
    assert (cfg.max_photos, cfg.max_videos) == (2, 2)                     # sin MAX_VIDEOS_DIA: tantos como horarios
    assert (cfg.limit("foto"), cfg.limit("video")) == (2, 2) and cfg.times("foto") == cfg.photo_times
    cfg = Config.from_sources({"HORARIOS_FOTOS": "09:00", "HORARIOS_VIDEOS": "12:00,19:00", "MAX_FOTOS_DIA": "3",
                               "MAX_VIDEOS_DIA": "1"}, environ={}, root=tmp_path)
    assert (cfg.limit("foto"), cfg.limit("video")) == (3, 1)
    off = Config.from_sources({"HORARIOS_FOTOS": "", "HORARIOS_VIDEOS": "18:00"}, environ={}, root=tmp_path)
    assert off.photo_times == () and off.limit("foto") == 0 and off.limit("video") == 1 and off.problems(False) == []
    assert "ninguna franja" in " ".join(Config.from_sources({"HORARIOS_FOTOS": "", "HORARIOS_VIDEOS": ""}, environ={},
                                                           root=tmp_path).problems(False))
    assert Config.from_sources({"MAX_VIDEOS_DIA": "0"}, environ={}, root=tmp_path).limit("video") == 0


def test_old_settings_still_work_with_a_notice(tmp_path):
    cfg = Config.from_sources({"FOTO_HORA": "10:15", "VIDEO_HORA": "19:45", "MAX_POSTS_DIA": "2"}, environ={}, root=tmp_path)
    assert cfg.photo_times == ("10:15",) and cfg.video_times == ("19:45",) and (cfg.max_photos, cfg.max_videos) == (1, 1)
    notes = " ".join(cfg.notes)
    assert "FOTO_HORA" in notes and "VIDEO_HORA" in notes and "MAX_POSTS_DIA" in notes
    new = Config.from_sources({"FOTO_HORA": "10:15", "HORARIOS_FOTOS": "08:00"}, environ={}, root=tmp_path)
    assert new.photo_times == ("08:00",)                                  # la clave nueva manda


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
class FakeSched:
    """Sustituye a `schedule.Scheduler`: solo anota (segundos, funcion, argumentos)."""

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


class Killed(BaseException):
    """El proceso muere de golpe (corte de luz, cierre de la ventana, reinicio de Windows): nadie lo captura."""


DAY = date(2026, 11, 23)


def combo_handler(state):
    """Fotos y Reels a la vez: /photos responde al momento y el resto sigue el flujo de tres fases del Reel."""
    reels = reel_handler(state)
    return lambda m, u, kw: Resp(200, {"id": "9", "post_id": f"{PAGE}_9"}) if u.endswith("/photos") else reels(m, u, kw)


def build(tmp_path, handler=None, *, dry=False, **cfg_kw):
    """Autopilot con generadores y API simulados. -> (auto, http, calls_del_generador)."""
    cfg = Config(page_id=PAGE, token=TOKEN, dry_run=dry, image_out=tmp_path / "salida", video_out=tmp_path / "salida",
                 state_file=tmp_path / "estado.json", log_file=tmp_path / "x.log", **cfg_kw)
    gen_calls = []
    counter = iter(range(1, 100))

    def runner(cmd, **kw):
        if cmd[1] == "-c":                                       # comprobacion de modulos del Python de los generadores
            return SimpleNamespace(returncode=0, stdout=b"MISSING:", stderr=b"")
        gen_calls.append(cmd)
        make_files(tmp_path, "foto" if cmd[1].endswith("generador_imagenes.py") else "video", n=next(counter))
        return SimpleNamespace(returncode=0, stdout=b"ok", stderr=b"")

    http = FakeHttp(handler or (lambda m, u, kw: Resp(200, {"id": "9", "post_id": "9_9", "video_id": "777", "success": True,
                                                              "status": {"video_status": "ready"}})))
    cl = GraphClient(PAGE, TOKEN, "v26.0", http=http, sleep=lambda s: None)
    when = [datetime(2026, 11, 23, 11, 40)]
    auto = core.Autopilot(cfg, cl, State(cfg.state_file), runner=runner, probe=lambda p: GOOD_VIDEO,
                          now=lambda: when[0], rng=random.Random(1), sleep=lambda s: None, sched=FakeSched(), cancel=object())
    auto.when = when
    return auto, http, gen_calls


def reopen(auto, **changes):
    """Cierra el programa y lo vuelve a abrir: el estado se lee de nuevo desde el disco; mismo reloj, API y generadores."""
    cfg = dataclasses.replace(auto.cfg, **changes) if changes else auto.cfg
    new = core.Autopilot(cfg, auto.client, State(cfg.state_file), runner=auto.runner, probe=auto.probe, now=auto.now,
                         rng=random.Random(2), sleep=auto.sleep, sched=FakeSched(), cancel=object())
    new.when = auto.when
    return new


def run_jobs(auto):
    """Llega la hora de todas las tareas programadas: se ejecutan en orden y la lista se vacia."""
    jobs, auto.sched.jobs = sorted(auto.sched.jobs, key=lambda j: j[0]), []
    for _n, fn, args in jobs:
        fn(*args)


def on_disk(auto, day="2026-11-23") -> dict:
    return json.loads(auto.cfg.state_file.read_text("utf-8"))["dias"][day]


def test_photo_task_generates_publishes_and_records_the_day(tmp_path):
    auto, http, gen = build(tmp_path)
    out = auto.execute("foto", "11:30")
    assert out.status == "ok" and gen[0][1].endswith("generador_imagenes.py") and "aleatorio" in gen[0] and "--no-copy" in gen[0]
    assert http.calls[0].url.endswith(f"/{PAGE}/photos") and http.calls[0].kw["data"]["caption"].startswith("Hola 👇")
    assert http.calls[0].kw["data"]["alt_text_custom"] == "Imagen de un reto."
    assert auto.state.count(DAY, "foto") == 1 and auto.state.slot(DAY, "foto", "11:30")["estado"] == "ejecutada"
    again = auto.execute("foto", "11:30")
    assert again.status == "skipped" and again.detail == "ya ejecutada" and len(http.calls) == 1   # no se duplica
    day = on_disk(auto)                                                   # y todo esta en el archivo
    assert day["fotos"] == 1 and day["videos"] == 0
    pub = day["publicaciones"][0]
    assert pub["tipo"] == "foto" and pub["franja"] == "11:30" and pub["archivo"] == "foto_prueba_1.png"
    assert pub["id"] == "9_9" and pub["estado"] == "ok" and pub["hora"] == "11:40:00"
    assert State(tmp_path / "estado.json").count(DAY, "foto") == 1        # sobrevive al reinicio


def test_video_task_uses_main_py_in_random_mode(tmp_path):
    auto, http, gen = build(tmp_path)
    out = auto.execute("video", "18:00")
    assert out.status == "ok" and gen[0][1].endswith("main.py") and gen[0][gen[0].index("--mode") + 1] == "random"
    assert "--no-copy" in gen[0] and any(c.url.endswith("/video_reels") for c in http.calls)


def test_video_publishing_flow_end_to_end(tmp_path):
    state = {}
    auto, http, _ = build(tmp_path, reel_handler(state))
    out = auto.execute("video", "18:00")
    assert out.status == "ok" and out.post_id == "777" and state["phases"] == ["start", "finish"]
    fin = next(c for c in http.calls if is_finish(c))
    assert fin.kw["data"]["is_ai_generated"] == "true" and fin.kw["data"]["description"].startswith("Hola")
    assert on_disk(auto)["publicaciones"][0]["id"] == "777"
    auto2, http2, _ = build(tmp_path / "otro", reel_handler({}), ai_label=False)
    auto2.execute("video", "18:00")
    assert next(c for c in http2.calls if is_finish(c)).kw["data"]["is_ai_generated"] == "false"


def test_daily_limits_are_independent_per_type_and_dry_run_records_nothing(tmp_path):
    auto, http, _ = build(tmp_path, photo_times=("11:30", "15:00"), max_photos=1)
    assert auto.execute("foto", "11:30").status == "ok"
    out = auto.execute("foto", "15:00")                                   # el limite de fotos (1) ya esta cubierto...
    assert out.status == "skipped" and out.detail == "límite diario" and len(http.calls) == 1
    assert auto.state.slot(DAY, "foto", "15:00")["estado"] == "omitida"   # ...y se anota la omision con su motivo
    assert "límite diario de fotos" in auto.state.slot(DAY, "foto", "15:00")["motivo"]
    assert auto.execute("video", "18:00").status == "ok"                  # ...pero el de videos es otro: sigue libre
    assert auto.state.count(DAY, "foto") == 1 and auto.state.count(DAY, "video") == 1 and auto.state.count(DAY) == 2
    assert auto.execute("foto", force=True).status == "ok"                # --ahora ignora los limites
    auto, http, gen = build(tmp_path / "d", dry=True)
    out = auto.execute("foto", "11:30")
    assert out.status == "dry" and not http.calls and gen and not auto.state.count(DAY)
    assert not (tmp_path / "d" / "estado.json").exists()                  # el ensayo no deja rastro en el estado


def test_generator_failure_is_logged_and_the_program_survives(tmp_path):
    auto, http, _ = build(tmp_path)
    auto.runner = lambda cmd, **kw: SimpleNamespace(returncode=1, stdout=b"", stderr=b"CUDA fuera de memoria")
    out = auto.execute("video", "18:00")
    assert out.status == "error" and "CUDA" in out.detail and not http.calls
    slot = auto.state.slot(DAY, "video", "18:00")
    assert slot["estado"] == "error" and slot["intentos"] == 1 and "CUDA" in slot["error"]
    assert auto.execute("video", "18:00").status == "error"                 # un error no bloquea el siguiente intento
    assert auto.state.slot(DAY, "video", "18:00")["intentos"] == 2
    auto.runner = lambda cmd, **kw: (_ for _ in ()).throw(RuntimeError("explotó"))
    assert auto._guard(auto.execute, "foto", "11:30").status == "error"     # ni siquiera una excepcion inesperada


def test_requirements_failure_blocks_publication(tmp_path):
    auto, http, _ = build(tmp_path)
    auto.probe = lambda p: {"streams": [{"codec_type": "video", "width": 300, "height": 300, "r_frame_rate": "30/1"}],
                            "format": {"duration": "10"}}
    out = auto.execute("video", "18:00")
    assert out.status == "error" and "no cumple" in out.detail and not http.calls


def test_transient_api_failures_are_retried_but_ambiguous_ones_are_not(tmp_path):
    seq = iter([err(4, "rate limit"), Resp(200, {"id": "1", "post_id": "1_1"})])
    auto, http, gen = build(tmp_path, lambda m, u, kw: next(seq), retries=2, retry_minutes=20)
    sleeps = []
    auto.sleep = sleeps.append
    out = auto.run_now("foto")
    assert out.status == "ok" and sleeps == [1200] and len(gen) == 1 and len(http.calls) == 2   # no se vuelve a renderizar
    assert auto.state.count(DAY, "foto") == 1                                # y se anota una sola publicacion
    auto, http, _ = build(tmp_path / "b", lambda m, u, kw: ReadTimeout("sin respuesta"))
    out = auto.execute("foto", "11:30")
    assert out.status == "ambiguous" and auto.state.count(DAY, "foto") == 1   # cuenta como publicado
    assert auto.state.slot(DAY, "foto", "11:30")["estado"] == "ambigua"
    auto, http, _ = build(tmp_path / "c", lambda m, u, kw: err(190, "token caducado"))
    assert auto.run_now("foto").status == "error" and len(http.calls) == 1   # error fatal: sin reintentos
    auto, http, _ = build(tmp_path / "d", lambda m, u, kw: err(4, "limite"), retries=1)
    out = auto.run_now("foto")                                               # agota los reintentos
    assert out.status == "error" and len(http.calls) == 2                    # 1 intento + 1 reintento
    assert [s["estado"] for s in auto.state.data["dias"]["2026-11-23"]["franjas"].values()] == ["error"]
    assert auto.state.count(DAY) == 0                                        # un error no gasta el cupo del dia


# --------------------------------------------------------------------------- plan del dia: solo franjas pendientes
def test_jitter_is_random_between_one_and_fifteen_minutes(tmp_path):
    auto, _, _ = build(tmp_path)
    auto.when[0] = datetime(2026, 11, 23, 11, 0)                            # antes de la hora base (11:30)
    base, seen = datetime(2026, 11, 23, 11, 30), set()
    for seed in range(300):
        auto.rng = random.Random(seed)
        planned, _ = auto.plan(persist=False)
        p = next(x for x in planned if x.kind == "foto")
        delay = (p.when - base).total_seconds()
        assert 60 <= delay <= 900 and not p.catchup
        seen.add(delay)
    assert len(seen) > 150                                                  # nunca la misma hora exacta
    assert min(seen) < 120 and max(seen) > 840


def test_plan_schedules_only_pending_slots_within_each_limit(tmp_path):
    auto, _, _ = build(tmp_path, photo_times=("09:00", "11:30", "15:00", "20:00"), max_photos=2,
                       video_times=("12:00", "19:00"), max_videos=1)
    auto.state.finish(DAY, "foto", "09:00", "ok", "madrugada.png", "55")        # la de las 09:00 ya salio
    planned, omitted = auto.plan()
    assert [(p.kind, p.slot) for p in sorted(planned, key=lambda p: (p.kind, p.slot))] == [("foto", "11:30"), ("video", "12:00")]
    assert {(k, f) for k, f, _ in omitted} == {("foto", "15:00"), ("foto", "20:00"), ("video", "19:00")}
    assert all("límite diario" in m for _, _, m in omitted)
    assert auto.state.slot(DAY, "foto", "15:00")["estado"] == "omitida" and auto.state.slot(DAY, "foto", "11:30")["estado"] == "programada"
    foto = next(p for p in planned if p.kind == "foto")
    assert foto.catchup and foto.when > auto.now()                          # las 11:30 ya pasaron (11:40): se recupera
    auto.start_day()
    assert len(auto.sched.jobs) == 2 and {a[:2] for _n, _f, a in auto.sched.jobs} == {("foto", "11:30"), ("video", "12:00")}
    assert all(a[2] == DAY for _n, _f, a in auto.sched.jobs)


def test_late_slots_are_omitted_after_a_long_sleep(tmp_path):
    auto, _, _ = build(tmp_path, tolerance_hours=3.0)
    auto.when[0] = datetime(2026, 11, 23, 15, 0)                            # la franja era a las 11:30: pasaron 3,5 h
    planned, omitted = auto.plan()
    assert not [p for p in planned if p.kind == "foto"] and omitted[0][:2] == ("foto", "11:30") and "3.5 h" in omitted[0][2]
    assert auto.state.slot(DAY, "foto", "11:30")["estado"] == "omitida"
    assert auto.execute("foto", "11:30").detail == "hora pasada"             # y si el trabajo despierta tarde, tampoco publica
    auto.when[0] = datetime(2026, 11, 23, 11, 31)
    assert [p.slot for p in reopen(auto).plan(persist=False)[0] if p.kind == "foto"] == ["11:30"]


def test_manual_publication_counts_toward_the_day_and_survives_a_restart(tmp_path):
    auto, http, _ = build(tmp_path)
    assert auto.run_now("foto").status == "ok"                               # --ahora foto
    new = reopen(auto)
    planned, omitted = new.plan()
    assert [(p.kind, p.slot) for p in planned] == [("video", "18:00")]       # la foto de las 11:30 ya no hace falta
    assert omitted == []                                                     # no «se omite»: la cubre la publicacion manual
    cover = new.state.slot(DAY, "foto", "11:30")
    assert cover["estado"] == "ejecutada" and "manual" in cover["nota"] and cover["archivo"] == "foto_prueba_1.png"
    new.start_day()
    assert len(new.sched.jobs) == 1 and len(http.calls) == 1


def test_earlier_publications_cover_their_slot_instead_of_recovering_it(tmp_path):
    """Caso real: horarios 09:30,16:00 y 12:30,19:30 (2 de cada) y, a las 14:25, ya habian salido una foto (13:42) y un Reel
    (13:53) de antes de configurar las franjas. El Reel de las 12:30 NO debe «recuperarse» ahora: cubre esa franja."""
    legacy = tmp_path / "autopiloto_estado.json"
    legacy.write_text(json.dumps({"dias": {"2026-11-23": {
        "foto": {"estado": "ok", "hora": "13:42:58", "archivo": "f.png", "id": "10_20"},
        "video": {"estado": "ok", "hora": "13:53:53", "archivo": "v.mp4", "id": "777"}}}}), "utf-8")
    auto, http, gen = build(tmp_path, photo_times=("09:30", "16:00"), max_photos=2, video_times=("12:30", "19:30"), max_videos=2)
    auto.state = State(auto.cfg.state_file, legacy=legacy, clock=auto.now)
    auto.when[0] = datetime(2026, 11, 23, 14, 25)
    planned, omitted = auto.plan()
    assert sorted((p.kind, p.slot) for p in planned) == [("foto", "16:00"), ("video", "19:30")]
    assert not [p for p in planned if p.catchup] and omitted == []             # nada de recuperar a las 12:30
    assert min(p.when for p in planned) > auto.now()
    day = on_disk(auto)
    assert day["franjas"]["foto@09:30"]["estado"] == "ejecutada" and "anterior" in day["franjas"]["video@12:30"]["nota"]
    assert sorted(p["cubre"] for p in day["publicaciones"]) == ["09:30", "12:30"]
    text = chr(10).join(auto.status_lines())
    assert "Franja video 12:30: ejecutada a las 13:53:53 (cubierta por una publicación anterior)" in text
    for _ in range(3):                                                        # reiniciar no hace que cubra mas franjas
        again = reopen(auto)
        assert sorted((p.kind, p.slot) for p in again.plan()[0]) == [("foto", "16:00"), ("video", "19:30")]
    assert sorted(p["cubre"] for p in on_disk(auto)["publicaciones"]) == ["09:30", "12:30"] and not http.calls


def test_a_publication_before_every_slot_covers_the_first_one(tmp_path):
    auto, _, _ = build(tmp_path, photo_times=("09:30", "16:00"), max_photos=2, video_times=())
    auto.when[0] = datetime(2026, 11, 23, 8, 0)
    assert auto.run_now("foto").status == "ok"                                # --ahora foto a las 08:00
    auto.when[0] = datetime(2026, 11, 23, 8, 30)
    planned, omitted = reopen(auto).plan()
    assert [p.slot for p in planned] == ["16:00"] and omitted == []           # la de las 09:30 queda cubierta
    auto.when[0] = datetime(2026, 11, 23, 8, 45)
    assert reopen(auto).state.slot(DAY, "foto", "09:30")["estado"] == "ejecutada"


def test_estado_shows_covered_slots_without_writing_anything(tmp_path):
    auto, _, _ = build(tmp_path)
    auto.run_now("foto")                                                      # una foto a mano a las 11:40
    before = auto.cfg.state_file.read_bytes()
    viewer = core.Autopilot(auto.cfg, None, State(auto.cfg.state_file, readonly=True, clock=auto.now), now=auto.now)
    assert any("Franja foto  11:30: ejecutada a las 11:40:00 (cubierta por una publicación manual)" in x
               for x in viewer.status_lines())
    assert auto.cfg.state_file.read_bytes() == before


def test_real_schedule_runs_the_jittered_job_once(tmp_path):
    pytest.importorskip("schedule")
    auto, http, _ = build(tmp_path, video_times=())                          # solo la imagen
    sch = core.build_scheduler(auto.cfg, auto)
    assert sch.get_jobs() == []                                              # no hay tareas fijas: solo las del plan
    assert len(auto.start_day()) == 1
    assert len(sch.get_jobs()) == 1 and 60 <= sch.get_jobs()[0].interval <= 900   # 11:40 ya pasada: hora actual + retraso
    sch.run_all()                                                            # llega la hora real
    assert len(http.calls) == 1 and sch.get_jobs() == []                     # se ejecuto y la tarea de una sola vez desaparecio
    assert auto.state.count(DAY, "foto") == 1


def test_run_forever_survives_scheduler_errors_and_calls_the_hook():
    calls, hooks = {"n": 0}, []

    class Sch:
        def run_pending(self):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("fallo raro")

    def hook():
        hooks.append(1)
        if len(hooks) == 3:
            raise RuntimeError("el gancho también puede fallar")

    ticks = []
    core.run_forever(Sch(), stop=lambda: len(ticks) >= 4, sleep=ticks.append, hook=hook)
    assert len(ticks) == 4 and len(hooks) == 4 and calls["n"] == 3          # un fallo del gancho no mata el bucle


def test_midnight_rollover_replans_the_new_day(tmp_path):
    auto, http, _ = build(tmp_path)
    auto.start_day()
    assert auto.planned_day == DAY and len(auto.sched.jobs) == 2
    auto.sched.jobs.clear()
    auto.ensure_plan()                                                       # mismo dia: no replanifica
    assert not auto.sched.jobs
    auto.when[0] = datetime(2026, 11, 24, 0, 5)                              # pasa la medianoche
    auto.ensure_plan()
    assert auto.planned_day == date(2026, 11, 24) and len(auto.sched.jobs) == 2
    assert all(a[2] == date(2026, 11, 24) for _n, _f, a in auto.sched.jobs)
    assert auto.execute("foto", "11:30", DAY).detail == "otro día" and not http.calls   # una tarea rezagada de ayer no publica


# --------------------------------------------------------------------------- reinicio sin duplicados
def test_restart_remembers_what_was_published_and_does_not_duplicate(tmp_path):
    auto, http, gen = build(tmp_path, combo_handler({}))
    auto.start_day()
    run_jobs(auto)                                                           # llegan las dos horas: sale 1 foto y 1 Reel
    posted = len(http.calls)
    assert (auto.state.count(DAY, "foto"), auto.state.count(DAY, "video")) == (1, 1) and posted > 2 and len(gen) == 2
    day = on_disk(auto)
    assert (day["fotos"], day["videos"]) == (1, 1)
    assert {p["archivo"] for p in day["publicaciones"]} == {"foto_prueba_1.png", "video_prueba_2.mp4"}
    assert {p["id"] for p in day["publicaciones"]} == {f"{PAGE}_9", "777"}
    assert {k: v["estado"] for k, v in day["franjas"].items()} == {"foto@11:30": "ejecutada", "video@18:00": "ejecutada"}

    for hour in (datetime(2026, 11, 23, 11, 45), datetime(2026, 11, 23, 14, 0), datetime(2026, 11, 23, 23, 59)):
        auto.when[0] = hour                                                  # el PC se reinicia varias veces durante el dia
        new = reopen(auto)
        assert (new.state.count(DAY, "foto"), new.state.count(DAY, "video")) == (1, 1)
        assert new.start_day() == [] and new.sched.jobs == []                # no queda nada pendiente
        assert "fotos 1/1 | videos 1/1" in new.status_lines()[0]
    assert len(http.calls) == posted and len(gen) == 2                       # ni una llamada ni un render de mas
    stale = reopen(auto)
    assert stale.execute("foto", "11:30").status == "skipped" and stale.execute("video", "18:00").status == "skipped"
    assert len(http.calls) == posted


def test_restart_between_slots_only_schedules_the_one_still_pending(tmp_path):
    auto, http, _ = build(tmp_path)
    auto.when[0] = datetime(2026, 11, 23, 11, 29)
    auto.start_day()
    assert {a[:2] for _n, _f, a in auto.sched.jobs} == {("foto", "11:30"), ("video", "18:00")}
    foto_job = next(j for j in auto.sched.jobs if j[2][0] == "foto")
    foto_job[1](*foto_job[2])                                                # sale la foto; se cierra el programa antes del Reel
    assert len(http.calls) == 1
    auto.when[0] = datetime(2026, 11, 23, 12, 0)
    new = reopen(auto)
    new.start_day()
    assert [a[:2] for _n, _f, a in new.sched.jobs] == [("video", "18:00")]   # solo queda el Reel
    lines = new.status_lines()
    assert lines[0].endswith("fotos 1/1 | videos 0/1") and any("Franja foto  11:30: ejecutada a las 11:29:00" in x for x in lines)
    assert any("pendiente, prevista a las 18:" in x for x in lines)


def test_restart_keeps_the_time_already_chosen_for_a_pending_slot(tmp_path):
    auto, _, _ = build(tmp_path)
    auto.when[0] = datetime(2026, 11, 23, 11, 0)
    first, _ = auto.plan()
    foto = next(p for p in first if p.kind == "foto")
    auto.when[0] = datetime(2026, 11, 23, 11, 20)                            # reinicio antes de la hora prevista
    second = next(p for p in reopen(auto).plan()[0] if p.kind == "foto")
    assert second.when == foto.when and not second.catchup                   # no se vuelve a sortear el retraso
    auto.when[0] = foto.when + timedelta(minutes=10)                         # el PC estuvo apagado en su hora: recuperacion
    late = next(p for p in reopen(auto).plan()[0] if p.kind == "foto")
    assert late.catchup and 5 <= (late.when - auto.now()).total_seconds() <= 60


def test_crash_while_publishing_is_ambiguous_after_restart_and_never_repeated(tmp_path):
    def dies(m, u, kw):
        raise Killed()

    auto, http, gen = build(tmp_path, dies)
    with pytest.raises(Killed):
        auto.execute("foto", "11:30")                                        # el proceso muere hablando con Meta
    assert on_disk(auto)["franjas"]["foto@11:30"]["estado"] == "en_curso"    # lo ultimo que quedo en disco: anotacion previa
    assert len(http.calls) == 1 and on_disk(auto)["publicaciones"] == []

    new = reopen(auto)                                                       # Windows se reinicia y vuelve el autopiloto
    slot = new.state.slot(DAY, "foto", "11:30")
    assert slot["estado"] == "ambigua" and "cerró" in slot["error"]
    assert new.state.count(DAY, "foto") == 1                                 # pudo publicarse: cuenta para el limite
    assert on_disk(auto)["publicaciones"][0]["estado"] == "ambiguo" and on_disk(auto)["fotos"] == 1
    planned, _ = new.plan()
    assert [p.kind for p in planned] == ["video"]                            # la foto NO se repite
    assert new.execute("foto", "11:30").status == "skipped"
    assert any("AMBIGUA" in line for line in new.status_lines())
    assert len(http.calls) == 1 and len(gen) == 1


def test_crash_while_generating_loses_nothing_and_publishes_once_after_restart(tmp_path):
    auto, http, gen = build(tmp_path, video_times=())
    good = auto.runner

    def dies(cmd, **kw):
        if cmd[1] == "-c":
            return good(cmd, **kw)
        raise Killed()

    auto.runner = dies
    with pytest.raises(Killed):
        auto.execute("foto", "11:30")                                        # se apaga el PC en mitad del render
    assert not http.calls and "foto@11:30" not in (on_disk(auto) if auto.cfg.state_file.exists() else {"franjas": {}})["franjas"]
    new = reopen(auto)
    new.runner = good                                                        # al volver, el render funciona
    new.start_day()
    run_jobs(new)
    assert new.state.count(DAY, "foto") == 1 and len([c for c in http.calls if c.url.endswith("/photos")]) == 1
    assert reopen(auto).start_day() == []                                    # la foto no vuelve a programarse


def test_slot_with_error_is_retried_after_a_restart_but_not_forever(tmp_path):
    auto, http, _ = build(tmp_path)
    auto.runner = lambda cmd, **kw: SimpleNamespace(returncode=1, stdout=b"", stderr=b"CUDA fuera de memoria")
    for _ in range(3):
        cur = reopen(auto)
        assert [p.slot for p in cur.plan(persist=False)[0] if p.kind == "foto"] == ["11:30"]   # se vuelve a intentar
        assert cur.execute("foto", "11:30").status == "error"
    assert reopen(auto).state.slot(DAY, "foto", "11:30")["intentos"] == 3
    assert not [p for p in reopen(auto).plan(persist=False)[0] if p.kind == "foto"]            # tope: no hay bucle de errores
    assert not http.calls


def test_an_uploaded_file_is_never_published_twice(tmp_path):
    auto, http, _ = build(tmp_path)
    art = auto.generate("foto")
    assert auto.publish(art, "11:30", DAY).status == "ok"
    out = reopen(auto).publish(art, "15:00", DAY)                            # mismo archivo, otra franja, otro proceso
    assert out.status == "error" and "ya se subió" in out.detail and len(http.calls) == 1


def test_failing_to_save_the_state_blocks_publication(tmp_path, monkeypatch):
    auto, http, _ = build(tmp_path)
    monkeypatch.setattr(State, "begin", lambda *a, **k: (_ for _ in ()).throw(OSError("disco lleno")))
    out = auto.execute("foto", "11:30")
    assert out.status == "error" and "estado" in out.detail and not http.calls   # sin anotacion previa no se publica


def test_status_lines_summarise_counts_files_and_slots(tmp_path):
    auto, _, _ = build(tmp_path, photo_times=("11:30", "17:00"), max_photos=2, video_times=("18:00",), max_videos=1)
    assert "Todavía no se ha publicado nada" in "\n".join(auto.status_lines())
    auto.state.finish(DAY, "foto", "11:30", "ok", "reto.png", "123_456")
    auto.state.finish(DAY, "video", "18:00", "ambiguo", "reel.mp4", None, error="se cortó")
    auto.state.omit(DAY, "foto", "17:00", "límite diario de fotos cubierto (2)")
    text = "\n".join(auto.status_lines())
    assert "Resumen de hoy (2026-11-23): fotos 1/2 | videos 1/1" in text
    assert "reto.png  id 123_456" in text and "reel.mp4" in text and "AMBIGUA" in text
    assert "Franja foto  11:30: ejecutada a las 11:40:00" in text and "Franja foto  17:00: omitida: límite diario" in text
    assert "Franja video 18:00: AMBIGUA" in text
    off = build(tmp_path / "x", video_times=())[0]
    assert "videos 0/0 (desactivado)" in off.status_lines()[0] and not any("Franja video" in x for x in off.status_lines())


# --------------------------------------------------------------------------- estado en disco: escritura atomica y recuperacion
def test_atomic_write_never_leaves_a_half_written_file(tmp_path, monkeypatch):
    path = tmp_path / "estado.json"
    atomic_write(path, '{"version": 1}')
    atomic_write(path, '{"version": 2}')
    assert json.loads(path.read_text("utf-8")) == {"version": 2}
    assert json.loads((tmp_path / "estado.json.bak").read_text("utf-8")) == {"version": 1}   # copia del guardado anterior
    assert not (tmp_path / "estado.json.tmp").exists()                                          # sin temporales sueltos

    def boom(src, dst):
        raise OSError("se fue la luz")

    monkeypatch.setattr(state_mod.os, "replace", boom)
    with pytest.raises(OSError):
        atomic_write(path, '{"version": 3, "texto": "' + "x" * 5000 + '"}')
    monkeypatch.undo()
    assert json.loads(path.read_text("utf-8")) == {"version": 2}             # el archivo bueno sigue entero


def test_atomic_write_retries_when_windows_has_the_file_open(tmp_path, monkeypatch):
    path = tmp_path / "estado.json"
    atomic_write(path, "{}")
    real, calls = os.replace, {"n": 0}

    def busy(src, dst):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise PermissionError("el antivirus lo tiene abierto")
        return real(src, dst)

    monkeypatch.setattr(state_mod.os, "replace", busy)
    monkeypatch.setattr(state_mod.time, "sleep", lambda s: None)
    atomic_write(path, '{"ok": true}')
    assert calls["n"] == 3 and json.loads(path.read_text("utf-8")) == {"ok": True}


def test_every_state_change_is_saved_right_away(tmp_path):
    st = State(tmp_path / "e.json", clock=lambda: datetime(2026, 11, 23, 9, 5, 7))
    st.begin(DAY, "foto", "09:00", "a.png")
    assert json.loads((tmp_path / "e.json").read_text("utf-8"))["dias"]["2026-11-23"]["franjas"]["foto@09:00"]["estado"] == "en_curso"
    st.finish(DAY, "foto", "09:00", "ok", "a.png", "1_2")
    st.omit(DAY, "video", "18:00", "motivo")
    again = State(tmp_path / "e.json")
    assert again.count(DAY, "foto") == 1 and again.slot(DAY, "foto", "09:00")["hora"] == "09:05:07"
    assert again.slot(DAY, "video", "18:00") == {"estado": "omitida", "hora": "09:05:07", "motivo": "motivo"}
    assert again.uploaded("a.png") and not again.uploaded("b.png") and not again.uploaded("")
    with st.batch():                                                         # varios cambios, un solo guardado
        mtime = (tmp_path / "e.json").stat().st_mtime_ns
        st.omit(DAY, "foto", "12:00", "x")
        st.omit(DAY, "foto", "13:00", "y")
        assert (tmp_path / "e.json").stat().st_mtime_ns == mtime
    assert State(tmp_path / "e.json").slot(DAY, "foto", "13:00")["estado"] == "omitida"


def test_corrupt_state_is_set_aside_and_the_backup_is_recovered(tmp_path):
    path = tmp_path / "e.json"
    st = State(path)
    st.finish(DAY, "foto", "11:30", "ok", "a.png", "1")
    st.finish(DAY, "video", "18:00", "ok", "b.mp4", "2")
    path.write_text('{"version": 2, "dias": {"2026-11-23": {"publi', "utf-8")        # archivo cortado a medias
    new = State(path)
    assert new.count(DAY, "foto") == 1                                        # la copia .bak tenia lo anterior al ultimo cambio
    assert list(tmp_path.glob("e.json.corrupto-*"))                           # el dañado se conserva aparte, no se borra
    assert json.loads(path.read_text("utf-8"))["version"] == 2                # y el principal vuelve a estar sano
    path.write_text("basura", "utf-8")
    (tmp_path / "e.json.bak").write_text("tambien basura", "utf-8")
    empty = State(path)                                                       # sin copia valida: parte de cero, sin romperse
    assert empty.data["dias"] == {} and len(list(tmp_path.glob("e.json.corrupto-*"))) >= 1
    empty.finish(DAY, "foto", "11:30", "ok", "c.png", "3")
    assert State(path).count(DAY, "foto") == 1


def test_old_state_format_is_migrated_once(tmp_path):
    legacy = tmp_path / "autopiloto_estado.json"
    legacy.write_text(json.dumps({"dias": {
        "2026-11-23": {"foto": {"estado": "ok", "hora": "13:42:58", "archivo": "f.png", "id": "10_20"},
                       "video": {"estado": "ambiguo", "hora": "13:53:53", "archivo": "v.mp4", "error": "x"}},
        "2026-11-22": {"foto": {"estado": "error", "error": "fallo"}}}}), "utf-8")
    before = legacy.read_bytes()
    st = State(tmp_path / "estado_autopiloto.json", legacy=legacy)
    assert st.count(DAY, "foto") == 1 and st.count(DAY, "video") == 1          # lo publicado hoy se conserva
    assert st.count(date(2026, 11, 22)) == 0                                   # los errores no cuentan como publicaciones
    pub = {p["tipo"]: p for p in st.publications(DAY)}
    assert pub["foto"]["archivo"] == "f.png" and pub["foto"]["id"] == "10_20" and pub["foto"]["hora"] == "13:42:58"
    assert pub["video"]["estado"] == "ambiguo"
    assert (tmp_path / "estado_autopiloto.json").exists() and legacy.read_bytes() == before   # el viejo no se toca
    legacy.write_text('{"dias": {}}', "utf-8")
    assert State(tmp_path / "estado_autopiloto.json", legacy=legacy).count(DAY, "foto") == 1   # ya no se vuelve a migrar
    auto, http, _ = build(tmp_path / "b")
    auto.state = State(tmp_path / "estado_autopiloto.json")
    assert auto.state.count(DAY) == 2 and auto.plan(persist=False)[0] == []    # hoy no se republica nada


def test_readonly_state_never_touches_the_file(tmp_path):
    path = tmp_path / "e.json"
    st = State(path)
    st.begin(DAY, "foto", "11:30", "a.png")                                    # un autopiloto en marcha esta publicando
    before, mtime = path.read_bytes(), path.stat().st_mtime_ns
    viewer = State(path, readonly=True)                                        # `--estado` desde otra ventana
    assert viewer.slot(DAY, "foto", "11:30")["estado"] == "en_curso"           # NO lo marca como ambiguo: sigue en curso
    viewer.omit(DAY, "foto", "12:00", "x")
    viewer.save()
    assert path.read_bytes() == before and path.stat().st_mtime_ns == mtime
    assert State(tmp_path / "otro.json", legacy=None, readonly=True).data["dias"] == {} and not (tmp_path / "otro.json").exists()


def test_state_pruning_and_single_instance(tmp_path):
    st = State(tmp_path / "e.json")
    for i in range(60):
        st.finish(date(2026, 1, 1) + timedelta(days=i), "foto", "11:30", "ok", f"f{i}.png", str(i))
    assert len(State(tmp_path / "e.json").data["dias"]) == 45
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


def cli_args(env, **kw):
    base = dict(env=env, fotos=None, videos=None, max_fotos=None, max_videos=None, jitter=None, dry_run=False)
    return SimpleNamespace(**{**base, **kw})


def test_cli_rejects_a_bad_configuration(tmp_path, monkeypatch):
    p = tmp_path / ".env"
    p.write_text(f"LOG_ARCHIVO={tmp_path / 'a.log'}\n", "utf-8")
    assert autopiloto.main(["--env", str(p), "--silencioso"]) == 2
    assert "PAGE_ID" in (tmp_path / "a.log").read_text("utf-8")
    p = env_file(tmp_path, HORARIOS_FOTOS="25:00,mediodia", MAX_VIDEOS_DIA="mil")
    assert autopiloto.main(["--env", str(p), "--silencioso"]) == 2
    log = (tmp_path / "auto.log").read_text("utf-8")
    assert "HORARIOS_FOTOS" in log and "MAX_VIDEOS_DIA" in log


def test_cli_options_override_the_env_file(tmp_path, monkeypatch):
    for key in ("HORARIOS_FOTOS", "HORARIOS_VIDEOS", "MAX_FOTOS_DIA", "MAX_VIDEOS_DIA"):
        monkeypatch.delenv(key, raising=False)
    env = env_file(tmp_path, HORARIOS_FOTOS="08:00", MAX_FOTOS_DIA="1")
    assert autopiloto.build_config(cli_args(env)).photo_times == ("08:00",)
    cfg = autopiloto.build_config(cli_args(env, fotos="09:00,17:30", max_fotos=2, videos="", jitter="2-5", dry_run=True))
    assert cfg.photo_times == ("09:00", "17:30") and cfg.max_photos == 2 and cfg.video_times == () and cfg.limit("video") == 0
    assert (cfg.jitter_min, cfg.jitter_max, cfg.dry_run) == (2, 5, True)
    with pytest.raises(SystemExit):
        autopiloto.build_config(cli_args(env, jitter="rapido"))


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
    assert not (tmp_path / "e.json").exists()


def test_cli_start_reads_the_state_prints_the_summary_and_schedules_only_what_is_pending(tmp_path, monkeypatch):
    today = datetime.now().date()
    State(tmp_path / "estado.json").finish(today, "foto", "11:30", "ok", "hoy.png", "55_66")      # ya salio antes de cerrar
    p = env_file(tmp_path, HORARIOS_FOTOS="11:30", HORARIOS_VIDEOS="")
    monkeypatch.setattr(autopiloto, "LOCK_FILE", tmp_path / "x.lock")
    started = {}
    monkeypatch.setattr(core, "run_forever", lambda sch, **kw: started.update(jobs=len(sch.get_jobs()), hook=kw.get("hook")))
    assert autopiloto.main(["--env", str(p), "--dry-run", "--silencioso"]) == 0
    log = (tmp_path / "auto.log").read_text("utf-8")
    assert f"Resumen de hoy ({today.isoformat()}): fotos 1/1" in log and "hoy.png" in log and "55_66" in log
    assert "Franja foto  11:30: ejecutada" in log and "Pendiente por publicar hoy: 0" in log
    assert started["jobs"] == 0 and callable(started["hook"])               # nada que programar; y el gancho de medianoche


def test_cli_estado_shows_the_day_without_touching_anything(tmp_path, monkeypatch):
    today = datetime.now().date()
    legacy = tmp_path / "autopiloto_estado.json"
    legacy.write_text(json.dumps({"dias": {today.isoformat(): {"video": {"estado": "ok", "hora": "18:07:00",
                                                                           "archivo": "r.mp4", "id": "777"}}}}), "utf-8")
    p = env_file(tmp_path, ESTADO_ARCHIVO=str(tmp_path / "estado_autopiloto.json"), HORARIOS_FOTOS="23:59",
                 HORARIOS_VIDEOS="18:00")
    monkeypatch.setattr(autopiloto, "LOCK_FILE", tmp_path / "x.lock")
    assert autopiloto.main(["--env", str(p), "--estado", "--silencioso"]) == 0
    log = (tmp_path / "auto.log").read_text("utf-8")
    assert "videos 1/1" in log and "r.mp4" in log and "Franja video 18:00" in log
    assert not (tmp_path / "estado_autopiloto.json").exists() and not (tmp_path / "x.lock").exists()   # solo lectura, sin candado
    monkeypatch.setattr(core, "run_forever", lambda sch, **kw: None)         # el primer arranque real migra el archivo antiguo
    assert autopiloto.main(["--env", str(p), "--dry-run", "--silencioso"]) == 0
    assert State(tmp_path / "estado_autopiloto.json").count(today, "video") == 1 and legacy.exists()


def test_cli_refuses_a_second_instance(tmp_path, monkeypatch):
    monkeypatch.setattr(autopiloto, "LOCK_FILE", tmp_path / "x.lock")
    State(tmp_path / "estado.json").begin(datetime.now().date(), "foto", "11:30", "a.png")   # otro autopiloto publicando
    first = core.SingleInstance(tmp_path / "x.lock")
    assert first.acquire()
    try:
        assert autopiloto.main(["--env", str(env_file(tmp_path)), "--silencioso"]) == 3
    finally:
        first.release()
    assert State(tmp_path / "estado.json", readonly=True).slot(datetime.now().date(), "foto", "11:30")["estado"] == "en_curso"
    logging.getLogger("autopiloto").handlers.clear()                           # el segundo no toco lo que el primero tenia en curso


# --------------------------------------------------------------------------- Python y FFmpeg de los generadores
def test_generators_use_the_project_venv_python_when_it_exists(tmp_path, monkeypatch):
    import sys
    assert media.project_python(tmp_path) == sys.executable                      # sin .venv: el Python actual
    exe = tmp_path / ".venv" / "Scripts" / "python.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    assert media.project_python(tmp_path) == str(exe)                            # con .venv: ese (alli estan moderngl y edge-tts)
    monkeypatch.setattr(media, "project_python", lambda root=None: "/ruta/venv/python")
    cfg = Config(image_out=tmp_path, video_out=tmp_path)
    assert media.video_command(cfg)[0] == "/ruta/venv/python" and media.image_command(cfg)[0] == "/ruta/venv/python"
    assert media.video_command(cfg, python="otro")[0] == "otro"


def test_missing_modules_detection():
    import sys
    assert media.missing_modules(sys.executable, ["os", "modulo_que_no_existe_xyz"]) == ["modulo_que_no_existe_xyz"]
    assert media.missing_modules(sys.executable, ["os", "json"]) == []
    fake = lambda out, rc=0, err=b"": (lambda cmd, **kw: SimpleNamespace(returncode=rc, stdout=out, stderr=err))   # noqa: E731
    assert media.missing_modules("py", ["a"], fake(b"aviso" + bytes([10]) + b"MISSING:moderngl,edge_tts" + bytes([10]))) \
        == ["moderngl", "edge_tts"]
    with pytest.raises(media.GenerationError, match="no funciona"):
        media.missing_modules("py", ["a"], fake(b"", 1, b"Traceback" + bytes([10]) + b"boom"))
    with pytest.raises(media.GenerationError, match="no se pudo ejecutar"):
        media.missing_modules("py", ["a"], lambda cmd, **kw: (_ for _ in ()).throw(FileNotFoundError("no existe")))


def test_reel_task_explains_which_module_is_missing_instead_of_a_traceback(tmp_path):
    auto, http, gen = build(tmp_path)
    base = auto.runner

    def runner(cmd, **kw):
        if cmd[1] == "-c":
            return SimpleNamespace(returncode=0, stdout=b"MISSING:moderngl", stderr=b"")
        return base(cmd, **kw)

    auto.runner = runner
    out = auto.execute("video", "18:00")
    assert out.status == "error" and "moderngl" in out.detail and "pip install -r requirements.txt" in out.detail
    assert not gen and not http.calls                                              # ni se lanza el generador ni se publica
    assert auto.state.slot(DAY, "video", "18:00")["estado"] == "error"


def test_ffmpeg_is_found_in_the_winget_folder(tmp_path, monkeypatch):
    import os
    monkeypatch.setattr(media.shutil, "which", lambda name: None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("PATH", "ruta_base")
    assert media.ensure_ffmpeg_on_path() is False
    bindir = tmp_path / "Microsoft" / "WinGet" / "Packages" / "Gyan.FFmpeg_x" / "ffmpeg-8.0-full_build" / "bin"
    bindir.mkdir(parents=True)
    (bindir / "ffmpeg.exe").write_bytes(b"")
    assert media.ensure_ffmpeg_on_path() is True
    assert os.environ["PATH"].split(os.pathsep)[0] == str(bindir)
    monkeypatch.setattr(media.shutil, "which", lambda name: "/usr/bin/" + name)
    assert media.ensure_ffmpeg_on_path() is True
