"""Everything from the browser: the app starts without data or a model
(setup mode), and settings, download, training, demo data and team-name
merges all work through the web API."""

import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from fd_mock import MockFDOrg, match
from footypred.config import load_config, load_local_settings
from footypred.data import localfile as lf
from footypred.data.db import Database
from footypred.data.synthetic import generate

KEY = "0123456789abcdef0123456789abcdef"


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _post(url, payload=None):
    req = urllib.request.Request(url, data=json.dumps(payload or {}).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _wait(base, job, limit=300):
    deadline = time.time() + limit
    while job["status"] == "running" and time.time() < deadline:
        time.sleep(0.5)
        job = _get(base + "/api/job?id=" + job["id"])[1]
    return job


def _serve(cfg, db=None):
    from footypred.ui.service import PredictionService
    from footypred.ui.web import make_server
    service = PredictionService(cfg, db)
    httpd = make_server(service, port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return service, httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


@pytest.fixture()
def api():
    ms = {"PL": [match(i, "PL", f"2024-{8 + i // 10:02d}-{1 + i % 10 * 2:02d}T15:00:00Z",
                       h, a, (i % 3, (i + 1) % 2), (0, 0))
                 for i, (h, a) in enumerate([("Arsenal", "Chelsea"), ("Liverpool", "Manchester City"),
                                             ("Chelsea", "Liverpool"), ("Manchester City", "Arsenal")] * 5)]}
    m = MockFDOrg(ms, key=KEY)
    yield m
    m.close()


def test_setup_mode_settings_download_names(tmp_path, api):
    cfg = load_config(root=tmp_path, overrides={
        "football_data_org": {"base_url": api.url, "min_interval_seconds": 0,
                              "fallback_football_data_co_uk": False, "first_season": 2024,
                              "competitions": {"E0": {"code": "PL", "name": "Premier League"}}}})
    cfg.paths.ensure()
    service, httpd, base = _serve(cfg)
    try:
        st = _get(base + "/api/status")[1]
        assert st["ready"] is False and st["has_data"] is False
        code, body = _get(base + "/api/predict?home=Arsenal&away=Chelsea")
        assert code == 409 and body["setup"] and "Data tab" in body["error"]
        assert _get(base + "/api/evaluation")[0] == 409
        assert _get(base + "/api/competitions") == (200, [])
        assert _get(base + "/api/data")[1]["model"] is None
        # downloading needs a key; a malformed one is refused, a good one is saved privately
        assert _post(base + "/api/settings", {"api_key": "nope"})[0] == 400
        code, s = _post(base + "/api/settings", {"api_key": KEY})
        assert code == 200 and s["api_key_set"] and s["api_key_hint"] == "…cdef"
        assert KEY not in json.dumps(_get(base + "/api/settings")[1])   # never sent back
        assert load_local_settings(tmp_path)["football_data_org"]["api_key"] == KEY
        assert load_config(root=tmp_path).raw["football_data_org"]["api_key"] == KEY
        # download the match file in the background
        code, job = _post(base + "/api/data/download", {})
        assert code == 200
        job = _wait(base, job)
        assert job["status"] == "done", job
        assert lf.csv_path(cfg).exists() and job["result"]["rows"] == 20
        st = _get(base + "/api/status")[1]
        assert st["has_data"] and not st["ready"]                       # train next
        code, again = _post(base + "/api/data/download", {})
        assert code == 400 and "Update" in again["error"]               # no silent overwrite
        # a second spelling of a club, merged from the Team names card
        rows = lf.read_csv(lf.csv_path(cfg))
        extra = rows.iloc[:3].copy()
        extra["match_id"] = ["x1", "x2", "x3"]
        extra["date"] = ["2024-12-01", "2024-12-08", "2024-12-15"]
        extra["home"] = "Arsenal London"
        lf.append_csv(extra, lf.csv_path(cfg))
        lf.sync_db(cfg, service.db)
        pairs = _get(base + "/api/data/names")[1]
        assert any({p["a"], p["b"]} == {"Arsenal", "Arsenal London"} for p in pairs)
        assert _post(base + "/api/data/alias", {"from": "Arsenal", "to": "Arsenal"})[0] == 400
        code, r = _post(base + "/api/data/alias", {"from": "Arsenal London", "to": "Arsenal"})
        assert code == 200 and "Arsenal London" not in service.db.teams()
        assert not any("Arsenal London" in (p["a"], p["b"]) for p in r["pairs"])
        # the demo data is refused once you have your own file
        assert _post(base + "/api/data/demo")[0] == 400
        # removing the saved key
        assert _post(base + "/api/settings", {"api_key": ""})[1]["api_key_set"] is False
    finally:
        httpd.shutdown()


def test_train_from_the_browser(tmp_path):
    cfg = load_config(root=tmp_path, overrides={
        "seasons": [2022, 2023, 2024],
        "training": {"models": ["poisson", "dixon_coles", "lightgbm"], "dc_half_life_grid": [240]}})
    cfg.paths.ensure()
    db = Database(cfg.paths.db_file)
    db.upsert_matches(generate([2022, 2023, 2024], cutoff="2025-06-30", seed=4, leagues=["E0"],
                               internationals=False), "synthetic")
    db.set_meta("data_source", "synthetic")
    service, httpd, base = _serve(cfg, db)
    try:
        assert _get(base + "/api/status")[1]["ready"] is False
        code, job = _post(base + "/api/train", {"quick": True})
        assert code == 200 and job["kind"] == "training"
        assert _get(base + "/api/job/current")[1]["job"]["id"] == job["id"]   # resumable
        assert _post(base + "/api/train", {})[0] == 400                       # one at a time
        job = _wait(base, job, 400)
        assert job["status"] == "done", job
        assert any("training on" in line for line in job["log"])           # live log lines
        assert job["result"]["status"]["ready"] is True
        assert _get(base + "/api/job/current")[1]["job"] is None
        code, d = _get(base + "/api/predict?home=Arsenal&away=Chelsea&chart=0")
        assert code == 200 and abs(sum(d["markets"]["1x2"].values()) - 1) < 1e-3
        info = _get(base + "/api/data")[1]
        assert info["model"] and info["model_matches"] == db.count_matches() and not info["retrain"]
    finally:
        httpd.shutdown()


def test_demo_data_from_the_browser(tmp_path):
    cfg = load_config(root=tmp_path, overrides={"seasons": [2025]})
    cfg.paths.ensure()
    service, httpd, base = _serve(cfg)
    try:
        code, job = _post(base + "/api/data/demo")
        assert code == 200
        job = _wait(base, job, 120)
        assert job["status"] == "done" and job["result"]["matches"] > 500
        st = _get(base + "/api/status")[1]
        assert st["has_data"] and st["data_source"] == "synthetic" and not st["ready"]
        assert _get(base + "/api/leagues")[1]                              # pickers filled
    finally:
        httpd.shutdown()


def test_local_settings_override_and_main_module(tmp_path, capsys):
    from footypred.config import save_local_settings
    save_local_settings({"local_data": {"csv": "elsewhere/my.csv"},
                         "football_data_org": {"first_season": 2023}}, tmp_path)
    cfg = load_config(root=tmp_path)
    assert lf.csv_path(cfg) == tmp_path / "elsewhere" / "my.csv"
    assert lf.first_season(cfg) == 2023
    assert cfg.raw["football_data_org"]["base_url"].startswith("https://")   # rest untouched
    save_local_settings({"football_data_org": {"first_season": None}}, tmp_path)
    assert "football_data_org" not in load_local_settings(tmp_path)
    import runpy
    import sys
    argv = sys.argv
    try:
        sys.argv = ["footypred", "--help"]
        with pytest.raises(SystemExit) as e:
            runpy.run_module("footypred", run_name="__main__")
        assert e.value.code == 0 and "backtest" in capsys.readouterr().out
    finally:
        sys.argv = argv
