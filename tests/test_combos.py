"""Polymarket combos: exact ranking (against brute force), exact counting,
and the Polymarket price parsing they are built on."""

import itertools
import json
import math
import random

import pytest

from footypred.data.sources import polymarket as pm
from footypred.predict.combos import Leg, count_combos, legs_filter, top_combos


def _groups(rng, n_groups, max_legs):
    gs = []
    for g in range(n_groups):
        gs.append([Leg(f"m{g}", f"Match {g}", f"k{g}_{i}", f"pick {g}.{i}",
                       prob=rng.uniform(0.15, 0.9), odds=rng.uniform(1.05, 6.0), price=0.5)
                   for i in range(rng.randint(0, max_legs))])
    return gs


def _brute(groups, objective, lo, hi):
    out = []
    for choice in itertools.product(*[[None] + g for g in groups]):
        legs = [x for x in choice if x is not None]
        if not (lo <= len(legs) <= (hi or len(groups))):
            continue
        p = math.prod(x.prob for x in legs)
        o = math.prod(x.odds for x in legs)
        out.append((p * o - 1 if objective == "ev" else p, tuple(x.key for x in legs)))
    out.sort(key=lambda t: -t[0])
    return out


@pytest.mark.parametrize("seed", range(12))
def test_top_combos_match_brute_force(seed):
    rng = random.Random(seed)
    groups = _groups(rng, rng.randint(2, 7), 3)
    for objective in ("ev", "prob"):
        for lo, hi in ((2, None), (2, 2), (3, 3), (3, None)):
            k = rng.choice([1, 5, 20])
            got = top_combos(groups, k=k, objective=objective, min_legs=lo, max_legs=hi)
            want = _brute(groups, objective, lo, hi)[:k]
            assert len(got) == len(want)
            for g, (score, _) in zip(got, want):
                value = g["ev"] if objective == "ev" else g["prob"]
                assert value == pytest.approx(score, rel=1e-9)
            for g in got:                                   # one leg per match, >= 2 legs
                matches = [leg["fixture"] for leg in g["legs"]]
                assert len(matches) == len(set(matches)) == g["n_legs"] >= lo
                assert g["prob"] == pytest.approx(math.prod(leg["prob"] for leg in g["legs"]))
                assert g["odds"] == pytest.approx(math.prod(leg["odds"] for leg in g["legs"]))
            assert [g["rank"] for g in got] == list(range(1, len(got) + 1))
        sizes = [len(g) for g in groups]
        for lo, hi in ((2, None), (2, 2), (3, None)):
            assert count_combos(sizes, lo, hi) == len(_brute(groups, "prob", lo, hi))


def test_big_days_rank_fast_and_count_exactly():
    import time
    rng = random.Random(7)
    groups = _groups(rng, 40, 6)
    t0 = time.time()
    top = top_combos(groups, k=100, objective="ev")
    assert len(top) == 100 and time.time() - t0 < 15
    assert all(a["ev"] >= b["ev"] for a, b in zip(top, top[1:]))
    sizes = [len(g) for g in groups if g]
    total = count_combos(sizes)
    assert total == math.prod(1 + m for m in sizes) - 1 - sum(sizes)   # all subsets minus 0/1 leg
    assert total > 10 ** 15                                            # far too many to list


def test_legs_filter_and_bad_objective():
    assert legs_filter("any") == (2, None) and legs_filter(3) == (3, 3) and legs_filter("6+") == (6, None)
    with pytest.raises(ValueError):
        legs_filter(1)
    with pytest.raises(ValueError, match="objective"):
        top_combos([[Leg("a", "A", "k", "x", 0.5, 2.0, 0.5)]] * 2, objective="kelly")
    assert top_combos([[Leg("a", "A", "k", "x", 0.5, 2.0, 0.5)]], k=5) == []   # one match


# --------------------------------------------------------- Polymarket parsing
def market(question, outcomes, prices, bid=None, ask=None, **kw):
    return {"question": question, "outcomes": json.dumps(outcomes),
            "outcomePrices": json.dumps([str(p) for p in prices]), "bestBid": bid,
            "bestAsk": ask, "active": True, "closed": False, **kw}


