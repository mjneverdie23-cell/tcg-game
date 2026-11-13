"""High stake mode: the club list, each team's upset record, the owner &
sponsor factor on the score grid, and 1.70+ picks with handicaps and the
BTTS + over 2.5 combo."""

import numpy as np
import pandas as pd
import pytest

from footypred.models.scorematrix import ScoreMatrix
from footypred.predict import highstake as hs
from footypred.predict.picks import (CANDIDATES, FOCUS_MARKETS, FormIndex, base_rates, form_check)


def test_club_list_loads_and_counts_only_real_control():
    flags = hs.load_flags(hs.flags_path(None))
    assert flags["Chelsea"].american and flags["Chelsea"].betting and flags["Chelsea"].count == 2
    assert flags["Bayern Munich"].betting and not flags["Bayern Munich"].american
    assert flags["Augsburg"].count == 0                     # 45% minority stake: listed, not counted
    assert flags["Sevilla"].count == 0                      # sale agreed, not completed
    assert hs.alerts_for(flags, "Augsburg") is None
    a = hs.alerts_for(flags, "Inter Milan")["alerts"]
    assert a[0].startswith("American owner: Oaktree") and a[1].startswith("Betting sponsor: Betsson")
    assert "2025-26" in flags["Udinese"].alerts()[0]        # last season's deal is labelled
    # names are matched exactly (or ignoring case/accents), never fuzzily
    fl = hs.load_flags(hs.flags_path(None), known=["Manchester United", "Inter"])
    assert "Manchester United" in fl and "Inter Milan" in fl and "Inter" not in fl


def _league(rounds=40, flip=20):
    """Six teams; S wins everything for `flip` rounds, then keeps slipping."""
    teams = ["S", "A", "B", "C", "D", "E"]
    rows, d = [], pd.Timestamp("2024-08-01")
    for r in range(rounds):
        order = teams[:1] + teams[1:][r % 5:] + teams[1:][:r % 5]
        for k in range(3):
            h, a = (order[k], order[5 - k]) if r % 2 == 0 else (order[5 - k], order[k])
            if "S" in (h, a):
                s_goals, o_goals = (3, 0) if r < flip else ((1, 1) if r % 2 else (0, 1))
                gh, ga = (s_goals, o_goals) if h == "S" else (o_goals, s_goals)
            else:
                gh, ga = [(1, 0), (1, 1), (0, 1)][(r + k) % 3]
            rows.append({"match_id": f"{r}{k}", "date": d + pd.Timedelta(days=7 * r), "home": h,
                         "away": a, "fthg": gh, "ftag": ga, "league": "L", "neutral": 0, "season": 2024})
    return pd.DataFrame(rows)


def test_upset_record_and_the_factor_on_the_grid():
    m = _league()
    prof = hs.UpsetProfiles(FormIndex(m))
    when = m["date"].max() + pd.Timedelta(days=7)
    s = prof.profile("S", when)
    assert s["fav_games"] >= 15 and s["fav_slips"] > s["fav_slips_expected"] and s["slip_ratio"] > 1.2
    grid = ScoreMatrix.poisson(2.0, 0.6).grid
    flags = {"S": hs.ClubFlags("S", owner="Owner LLC", owner_stake="majority", sponsor="BetCo")}
    before = hs._outcomes(grid)

    same, info = hs.adjust(grid, "S", "A", flags, prof, 0.0, when)          # slider at 0%
    assert np.allclose(same, grid) and not info["applied"]
    same, info = hs.adjust(grid, "S", "A", {}, prof, 1.0, when)             # nobody flagged
    assert np.allclose(same, grid) and not info["applied"] and "Neither" in info["text"]

    half, info_half = hs.adjust(grid, "S", "A", flags, prof, 0.5, when)
    full, info = hs.adjust(grid, "S", "A", flags, prof, 1.0, when)
    assert info["applied"] and info["flags"] == 2 and info["ratio"] > 1 and info["favourite"] == "S"
    assert abs(full.sum() - 1) < 1e-9 and (full >= 0).all()
    after = hs._outcomes(full)
    assert after[0] < hs._outcomes(half)[0] < before[0]                     # bigger slider, bigger move
    # draws and away wins keep their proportions
    assert after[1] / after[2] == pytest.approx(before[1] / before[2], rel=1e-9)
    assert info["profiles"]["favourite"]["team"] == "S" and "chance of not winning" in info["text"]
    # one flag counts half
    one = {"S": hs.ClubFlags("S", sponsor="BetCo")}
    _, info_one = hs.adjust(grid, "S", "A", one, prof, 1.0, when)
    assert info_one["flag_weight"] == 0.5 and info_one["after"][0] > after[0]


