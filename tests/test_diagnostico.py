"""Pruebas de la herramienta de diagnostico de Reels (solo lectura) con la Graph API simulada: sin red y sin publicar nada."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import comparar_reels
from paradoja.autopilot import diagnostico as dg
from paradoja.autopilot.graph import GraphClient, GraphError

TOKEN = "EAAB" + "x1y2z3" * 12
PAGE = "1234567890123"
NOW = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)


class Resp:
    def __init__(self, body, status=200):
        self.status_code, self._body, self.text = status, body, ""

    def json(self):
        return self._body


class FakeHttp:
    """`handler(url, params) -> dict`. Anota cada peticion para comprobar que solo hay GET."""

    def __init__(self, handler):
        self.handler, self.calls = handler, []

    def request(self, method, url, **kw):
        self.calls.append((method, url, kw.get("params") or {}))
        out = self.handler(url, kw.get("params") or {})
        return out if isinstance(out, Resp) else Resp(out)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S+0000")


def make_reels(spec):
    """spec: [(id, horas_de_edad, vistas)] -> handler de la API (la lista de Reels trae las vistas y los comentarios)."""
    items = [{"id": i, "created_time": iso(NOW - timedelta(hours=h)), "length": 63.0, "views": v,
              "comments": {"data": [], "summary": {"total_count": 0}, "paging": {"cursors": f"access_token={TOKEN}"}}}
             for i, h, v in spec]

    def handler(url, params):
        assert url.endswith("/video_reels") and "ids" not in params               # `ids` esta obsoleto desde la v26.0
        return {"data": items[:int(params.get("limit", 40))], "paging": {"next": f"https://graph.facebook.com/x?access_token={TOKEN}"}}
    return handler


def client(handler):
    http = FakeHttp(handler)
    return GraphClient(PAGE, TOKEN, "v26.0", http=http, sleep=lambda s: None), http


# --------------------------------------------------------------------------- lectura
def test_get_is_read_only_and_strips_every_paging_url():
    c, http = client(lambda url, params: {"data": [{"id": "1", "comments": {"paging": {"next": f"access_token={TOKEN}"}}}],
                                          "paging": {"next": f"https://x/?access_token={TOKEN}"}})
    out = c.get(f"{PAGE}/video_reels", fields="id")
    assert "paging" not in json.dumps(out) and TOKEN not in json.dumps(out)
    assert [m for m, _u, _p in http.calls] == ["GET"]


def test_collect_reads_reels_and_views_in_one_call_and_marks_the_origin(tmp_path):
    spec = [(f"{1000 + i}", 30 + i, 250 + i) for i in range(30)] + [("2001", 3, 1), ("2002", 20, 2)]
    c, http = client(make_reels(spec))
    state = tmp_path / "estado.json"
    state.write_text(json.dumps({"dias": {"2026-11-24": {"publicaciones": [
        {"tipo": "video", "id": "2001", "archivo": "a.mp4"}, {"tipo": "foto", "id": "9", "archivo": "f.png"},
        {"tipo": "video", "id": "2002", "archivo": "b.mp4"}]}}}), "utf-8")
    reels = dg.collect(c, dg.origins_from_state(state), manual=["1000"], limit=40)
    assert len(reels) == 32 and {r.id: r.origin for r in reels if r.origin != "otro"} == {"2001": "autopiloto", "2002": "autopiloto", "1000": "manual"}
    assert next(r for r in reels if r.id == "2001").views == 1 and next(r for r in reels if r.id == "2001").archivo == "a.mp4"
    assert len(http.calls) == 1 and http.calls[0][2]["limit"] == 40                            # una sola lectura
    assert {m for m, _u, _p in http.calls} == {"GET"}                                          # nunca publica ni modifica
    assert len(dg.collect(client(make_reels(spec))[0], {}, limit=5)) == 5
    assert [r.created for r in reels] == sorted((r.created for r in reels), reverse=True)


def test_origins_are_read_without_touching_the_state_file(tmp_path):
    p = tmp_path / "estado.json"
    p.write_text(json.dumps({"dias": {"d": {"publicaciones": [{"tipo": "video", "id": 77, "archivo": "x.mp4"}]}}}), "utf-8")
    before, mtime = p.read_bytes(), p.stat().st_mtime_ns
    assert dg.origins_from_state(p) == {"77": "x.mp4"}
    assert p.read_bytes() == before and p.stat().st_mtime_ns == mtime and not list(tmp_path.glob("*.bak"))
    assert dg.origins_from_state(tmp_path / "no_existe.json") == {}
    p.write_text("basura", "utf-8")
    assert dg.origins_from_state(p) == {}


# --------------------------------------------------------------------------- estadisticas y veredicto
def build_reels(auto, rest, ages=None):
    ages = ages or {}
    out = [dg.Reel(f"a{i}", NOW - timedelta(hours=ages.get(f"a{i}", 20)), 63, v, 0, "autopiloto") for i, v in enumerate(auto)]
    out += [dg.Reel(f"m{i}", NOW - timedelta(hours=ages.get(f"m{i}", 30)), 63, v, 0, "otro") for i, v in enumerate(rest)]
    return out


def test_summary_only_compares_reels_old_enough_and_keeps_the_new_ones_apart():
    reels = build_reels([1, 2, 5], [250, 300, 270, 260], ages={"a2": 1, "m3": 2})            # un Reel de cada grupo es reciente
    s = dg.summarize(reels, NOW, min_age_hours=6)
    assert s["autopiloto"] == {"n": 2, "recientes": 1, "total": 3, "mediana": 1.5, "media": 1.5, "min": 1, "max": 2}
    assert s["resto"]["n"] == 3 and s["resto"]["recientes"] == 1 and s["resto"]["mediana"] == 270 and s["resto"]["max"] == 300


def test_the_verdict_quantifies_the_gap_without_claiming_a_cause():
    big = dg.verdict(dg.summarize(build_reels([1, 2, 1], [250, 300, 270, 260]), NOW))
    text = " ".join(big)
    assert "1 frente a 265" in text.replace("1.5", "1") or "frente a" in text
    assert "Modo" in text and "incógnito" in text and "no parece el motivo" in text          # diferencia muy grande: lista de comprobaciones
    mid = " ".join(dg.verdict(dg.summarize(build_reels([100, 120], [250, 300, 270]), NOW)))
    assert "apreciable" in mid and "incógnito" not in mid
    same = " ".join(dg.verdict(dg.summarize(build_reels([250, 280], [250, 300, 270]), NOW)))
    assert "Sin diferencia relevante" in same
    few = " ".join(dg.verdict(dg.summarize(build_reels([1], [250, 300]), NOW)))
    assert "pocos Reels" in few and "hay 1 y 2" in few


# --------------------------------------------------------------------------- fotos de vistas
def test_snapshots_give_the_views_at_one_and_twenty_four_hours(tmp_path):
    f = tmp_path / "diag.json"
    reel = dg.Reel("r1", NOW - timedelta(hours=30), 63, 40, 0, "autopiloto")
    other = dg.Reel("r2", NOW - timedelta(hours=2), 63, 7, 0, "otro")
    assert dg.load_snapshots(f) == []
    for hours_after_creation, views in ((0.9, 5), (5, 12), (24.5, 33)):
        at = reel.created + timedelta(hours=hours_after_creation)
        dg.save_snapshot([dg.Reel("r1", reel.created, 63, views, 0, "autopiloto")], at, f)
    snaps = dg.load_snapshots(f)
    assert len(snaps) == 3
    assert dg.views_at(snaps, reel, 1, 0.4) == 5 and dg.views_at(snaps, reel, 24, 3) == 33
    assert dg.views_at(snaps, reel, 12, 1) is None and dg.views_at(snaps, other, 1, 0.4) is None      # sin foto cerca: no se inventa
    assert TOKEN not in f.read_text("utf-8") and not list(tmp_path.glob("*.tmp"))
    for _ in range(dg.KEEP_SNAPSHOTS + 20):
        dg.save_snapshot([reel], NOW, f)
    assert len(dg.load_snapshots(f)) == dg.KEEP_SNAPSHOTS


def test_report_shows_the_table_the_summary_and_the_checklist(tmp_path):
    f = tmp_path / "diag.json"
    reels = build_reels([1, 2, 1], [250, 300, 270, 260])
    dg.save_snapshot([dg.Reel("a0", reels[0].created + timedelta(hours=1), 63, 1, 0, "autopiloto")], reels[0].created + timedelta(hours=1), f)
    lines = dg.render(reels, NOW, dg.load_snapshots(f), detail=3)
    text = "\n".join(lines)
    assert "autopiloto" in text and "Resumen" in text and "(… y 4 más antiguos" in text and "a +1 h" in text and "Modo" in text
    assert dg.limpiar(f"fallo access_token={TOKEN} y {TOKEN}", TOKEN).count(TOKEN) == 0
    assert "access_token=***" in dg.limpiar(f"x?access_token={TOKEN}", TOKEN)


# --------------------------------------------------------------------------- comando
def env_file(tmp_path, **extra):
    lines = {"PAGE_ID": PAGE, "PAGE_ACCESS_TOKEN": TOKEN, "ESTADO_ARCHIVO": str(tmp_path / "estado.json"), **extra}
    p = tmp_path / ".env"
    p.write_text("\n".join(f"{k}={v}" for k, v in lines.items()), "utf-8")
    return p


def test_cli_prints_the_report_and_saves_a_snapshot_without_leaking_the_token(tmp_path, monkeypatch, capsys):
    spec = [("2001", 30, 1), ("2002", 40, 2), ("1001", 50, 250), ("1002", 60, 300), ("1003", 70, 270)]
    http = FakeHttp(make_reels(spec))
    monkeypatch.setattr(comparar_reels, "GraphClient", lambda *a, **k: GraphClient(*a, http=http, sleep=lambda s: None, **{
        kk: vv for kk, vv in k.items() if kk != "http"}))
    monkeypatch.setattr(dg, "SNAPSHOT_FILE", tmp_path / "diag.json")
    (tmp_path / "estado.json").write_text(json.dumps({"dias": {"d": {"publicaciones": [
        {"tipo": "video", "id": "2001", "archivo": "a.mp4"}, {"tipo": "video", "id": "2002", "archivo": "b.mp4"}]}}}), "utf-8")
    assert comparar_reels.main(["--env", str(env_file(tmp_path))]) == 0
    out = capsys.readouterr().out
    assert "Resumen" in out and "autopiloto" in out and "Foto de vistas guardada (1 en total)" in out and TOKEN not in out
    assert "access_token" not in out and (tmp_path / "diag.json").exists()
    assert {m for m, _u, _p in http.calls} == {"GET"}                                      # solo lectura
    assert comparar_reels.main(["--env", str(env_file(tmp_path)), "--no-guardar", "--detalle", "2"]) == 0
    assert len(dg.load_snapshots()) == 1                                                   # --no-guardar no escribe


def test_cli_fails_cleanly_without_credentials_or_when_meta_rejects_the_call(tmp_path, monkeypatch, capsys):
    p = tmp_path / ".env"
    p.write_text("ESTADO_ARCHIVO=" + str(tmp_path / "e.json"), "utf-8")
    assert comparar_reels.main(["--env", str(p)]) == 2
    assert "PAGE_ID" in capsys.readouterr().out

    def rejects(url, params):
        return Resp({"error": {"code": 190, "message": f"Error validating access token {TOKEN}"}}, 400)

    http = FakeHttp(rejects)
    monkeypatch.setattr(comparar_reels, "GraphClient", lambda *a, **k: GraphClient(*a, http=http, sleep=lambda s: None))
    monkeypatch.setattr(dg, "SNAPSHOT_FILE", tmp_path / "diag.json")
    assert comparar_reels.main(["--env", str(env_file(tmp_path))]) == 1
    out = capsys.readouterr().out
    assert "No se pudieron leer" in out and TOKEN not in out and not (tmp_path / "diag.json").exists()
