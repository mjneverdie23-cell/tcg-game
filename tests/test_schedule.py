"""Schedule page data: fixtures from football-data.org (played, live and
upcoming), football-data.co.uk fixture lists for leagues the API doesn't
cover, results from the match file; and follow-up picks."""

import pandas as pd
import pytest

from fd_mock import FakeCoUk, MockFDOrg, match
from footypred.config import load_config
from footypred.data import localfile as lf
from footypred.data import schedule as sch
from footypred.data.sources.football_data_org import FDOrgClient

TODAY = "2026-10-21"


@pytest.fixture()
def setup(tmp_path):
    ms = {"PL": [match(1, "PL", "2026-10-18T14:00:00Z", "Arsenal", "Chelsea", (2, 1), (1, 0)),
                 match(2, "PL", "2026-10-21T19:00:00Z", "Liverpool", "Manchester City", (1, 0), (1, 0),
                       status="IN_PLAY"),
                 match(3, "PL", "2026-10-24T11:30:00Z", "Chelsea", "Liverpool", None, None, status="TIMED"),
                 match(4, "PL", "2026-11-20T15:00:00Z", "Arsenal", "Liverpool", None, None, status="TIMED")],
          "CL": [match(9, "CL", "2026-10-22T19:00:00Z", "Bayern Munich", "Arsenal", None, None,
                       status="TIMED", stage="LEAGUE_STAGE")]}
    api = MockFDOrg(ms, key="0123456789abcdef0123456789abcdef")
    cfg = load_config(root=tmp_path, overrides={"football_data_org": {"base_url": api.url}})
    cfg.paths.ensure()
    # your match file already has a Süper Lig result (UK time) and the Arsenal game
    lf.write_csv(pd.DataFrame({
        "match_id": ["cuk-1", "fd-1"], "source": ["football-data.co.uk", "football-data.org"],
        "competition": ["T1", "E0"], "season": 2026, "date": ["2026-10-19", "2026-10-18"],
        "kickoff": ["17:00", "14:00"], "kickoff_tz": ["Europe/London", "UTC"],
        "home": ["Trabzonspor", "Arsenal"], "away": ["Besiktas", "Chelsea"],
        "fthg": [2, 2], "ftag": [0, 1]}), lf.csv_path(cfg))
    fixtures = ("Div,Date,Time,HomeTeam,AwayTeam,B365H,B365D,B365A,AvgH,AvgD,AvgA\n"
                "T1,24/10/2026,17:00,Buyuksehyr,Galatasaray,3.9,3.6,1.9,3.8,3.5,1.95\n"
                "E0,24/10/2026,12:30,Chelsea,Liverpool,2.5,3.4,2.8,2.5,3.4,2.8\n")
    http = FakeCoUk({"fixtures.csv": fixtures.encode()})
    client = FDOrgClient("0123456789abcdef0123456789abcdef", base_url=api.url, min_interval=0,
                         sleep=lambda s: None)
    yield cfg, client, http, api
    api.close()


def test_refresh_and_window(setup):
    cfg, client, http, api = setup
    r = sch.refresh(cfg, client, http, today=TODAY)
    assert api.window_calls == 2                        # 11 days -> two calls of <= 10 days
    assert r["matches"] == 5 and sch.fixtures_path(cfg).exists()
    w = sch.window(cfg, today=TODAY)
    by = {(m["competition"], m["home"], m["away"]): m for m in w["matches"]}
    assert ("E0", "Arsenal", "Liverpool") not in by        # outside the window
    live = by[("E0", "Liverpool", "Manchester City")]
    assert live["live"] and (live["fthg"], live["ftag"]) == (1, 0) and live["utc"] == "2026-10-21T19:00:00Z"
    assert by[("E0", "Arsenal", "Chelsea")]["status"] == "FINISHED"
    assert by[("CL", "Bayern Munich", "Arsenal")]["home_crest"].startswith("https://")
    # the co.uk list adds Süper Lig only (the Premier League came from the API), UK time -> UTC
    t1 = by[("T1", "Basaksehir", "Galatasaray")]
    assert t1["source"] == "football-data.co.uk" and t1["utc"] == "2026-10-24T16:00:00Z"
    assert t1["odds_h"] == 3.8                             # market average before Bet365
    assert len([m for m in w["matches"] if (m["home"], m["away"]) == ("Chelsea", "Liverpool")]) == 1
    # a result in your match file shows on its day (Süper Lig isn't in the API)
    res = by[("T1", "Trabzonspor", "Besiktas")]
    assert res["status"] == "FINISHED" and res["fthg"] == 2 and res["utc"] == "2026-10-19T16:00:00Z"
    assert w["back"] == 3 and w["ahead"] == 5 and w["fetched_at"]


