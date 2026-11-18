"""League tables for the Schedule tab: points, tie-breaks, deductions,
results the file doesn't have yet, league phases and cup matches."""

import pandas as pd

from footypred.config import load_config
from footypred.data.db import Database
from footypred.data.standings import season_of, standings, table


def _r(rows):
    return pd.DataFrame(rows, columns=["date", "league", "home", "away", "fthg", "ftag"])


def test_points_goal_difference_and_head_to_head():
    rows = [("2026-09-01", "E0", "A", "B", 1, 0), ("2026-09-08", "E0", "C", "A", 5, 0),
            ("2026-09-15", "E0", "B", "C", 1, 0), ("2026-09-22", "E0", "B", "D", 3, 0),
            ("2026-09-29", "E0", "A", "D", 1, 0), ("2026-10-06", "E0", "C", "D", 0, 0)]
    res = _r(rows)
    gd = table(res, "gd")
    # B and A both have 6 points; B's goal difference is better
    assert [t["team"] for t in gd] == ["B", "A", "C", "D"] and gd[0]["pts"] == 6
    assert gd[0]["p"] == 3 and gd[0]["w"] == 2 and gd[0]["l"] == 1 and gd[0]["gd"] == 3
    # head-to-head first: A beat B, so A goes above
    h2h = table(res, "h2h")
    assert [t["team"] for t in h2h][:2] == ["A", "B"]
    ded = table(res, "gd", {"B": 2})                    # B drops to 4, below C on goal difference
    assert [t["team"] for t in ded] == ["A", "C", "B", "D"]
    assert ded[2]["pts"] == 4 and ded[2]["deducted"] == 2


def test_seasons():
    assert season_of("2026-11-18") == 2026 and season_of("2027-03-01") == 2026
    assert season_of("2027-03-01", calendar_year=True) == 2027


def test_standings_from_the_file_and_the_schedule(tmp_path):
    cfg = load_config(root=tmp_path)
    cfg.paths.ensure()
    db = Database(cfg.paths.db_file)
    m = pd.DataFrame([
        {"match_id": "1", "date": "2026-09-01", "season": 2026, "league": "E0", "home": "Arsenal",
         "away": "Chelsea", "fthg": 2, "ftag": 0},
        {"match_id": "2", "date": "2026-09-08", "season": 2026, "league": "E0", "home": "Liverpool",
         "away": "Arsenal", "fthg": 1, "ftag": 1},
        {"match_id": "3", "date": "2025-09-01", "season": 2025, "league": "E0", "home": "Chelsea",
         "away": "Liverpool", "fthg": 9, "ftag": 0},                        # last season: not counted
        {"match_id": "4", "date": "2026-10-01", "season": 2026, "league": "CL", "home": "Arsenal",
         "away": "Bayern Munich", "fthg": 3, "ftag": 1},
        {"match_id": "5", "date": "2026-09-05", "season": 2026, "league": "D1", "home": "Bayern Munich",
         "away": "Dortmund", "fthg": 2, "ftag": 2},
        {"match_id": "6", "date": "2027-02-20", "season": 2026, "league": "CL", "home": "Bayern Munich",
         "away": "Arsenal", "fthg": 4, "ftag": 0}])                        # knockout: not in the table
    m["date"] = pd.to_datetime(m["date"])
    db.upsert_matches(m, "test")
    extra = [{"competition": "E0", "home": "Chelsea", "away": "Liverpool", "fthg": 0, "ftag": 1,
              "date": "2026-11-15", "status": "FINISHED"},
             {"competition": "E0", "home": "Arsenal", "away": "Chelsea", "fthg": 2, "ftag": 0,
              "date": "2026-09-01", "status": "FINISHED"}]                   # already in the file
    st = standings(cfg, db, "E0", "Arsenal", "Chelsea", "2026-11-20", extra)
    t = st["tables"][0]
    assert t["season"] == "2026-27" and t["matches"] == 3 and t["as_of"] == "2026-11-15"
    # Arsenal and Liverpool have 4 points; Arsenal's goal difference is better (+2 v +1)
    assert [r["team"] for r in t["rows"]] == ["Arsenal", "Liverpool", "Chelsea"]
    assert t["home"] == {"team": "Arsenal", "pos": 1, "pts": 4, "p": 2}
    assert t["away"]["pos"] == 3 and t["away"]["pts"] == 0
    cl = standings(cfg, db, "CL", "Arsenal", "Bayern Munich", "2027-02-20")["tables"]
    assert len(cl) == 1 and "league phase" in cl[0]["name"] and cl[0]["matches"] == 1
    assert cl[0]["home"]["pts"] == 3
    # a cup without a league phase: each team's domestic table
    cfg.raw["standings"] = {"league_phase": {}}
    cup = standings(cfg, db, "CL", "Arsenal", "Bayern Munich", "2026-10-01")
    assert [t["code"] for t in cup["tables"]] == ["E0", "D1"] and "Cup match" in cup["note"]