def test_extra_markets_off_the_grid():
    grid = ScoreMatrix.poisson(1.4, 1.1, rho=-0.05).grid
    p = hs.extra_probs(grid)
    o = hs._outcomes(grid)
    assert p["hcp_h05"] == pytest.approx(o[0] + o[1]) and p["hcp_a05"] == pytest.approx(o[1] + o[2])
    assert p["hcp_h15"] > p["hcp_h05"] and p["hcp_a15"] > p["hcp_a05"]
    mk = ScoreMatrix.from_grid(grid).markets()
    assert p["btts_o25"] < min(mk["btts"], mk["o25"])


def test_handicap_and_combo_candidates():
    c = {x.key: x for x in CANDIDATES}
    assert c["home_plus_1.5"].test_home_side(0, 1) and not c["home_plus_1.5"].test_home_side(0, 2)
    assert c["home_plus_1.5"].test_away_side(1, 0) and not c["home_plus_1.5"].test_away_side(2, 0)
    assert c["away_plus_0.5"].test_home_side(1, 1) and not c["away_plus_0.5"].test_home_side(2, 1)
    assert c["btts_and_over_2.5"].test_home_side(2, 1) and not c["btts_and_over_2.5"].test_home_side(1, 1)


def _probs():
    return {"1x2": np.array([0.55, 0.25, 0.20]), "o15": 0.76, "o25": 0.52, "o35": 0.30, "btts": 0.48,
            "h_o05": 0.82, "h_o15": 0.55, "h_o25": 0.28, "a_o05": 0.58, "a_o15": 0.22, "a_o25": 0.07,
            "hcp_h05": 0.80, "hcp_h15": 0.91, "hcp_a05": 0.45, "hcp_a15": 0.64, "btts_o25": 0.36}


def test_high_stake_picks_are_1_70_and_up_and_lead_with_the_focus_markets():
    m = _league(rounds=30, flip=30)
    idx = FormIndex(m)
    when = m["date"].max() + pd.Timedelta(days=7)
    base = base_rates(m, min_league_games=10).get("L")
    f = form_check(idx, "A", "B", when, _probs(), {"mode": "high"})        # no league yardstick
    st = f["settings"]
    assert st["mode"] == "high" and st["min_odds"] >= 1.70 and "handicap" in st["markets"]
    elig = [c for c in f["candidates"] if c["eligible"]]
    assert elig and all(c["fair_odds"] >= 1.70 for c in elig)
    assert all(c["fair_odds"] >= 1.70 for c in f["top_picks"])
    assert f["best_pick"]["market"] in FOCUS_MARKETS                  # focus markets first
    short = next(c for c in f["candidates"] if c["key"] == "home_plus_0.5")
    assert not short["eligible"] and "too short" in short["fails"]       # 0.80 -> 1.25
    assert {"handicap", "combo"} <= set(f["best_by_market"])
    # a lower min odds can't take high stake mode under 1.70
    low = form_check(idx, "A", "B", when, _probs(), {"mode": "high", "min_odds": 1.3}, base=base)
    assert low["settings"]["min_odds"] == 1.70
    # balanced mode is unchanged: no handicap / combo picks or rows
    bal = form_check(idx, "A", "B", when, _probs(), {}, base=base)
    assert bal["settings"]["mode"] == "balanced"
    assert not any(c["market"] in ("handicap", "combo") and c["eligible"] for c in bal["candidates"])
    assert not {"handicap", "combo"} & set(bal["best_by_market"])
    with pytest.raises(ValueError, match="mode"):
        form_check(idx, "A", "B", when, _probs(), {"mode": "reckless"})