def test_window_without_api_key_uses_couk_and_results(setup):
    cfg, _, http, _ = setup
    sch.refresh(cfg, None, http, today=TODAY)
    w = sch.window(cfg, today=TODAY)
    comps = {m["competition"] for m in w["matches"]}
    assert comps == {"E0", "T1"}                            # co.uk list + your results


def test_follow_up_picks_are_diverse():
    from footypred.predict.picks import follow_up_picks
    mk = lambda key, market, score: {"key": key, "market": market, "label": key, "model_prob": 0.7,
                                     "form_rate": 0.8, "fair_odds": 1.4, "score": score,
                                     "agreement": "", "eligible": True, "evidence": []}
    ranked = [mk("home_over_0.5", "team_totals", 0.9), mk("home_over_1.5", "team_totals", 0.85),
              mk("over_1.5", "totals", 0.8), mk("btts_yes", "btts", 0.7),
              mk("away_over_0.5", "team_totals", 0.65), mk("home_win", "1x2", 0.6)]
    fu = follow_up_picks(ranked, ranked[0], n=4)
    keys = [c["key"] for c in fu]
    assert "home_over_0.5" not in keys and len(keys) == 4
    assert "home_over_1.5" not in keys                      # same family as the best pick: later
    assert set(keys) == {"over_1.5", "btts_yes", "away_over_0.5", "home_win"}
    assert not any(c.get("lean") for c in fu)
    # nothing passes the style: leans fill in, each with the rule it missed
    soft = [{**c, "eligible": False, "fails": ["too short"]} for c in ranked]
    soft[3]["fails"] = ["market off"]                       # unticked market: never offered
    leans = follow_up_picks(soft, None, n=3)
    assert len(leans) == 3 and all(c["lean"] and "odds below" in c["why"] for c in leans)
    assert "btts_yes" not in [c["key"] for c in leans]


def test_schedule_from_the_browser(setup):
    """Service + web: refresh fetches the window; rows say whether both
    teams are known (so the page knows what it can predict)."""
    import json
    import threading
    import urllib.request
    from footypred.data.db import Database
    from footypred.ui.service import PredictionService
    from footypred.ui.web import make_server
    cfg, _, _, api = setup
    cfg.raw["football_data_org"].update({"api_key": "0123456789abcdef0123456789abcdef",
                                          "min_interval_seconds": 0,
                                          "fallback_football_data_co_uk": False})
    db = Database(cfg.paths.db_file)
    lf.sync_db(cfg, db)
    svc = PredictionService(cfg, db)
    httpd = make_server(svc, port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        req = urllib.request.Request(base + "/api/schedule/refresh", data=b"{}", method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            w = json.loads(r.read())
        assert w["has_key"] and w["fetched_at"] and not w["ready"]
        names = {(m["home"], m["away"]): m for m in w["matches"]}
        assert names[("Arsenal", "Chelsea")]["known"] is True          # in the match file
        assert names[("Bayern Munich", "Arsenal")]["home_known"] is False
        assert not any(m["predictable"] for m in w["matches"])         # no model yet
    finally:
        httpd.shutdown()
