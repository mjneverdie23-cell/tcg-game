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
