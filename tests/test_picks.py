import numpy as np
import pandas as pd

from footypred.predict.picks import (CANDIDATES, FormIndex, backtest, base_rates, form_check,
                                     form_counts)


def _m(date, home, away, gh, ga, league="L"):
    return {"match_id": f"{date}_{home}_{away}", "date": pd.Timestamp(date), "home": home,
            "away": away, "fthg": gh, "ftag": ga, "league": league, "neutral": 0, "season": 2025}


def _scenario():
    """Your example: A scores and keeps clean sheets at home; B scores and
    concedes both home and away."""
    rows = []
    d = pd.Timestamp("2025-08-01")
    for i in range(5):
        rows.append(_m(d + pd.Timedelta(days=14 * i), "A", f"X{i}", 2, 0))       # A at home
        rows.append(_m(d + pd.Timedelta(days=14 * i + 7), f"Y{i}", "A", 1, 1))   # A away
        rows.append(_m(d + pd.Timedelta(days=14 * i + 1), "B", f"Z{i}", 2, 2))   # B at home
        rows.append(_m(d + pd.Timedelta(days=14 * i + 8), f"W{i}", "B", 2, 1))   # B away
    return pd.DataFrame(rows)


def _probs(**over):
    p = {"1x2": np.array([0.55, 0.25, 0.20]), "o25": 0.52, "btts": 0.45,
         "h_o05": 0.82, "h_o15": 0.55, "h_o25": 0.28, "a_o05": 0.55, "a_o15": 0.22, "a_o25": 0.07}
    p.update(over)
    return p


def test_windows_are_strictly_before_the_date_and_from_each_side():
    idx = FormIndex(_scenario())
    home5 = idx.window("A", "home", "2025-10-01", 5)
    assert len(home5) == 5 and all(r["venue"] == "H" and r["gf"] == 2 and r["ga"] == 0 for r in home5)
    away5 = idx.window("B", "away", "2025-10-01", 5)
    assert all(r["gf"] == 1 and r["ga"] == 2 for r in away5)          # B's goals first
    assert idx.window("A", "home", "2025-08-01", 5) == []               # nothing before day 1
    assert len(idx.window("A", "home", "2025-08-16", 5)) == 2           # same-day game excluded


def test_example_scenario_picks_team_a_over_0_5():
    idx = FormIndex(_scenario())
    f = form_check(idx, "A", "B", "2025-10-20", _probs())
    assert f["best_pick"]["key"] == "home_over_0.5"
    assert any("scores often (5/5)" in t for t in f["profiles"]["home"]["at home"])
    assert any("keeps clean sheets (5/5)" in t for t in f["profiles"]["home"]["at home"])
    assert any("concedes often (5/5)" in t for t in f["profiles"]["away"]["away"])
    ev = {e["window"]: (e["hits"], e["n"]) for e in f["best_pick"]["evidence"]}
    assert ev["A's last 5 home games"] == (5, 5) and ev["B's last 5 away games"] == (5, 5)
    assert f["counts"]["home_home"]["clean_sheets"] == 5
    assert "A over 0.5 goals" in f["reason"]


def test_model_gate_and_market_filter():
    idx = FormIndex(_scenario())
    # model strongly disagrees -> form alone can't make it the pick
    f = form_check(idx, "A", "B", "2025-10-20", _probs(h_o05=0.40))
    assert f["best_pick"] is None or f["best_pick"]["key"] != "home_over_0.5"
    f = form_check(idx, "A", "B", "2025-10-20", _probs(), {"markets": ["btts", "1x2"]})
    assert f["best_pick"] is None or f["best_pick"]["market"] in ("btts", "1x2")
    assert set(f["best_by_market"]) == {"1x2", "ou25", "btts", "team_totals"}


def test_lift_requires_beating_the_typical_game():
    idx = FormIndex(_scenario())
    typical = {c.key: 0.5 for c in CANDIDATES}
    typical["home_over_0.5"] = 0.80                    # 82% is ordinary in this league
    f = form_check(idx, "A", "B", "2025-10-20", _probs(), {"min_lift": 0.05}, base=typical)
    assert f["best_pick"] is None or f["best_pick"]["key"] != "home_over_0.5"
    f = form_check(idx, "A", "B", "2025-10-20", _probs(), {"min_lift": 0.0}, base=typical)
    assert f["best_pick"]["key"] == "home_over_0.5"


def test_candidate_outcomes_and_base_rates():
    outcome = {c.key: c.test_home_side(2, 1) for c in CANDIDATES}
    assert outcome["home_win"] and outcome["over_2.5"] and outcome["btts_yes"]
    assert outcome["home_over_1.5"] and not outcome["home_over_2.5"]
    assert outcome["away_over_0.5"] and outcome["away_under_1.5"] and not outcome["draw"]
    b = base_rates(_scenario(), min_league_games=1)
    assert 0 <= b["_all"]["btts_yes"] <= 1 and "L" in b
    c = form_counts([{"gf": 0, "ga": 0, "venue": "H", "opponent": "Q", "result": "D"}])
    assert c["clean_sheets"] == 1 and c["failed_to_score"] == 1


def test_backtest_runs_and_counts_hits():
    m = _scenario()
    later = pd.DataFrame([_m("2025-11-01", "A", "B", 3, 0), _m("2025-11-08", "B", "A", 1, 2)])
    allm = pd.concat([m, later], ignore_index=True)
    n = len(later)
    probs = {"1x2": np.tile([0.55, 0.25, 0.20], (n, 1)), **{k: np.full(n, v) for k, v in
             {"o25": 0.52, "btts": 0.45, "h_o05": 0.82, "h_o15": 0.55, "h_o25": 0.28,
              "a_o05": 0.55, "a_o15": 0.22, "a_o25": 0.07}.items()}}
    r = backtest(FormIndex(allm), later.reset_index(drop=True), probs, {"min_lift": 0})
    assert r["matches"] == 2 and r["picks"] >= 1 and 0 <= r["hit_rate"] <= 1
