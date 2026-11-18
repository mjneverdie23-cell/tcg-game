"""Polymarket combos: the best multi-match parlays from the model's picks.

A combo takes at most one pick from each match and has at least two legs.
Matches are treated as independent events, so

    P(combo)    = product of the legs' model probabilities
    odds(combo) = product of the legs' decimal odds (1 / Polymarket price)
    EV          = P(combo) x odds(combo) - 1                (per 1 staked)

Ranking covers *every* such combo without listing them. In log space both
objectives are sums over the legs:

    EV ranking:          log(EV + 1) = sum of log(p_i x odds_i)
    probability ranking: log P       = sum of log(p_i)

With at most one leg per match, the k best combos with exactly l legs are
built match by match, keeping only the k best partial combos for each leg
count. That is exact: if a combo's part over the first matches weren't
among the k best partial combos with its leg count, each of those k could
take the same remaining legs and beat it, so it couldn't be in the top k.
Cost: O(matches x legs x k x picks per match), milliseconds for a match
day, where listing everything would mean millions of combos.

The number of combos is counted exactly too: with m_g picks in match g,
the combos with l legs number e_l(m_1, ..., m_G), the elementary symmetric
polynomial (the coefficient of x^l in the product of (1 + m_g x)).
"""

from __future__ import annotations

import heapq
import math
from dataclasses import asdict, dataclass
from itertools import count
from operator import itemgetter

OBJECTIVES = ("ev", "prob")


@dataclass(frozen=True)
class Leg:
    fixture: str            # id of the match (one leg per match)
    match: str              # "Arsenal v Chelsea"
    key: str                # selection key
    label: str              # "Arsenal to win"
    prob: float             # model probability
    odds: float             # decimal odds on Polymarket (1 / price)
    price: float            # cost of a $1 share
    kind: str = "ask"       # "ask" order-book price, "mid" midpoint
    kickoff: str | None = None
    competition: str | None = None
    url: str | None = None

    @property
    def ev(self) -> float:
        return self.prob * self.odds - 1.0

    def to_dict(self) -> dict:
        return {**asdict(self), "ev": round(self.ev, 4)}


def count_combos(sizes: list[int], min_legs: int = 2, max_legs: int | None = None) -> int:
    """Exact number of combos with min_legs..max_legs legs, one leg per
    match from matches with sizes[g] picks each (Python ints: no overflow)."""
    e = [1]                                     # e[l] = combos with exactly l legs so far
    for m in sizes:
        if m <= 0:
            continue
        e = [(e[i] if i < len(e) else 0) + (m * e[i - 1] if i >= 1 else 0)
             for i in range(len(e) + 1)]
    hi = len(e) - 1 if max_legs is None else min(max_legs, len(e) - 1)
    return sum(e[min_legs:hi + 1]) if hi >= min_legs else 0


def top_combos(groups: list[list[Leg]], k: int = 100, objective: str = "ev",
               min_legs: int = 2, max_legs: int | None = None) -> list[dict]:
    """The k best combos over all combos with min_legs..max_legs legs and at
    most one leg per group (exact; see the module docstring)."""
    if objective not in OBJECTIVES:
        raise ValueError(f"objective must be one of {', '.join(OBJECTIVES)}")
    groups = [g for g in groups if g]
    if k <= 0 or len(groups) < max(min_legs, 1):
        return []
    top = len(groups) if max_legs is None else min(max_legs, len(groups))
    if top < min_legs:
        return []
    weight = ((lambda leg: math.log(leg.prob * leg.odds)) if objective == "ev"
              else (lambda leg: math.log(leg.prob)))
    uid = count(1)
    # a node is (score, uid, leg, parent node); dp[l] = the k best with exactly l legs
    dp: list[list[tuple]] = [[(0.0, 0, None, None)]] + [[] for _ in range(top)]
    for g, legs in enumerate(groups):
        scored = [(weight(leg), leg) for leg in legs if leg.prob > 0 and leg.odds > 1]
        if not scored:
            continue
        # descending l: dp[l - 1] still holds combos without this match's legs
        for ell in range(min(top, g + 1), 0, -1):
            prev = dp[ell - 1]
            if not prev:
                continue
            grown = [(node[0] + w, next(uid), leg, node) for node in prev for w, leg in scored]
            dp[ell] = heapq.nlargest(k, dp[ell] + grown, key=itemgetter(0, 1))
    finals = [node for ell in range(min_legs, top + 1) for node in dp[ell]]
    best = heapq.nlargest(k, finals, key=itemgetter(0, 1))
    out = []
    for rank, node in enumerate(best, 1):
        legs, n = [], node
        while n is not None and n[2] is not None:
            legs.append(n[2])
            n = n[3]
        legs.reverse()
        prob = math.prod(leg.prob for leg in legs)
        odds = math.prod(leg.odds for leg in legs)
        out.append({"rank": rank, "n_legs": len(legs), "prob": prob, "odds": odds,
                    "ev": prob * odds - 1.0, "legs": [leg.to_dict() for leg in legs]})
    return out


def legs_filter(value) -> tuple[int, int | None]:
    """'any' -> (2, None); 3 -> (3, 3); '6+' -> (6, None)."""
    if value in (None, "", "any"):
        return 2, None
    s = str(value).strip()
    if s.endswith("+"):
        n = int(s[:-1])
        return max(n, 2), None
    n = int(s)
    if n < 2:
        raise ValueError("a combo has at least 2 legs")
    return n, n
