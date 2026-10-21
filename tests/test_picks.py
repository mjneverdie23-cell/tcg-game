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
    p = {"1x2": np.array([0.55, 0.25, 0.20]), "o15": 0.76, "o25": 0.52, "o35": 0.30,
         "btts": 0.45,
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
    # 82% / fair odds 1.22: a "safe"-style pick (balanced starts at 1.25)
    f = form_check(idx, "A", "B", "2025-10-20", _probs(), {"style": "safe"})
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
    assert set(f["best_by_market"]) == {"1x2", "totals", "btts", "team_totals"}
    f = form_check(idx, "A", "B", "2025-10-20", _probs(), {"markets": ["ou25"]})   # old name
    assert f["settings"]["markets"] == ["totals"]


def test_lift_requires_beating_the_typical_game():
    idx = FormIndex(_scenario())
    typical = {c.key: 0.5 for c in CANDIDATES}
    typical["home_over_0.5"] = 0.80                    # 82% is ordinary in this league
    f = form_check(idx, "A", "B", "2025-10-20", _probs(), {"min_lift": 0.05, "style": "safe"},
                   base=typical)
    assert f["best_pick"] is None or f["best_pick"]["key"] != "home_over_0.5"
    f = form_check(idx, "A", "B", "2025-10-20", _probs(), {"min_lift": 0.0, "style": "safe"},
                   base=typical)
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
             {"o15": 0.76, "o25": 0.52, "o35": 0.30, "btts": 0.45, "h_o05": 0.82,
              "h_o15": 0.55, "h_o25": 0.28,
              "a_o05": 0.55, "a_o15": 0.22, "a_o25": 0.07}.items()}}
    r = backtest(FormIndex(allm), later.reset_index(drop=True), probs, {"min_lift": 0})
    assert r["matches"] == 2 and r["picks"] >= 1 and 0 <= r["hit_rate"] <= 1


def _lopsided():
    """A league with strong (S, T*), middling (F*) and weak (W, V*) sides:
    ratings separate first, then strong sides play weak ones."""
    rows, d = [], pd.Timestamp("2025-08-01")
    strong, mid, weak = ["S", "T1", "T2", "T3"], [f"F{i}" for i in range(5)], ["W", "V1", "V2", "V3"]
    day = 0
    for _ in range(2):
        for f in mid:
            for t in strong:
                rows.append(_m(d + pd.Timedelta(days=day), t, f, 3, 0)); day += 1
            for w in weak:
                rows.append(_m(d + pd.Timedelta(days=day), f, w, 2, 0)); day += 1
    for v in ("V1", "V2", "V3"):                      # S against weak sides
        rows.append(_m(d + pd.Timedelta(days=day), "S", v, 3, 0)); day += 1
    for t in ("T1", "T2", "T3"):                      # W against strong sides
        rows.append(_m(d + pd.Timedelta(days=day), t, "W", 3, 0)); day += 1
    return pd.DataFrame(rows)


def test_lopsided_match_climbs_the_ladder():
    idx = FormIndex(_lopsided())
    when = "2026-03-01"
    assert idx.rating("S", when) - idx.rating("W", when) > 150
    sim = idx.similar("S", "W", when)
    assert len(sim) >= 3 and all(r["gf"] >= 2 for r in sim)      # S vs weak sides
    probs = _probs(**{"1x2": np.array([0.80, 0.13, 0.07]), "h_o05": 0.95, "h_o15": 0.78,
                      "h_o25": 0.55, "a_o05": 0.40, "a_o15": 0.12, "a_o25": 0.03,
                      "o15": 0.86, "o25": 0.66, "o35": 0.42, "btts": 0.38})
    f = form_check(idx, "S", "W", when, probs)                       # balanced style
    assert f["gap"]["lopsided"] and f["gap"]["favourite"] == "S"
    assert f["too_short"] is not None and f["too_short"]["fair_odds"] < 1.25
    b = f["best_pick"]
    assert b is not None and b["key"] != "home_over_0.5"
    assert 1.25 <= b["fair_odds"] <= 2.20
    assert b["key"] in {"home_win", "home_over_1.5", "home_over_2.5", "over_2.5", "btts_no",
                        "away_under_0.5"}
    assert "too short" in f["reason"]
    bold = form_check(idx, "S", "W", when, probs, {"style": "bold"})["best_pick"]
    assert bold is None or bold["fair_odds"] >= 1.60


def test_older_model_outputs_without_new_lines_still_work():
    idx = FormIndex(_scenario())
    p = _probs()
    p.pop("o15"); p.pop("o35")
    f = form_check(idx, "A", "B", "2025-10-20", p)
    assert all(c["key"] not in ("over_1.5", "under_3.5") for c in f["candidates"])