def match_event(slug="epl-ars-che-2026-11-22", kickoff="2026-11-22T15:00:00Z", more=()):
    return {"id": slug, "slug": slug, "title": "Arsenal FC vs. Chelsea FC",
            "endDate": kickoff, "markets": [
                market("Will Arsenal FC win on 2026-11-22?", ["Yes", "No"], [0.52, 0.48],
                       bid=0.51, ask=0.53, gameStartTime=kickoff.replace("T", " "),
                       groupItemTitle="Arsenal FC", sportsMarketType="moneyline"),
                market("Will Arsenal FC vs. Chelsea FC end in a draw?", ["Yes", "No"], [0.26, 0.74],
                       bid=0.25, ask=0.27, groupItemTitle="Draw (Arsenal FC vs. Chelsea FC)"),
                market("Will Chelsea FC win on 2026-11-22?", ["Yes", "No"], [0.23, 0.77],
                       bid=0.22, ask=0.24, groupItemTitle="Chelsea FC"),
                *more]}


def test_event_prices_are_buy_prices():
    e = match_event(more=[
        market("Arsenal FC vs. Chelsea FC: O/U 2.5", ["Over", "Under"], [0.55, 0.45], bid=0.54,
               ask=0.56, line=2.5),
        market("Arsenal FC vs. Chelsea FC: Both Teams to Score", ["Yes", "No"], [0.5, 0.5]),
        market("Spread: Arsenal FC (-1.5)", ["Arsenal FC", "Chelsea FC"], [0.3, 0.7], bid=0.29,
               ask=0.31),
        market("Arsenal FC vs. Chelsea FC: 1st Half O/U 0.5", ["Over", "Under"], [0.7, 0.3]),
        market("Will Arsenal FC win or draw?", ["Yes", "No"], [0.8, 0.2], bid=0.79, ask=0.81),
        market("Will Arsenal FC win the first half?", ["Yes", "No"], [0.4, 0.6]),
        {**market("Will Arsenal FC win on 2026-11-22?", ["Yes", "No"], [0.5, 0.5], ask=0.40),
         "closed": True}])
    q = pm.event_quotes(e, "Arsenal FC", "Chelsea FC", "Arsenal", "Chelsea")
    assert q["home_win"].price == 0.53 and q["home_win"].kind == "ask"    # best ask of Yes
    assert q["draw"].price == 0.27 and q["away_win"].price == 0.24
    assert q["away_plus_0.5"].price == pytest.approx(1 - 0.51)          # No on Arsenal = 1 - bid
    # home +0.5: "No" on Chelsea (1 - 0.22) beats the 0.81 ask of the "win or draw" market
    assert q["home_plus_0.5"].price == pytest.approx(0.78)
    assert q["over_2.5"].price == 0.56 and q["under_2.5"].price == pytest.approx(0.46)
    assert q["btts_yes"].kind == "mid" and q["btts_yes"].price == 0.5   # no order book: midpoint
    assert q["away_plus_1.5"].price == pytest.approx(1 - 0.29)          # the other side of -1.5
    assert "over_0.5" not in q and "ht_over_0.5" not in q                  # first half ignored
    assert q["home_win"].odds == pytest.approx(1 / 0.53)
    p = q["home_win"].as_price(fee=0.02)
    assert p["source"] == "polymarket" and p["price"] == pytest.approx(0.53 * 1.02)


def test_titles_times_and_names():
    assert pm.teams_from_title("Arsenal FC vs. Chelsea FC") == ("Arsenal FC", "Chelsea FC")
    assert pm.teams_from_title("Arsenal vs Chelsea - More Markets") == ("Arsenal", "Chelsea")
    assert pm.teams_from_title("Who will win the Premier League?") is None
    assert str(pm.kickoff_of(match_event())) == "2026-11-22 15:00:00+00:00"
    assert pm.same_team("Arsenal FC", "Arsenal") and pm.same_team("FC Bayern München", "Bayern Munich")
    assert pm.same_team("Manchester United FC", "Manchester United")
    assert not pm.same_team("Manchester City FC", "Manchester United")
    assert not pm.same_team("Real Madrid CF", "Atletico Madrid")
