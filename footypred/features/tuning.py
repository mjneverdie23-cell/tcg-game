"""Data-driven tuning of the online rating systems.

The ratings feed the most important features, so their learning rate and
the goals-vs-xG blend are tuned on *prequential* log-likelihood: each
match is predicted from ratings that have only seen earlier matches, then
the ratings learn from it. No hold-out needed and no leakage possible.
"""

from __future__ import annotations

import math

import pandas as pd

from footypred.features.ratings import PoissonRatings
from footypred.logging_utils import get_logger

log = get_logger("features.tuning")


def prequential_nll(records: list[dict], lr: float, xg_weight: float,
                    burn_in_season: int) -> float:
    r = PoissonRatings(lr=lr)
    ll, n = 0.0, 0
    for x in records:
        neutral = bool(x.get("neutral") or 0)
        lh, la = r.rates(x["home"], x["away"], x["league"], neutral)
        gh, ga = x["fthg"], x["ftag"]
        if x["season"] >= burn_in_season:
            ll += gh * math.log(lh) - lh + ga * math.log(la) - la
            n += 1
        hx, ax = x.get("home_xg"), x.get("away_xg")
        if xg_weight > 0 and hx is not None and not pd.isna(hx) and not pd.isna(ax):
            bh = (1 - xg_weight) * gh + xg_weight * hx
            ba = (1 - xg_weight) * ga + xg_weight * ax
        else:
            bh, ba = gh, ga
        r.update(x["home"], x["away"], x["league"], bh, ba, neutral)
    return -ll / max(n, 1)


def tune_ratings(matches: pd.DataFrame) -> dict:
    """Coordinate search; returns feature-config overrides."""
    m = matches.sort_values(["date", "match_id"])
    recs = m.to_dict("records")
    seasons = sorted(m["season"].unique())
    burn = seasons[1] if len(seasons) > 1 else seasons[0]

    goals_grid = [0.006, 0.01, 0.015, 0.02, 0.03, 0.045]
    scores = {lr: prequential_nll(recs, lr, 0.0, burn) for lr in goals_grid}
    rt_lr = min(scores, key=scores.get)
    out = {"rt_lr": rt_lr, "rx_lr": rt_lr, "rx_xg_weight": 0.0,
           "tuning": {"goals_nll": round(scores[rt_lr], 5)}}

    xg_cov = m["home_xg"].notna().mean() if "home_xg" in m else 0.0
    if xg_cov >= 0.5:
        wx_scores = {wx: prequential_nll(recs, 0.03, wx, burn) for wx in (0.25, 0.5, 0.75, 1.0)}
        wx = min(wx_scores, key=wx_scores.get)
        lr_scores = {lr: prequential_nll(recs, lr, wx, burn)
                     for lr in (0.015, 0.02, 0.03, 0.045, 0.06)}
        rx_lr = min(lr_scores, key=lr_scores.get)
        out.update({"rx_lr": rx_lr, "rx_xg_weight": wx})
        out["tuning"]["xg_nll"] = round(lr_scores[rx_lr], 5)
    log.info("rating tuning: goals lr=%s, xG-blend lr=%s weight=%s (xG coverage %.0f%%)",
             out["rt_lr"], out["rx_lr"], out["rx_xg_weight"], 100 * xg_cov)
    return out
