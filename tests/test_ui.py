"""Web app API, terminal menu, packaging and edge-case regressions."""

import json
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd
import pytest

from footypred.features.engineering import FeatureBuilder, feature_columns
from footypred.models.registry import ModelRegistry
from footypred.models.trainer import Trainer

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def service(cfg, populated_db):
    from footypred.ui.service import PredictionService
    reg = ModelRegistry(cfg.paths.models_dir)
    if not reg.latest_version():
        fb = FeatureBuilder(cfg, populated_db)
        frame = fb.build_training_frame()
        res = Trainer(cfg).train(frame, feature_columns(frame))
        res.feature_params = fb.params
        reg.save(res, fb.state)
    return PredictionService(cfg, populated_db)


@pytest.fixture(scope="module")
def server(service):
    from footypred.ui.web import make_server
    httpd = make_server(service, port=0)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_web_api(server):
    code, body = _get(server + "/")
    assert code == 200 and b'id="home-league"' in body and b'id="away-team"' in body
    leagues = json.loads(_get(server + "/api/leagues")[1])
    assert leagues[0]["code"] == "E0" and leagues[0]["name"] == "Premier League"
    teams = json.loads(_get(server + "/api/teams?league=E0")[1])
    assert "Arsenal" in teams and "Chelsea" in teams
    code, body = _get(server + "/api/predict?home=Arsenal&away=Chelsea&date=2026-07-15")
    d = json.loads(body)
    assert code == 200 and d["chart_png"] and abs(sum(d["markets"]["1x2"].values()) - 1) < 1e-3
    code, body = _get(server + "/api/predict?home=Arsenal&away=Arsenal")
    assert code == 400 and b"different" in body
    code, body = _get(server + "/api/predict?home=Nowhere%20FC&away=Chelsea")
    assert code == 400 and b"Did you mean" in body
    code, body = _get(server + "/api/evaluation")
    assert code == 200 and json.loads(body)["chart_png"]


def _post(url, payload=None):
    req = urllib.request.Request(url, data=json.dumps(payload or {}).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_data_and_backtest_endpoints(server):
    import time
    comps = json.loads(_get(server + "/api/competitions")[1])
    assert [c["code"] for c in comps] == ["E0"]
    d = json.loads(_get(server + "/api/data")[1])
    assert d["exists"] is False and d["db_matches"] > 1000 and d["path"].endswith("matches.csv")
    code, body = _post(server + "/api/data/reload")
    assert code == 400 and "download it first" in body["error"]
    rng = json.loads(_get(server + "/api/date-range")[1])
    assert rng["first"] < rng["min_start"] < rng["last"]
    assert _post(server + "/api/backtest", {"to": "2026-05-01"})[0] == 400
    assert _post(server + "/api/backtest", {"from": "not a date"})[0] == 400
    code, job = _post(server + "/api/backtest", {"from": "2026-05-01", "to": "2026-05-24",
                                                 "quick": True, "no_tune": True})
    assert code == 200 and job["status"] == "running"
    code, busy = _post(server + "/api/backtest", {"from": "2026-05-01"})
    assert code == 400 and "already running" in busy["error"]
    deadline = time.time() + 300
    while job["status"] == "running" and time.time() < deadline:
        time.sleep(1)
        job = json.loads(_get(server + "/api/job?id=" + job["id"])[1])
    assert job["status"] == "done", job
    r = job["result"]
    assert r["matches"] > 20 and r["chart_png"] and r["table"] and r["start"] == "2026-05-01"
    assert set(r["picks"]) == {"safe", "balanced", "bold"}
    code, csv = _get(server + "/api/backtest.csv?id=" + job["id"])
    assert code == 200 and csv.count(b"\n") == r["matches"] + 1 and b"pick_balanced" in csv


def test_follow_ups_and_batch_picks(server):
    code, body = _get(server + "/api/predict?home=Arsenal&away=Chelsea&date=2026-07-15&chart=0")
    f = json.loads(body)["form"]
    assert code == 200 and set(f["by_style"]) == {"safe", "balanced", "bold"}
    assert isinstance(f["follow_ups"], list) and len(f["follow_ups"]) <= 4
    best = f["best_pick"]["key"] if f["best_pick"] else None
    assert all(c["key"] != best for c in f["follow_ups"])
    assert all("why" in c for c in f["follow_ups"] if c.get("lean"))
    code, rows = _post(server + "/api/predict-batch", {"fixtures": [
        {"id": 1, "home": "Arsenal", "away": "Chelsea", "date": "2026-07-15", "competition": "E0"},
        {"id": 2, "home": "Nowhere FC", "away": "Chelsea"}], "pick_opts": {"style": "bold"}})
    assert code == 200 and [r["ok"] for r in rows] == [True, False]
    assert rows[0]["style"] == "bold" and set(rows[0]["by_style"]) == {"safe", "balanced", "bold"}
    assert "1x2" in rows[0] and "Did you mean" in rows[1]["error"]
    code, sch = _get(server + "/api/schedule")
    sch = json.loads(sch)
    assert code == 200 and sch["back"] == 3 and sch["ahead"] == 5 and sch["ready"] is True


def test_merge_endpoint(server, cfg, tmp_path):
    from footypred.data.localfile import csv_path
    assert _post(server + "/api/data/merge", {"paths": ""})[0] == 400
    code, body = _post(server + "/api/data/merge", {"paths": str(tmp_path / "missing.csv")})
    assert code == 400 and "not found" in body["error"]
    f = tmp_path / "T1.csv"
    f.write_text("Div,Date,HomeTeam,AwayTeam,FTHG,FTAG\nT1,08/08/2025,Galatasaray,Goztep,3,0\n")
    code, r = _post(server + "/api/data/merge", {"paths": f'"{f}"', "dry_run": True})
    assert code == 200 and r["added"] == 1 and r["dry_run"] and "Would add 1" in r["text"]
    assert not csv_path(cfg).exists()              # a preview never writes


def test_image_upload_and_batch_endpoints(server):
    import importlib.util
    if importlib.util.find_spec("rapidocr_onnxruntime") is None:
        pytest.skip("rapidocr_onnxruntime not installed")
    img = (ROOT / "tests" / "data" / "coupon_mobile.png").read_bytes()
    req = urllib.request.Request(server + "/api/image?engine=ocr", data=img, method="POST",
                                 headers={"Content-Type": "image/png"})
    with urllib.request.urlopen(req, timeout=120) as r:
        res = json.loads(r.read())
    pairs = [(f["home"], f["away"]) for f in res["fixtures"]]
    assert ("Arsenal", "Chelsea") in pairs        # E0-only test database
    idx = json.loads(_get(server + "/api/team-index")[1])
    assert idx["Arsenal"] == "E0"
    code, body = _get(server + "/api/predict?home=Arsenal&away=Chelsea&chart=0&markets=team_totals"
                               "&min_odds=1.2&min_lift=0")
    d = json.loads(body)
    assert code == 200 and d["chart_png"] is None
    assert d["form"]["settings"]["markets"] == ["team_totals"]
    assert d["form"]["best_pick"] is None or d["form"]["best_pick"]["market"] == "team_totals"
    req = urllib.request.Request(server + "/api/image", data=b"not an image", method="POST")
    try:
        urllib.request.urlopen(req, timeout=60)
        raise AssertionError("expected an error")
    except urllib.error.HTTPError as e:
        assert e.code == 400


def test_terminal_menu(service):
    from footypred.ui.menu import Menu
    answers = iter(["1",            # league: Premier League
                    "arsnal",       # home team by fuzzy name
                    "",             # away league = same
                    "Chelsea",      # away team by name
                    "2026-07-15", "n",   # date, neutral
                    "n",            # don't save chart
                    "n"])           # no more fixtures
    out = []
    Menu(service, input_fn=lambda _: next(answers), print_fn=out.append).run()
    text = "\n".join(map(str, out))
    assert "Arsenal vs Chelsea" in text and "BOTH TEAMS TO SCORE" in text


def test_past_date_has_no_negative_rest(service):
    pred, _ = service.predict("Arsenal", "Chelsea", "2023-01-07", chart=False)
    st = service.predictor.state
    f = st.features("Arsenal", "Chelsea", pd.Timestamp("2023-01-07"), "E0")
    assert f["h_rest"] >= 0 and f["a_rest"] >= 0
    assert any("not a fair backtest" in w for w in pred.warnings)


def test_every_source_file_is_tracked_by_git():
    """Regression: a `data/` ignore rule once dropped footypred/data and
    footypred/models from the release archive."""
    try:
        tracked = set(subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                                     text=True, check=True).stdout.split())
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    files = [p.relative_to(ROOT).as_posix() for p in (ROOT / "footypred").rglob("*")
             if p.suffix in (".py", ".html") and "__pycache__" not in p.parts]
    missing = [f for f in files if f not in tracked]
    assert not missing, f"untracked package files (check .gitignore): {missing}"
