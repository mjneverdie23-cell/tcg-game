"""Explanations grounded in past match details.

* evidence()  — raw counts from each team's recent matches, per market
                ("scored in 7/8 home games", "BTTS in 6/10", H2H record)
* drivers()   — per-market feature contributions (exact TreeSHAP via
                LightGBM pred_contrib) from the direct market models
* humanize()  — readable names for engineered features
"""

from __future__ import annotations

import re

import numpy as np

from footypred.features.engineering import GA, GF, VEN, XGA, XGF

STAT_TEXT = {
    "gf": "goals scored/game", "ga": "goals conceded/game", "xgf": "xG for/game",
    "xga": "xG against/game", "sotf": "shots on target/game", "sota": "shots on target against",
    "s1": "scored-in rate", "s2": "scored 2+ rate", "s3": "scored 3+ rate",
    "c1": "conceded-in rate", "c2": "conceded 2+ rate", "c3": "conceded 3+ rate",
    "btts": "BTTS rate", "o25": "over-2.5 rate", "win": "win rate", "draw": "draw rate",
    "ppg": "points/game", "ht": "1st-half goals/game", "gf_res": "goals vs expectation",
    "ga_res": "conceded vs expectation", "btts_res": "BTTS above expectation",
    "o25_res": "over-2.5 above expectation", "tot_disp": "match-total volatility",
    "n_hist": "matches on record", "trusted": "enough history", "rest": "rest days",
    "cong21": "matches in last 21 days", "elo": "Elo rating", "rt_att": "attack rating",
    "rt_def": "defence rating", "rx_att": "xG attack rating", "rx_def": "xG defence rating",
}
WIN_TEXT = {"s5": "last 5", "l10": "last 10", "ew": "weighted form", "v": "at venue"}
OTHER_TEXT = {
    "rt_lh": "rating-expected home goals", "rt_la": "rating-expected away goals",
    "rx_lh": "xG-rating expected home goals", "rx_la": "xG-rating expected away goals",
    "rx_sup": "xG-rating goal supremacy", "rx_tot": "xG-rating expected total goals",
    "elo_diff": "Elo difference", "elo_exp": "Elo win expectancy",
    "m_btts": "combined BTTS rate", "m_btts_v": "combined BTTS rate (venue)",
    "m_btts_prod": "both-score likelihood from records", "m_o25": "combined over-2.5 rate",
    "m_o25_v": "combined over-2.5 rate (venue)", "m_btts_res": "BTTS tendency vs strength",
    "m_o25_res": "over-2.5 tendency vs strength", "m_disp": "combined totals volatility",
    "m_xg_h": "home xG vs away xGA", "m_xg_a": "away xG vs home xGA",
    "m_gl_h": "home goals vs away concessions", "m_gl_a": "away goals vs home concessions",
    "h2h_n": "H2H meetings", "h2h_tot": "H2H goals/game", "h2h_btts": "H2H BTTS rate",
    "h2h_o25": "H2H over-2.5 rate", "h2h_gd": "H2H goal difference",
    "lg_gpm": "league goals/game", "lg_btts": "league BTTS rate", "lg_o25": "league over-2.5 rate",
    "lg_hw": "league home-win rate", "lg_dr": "league draw rate", "neutral": "neutral venue",
    "intl": "international match", "season_prog": "season progress", "rest_diff": "rest-day gap",
}


def humanize(feat: str, home: str = "Home", away: str = "Away") -> str:
    if feat in OTHER_TEXT:
        return OTHER_TEXT[feat]
    m = re.match(r"pr_(.+)", feat)
    if m:
        what = {"home": "home win", "draw": "draw", "away": "away win", "o25": "over 2.5",
                "btts": "BTTS", "h_o05": f"{home} over 0.5", "h_o15": f"{home} over 1.5",
                "h_o25": f"{home} over 2.5", "a_o05": f"{away} over 0.5",
                "a_o15": f"{away} over 1.5", "a_o25": f"{away} over 2.5"}.get(m.group(1), m.group(1))
        return f"rating-implied P({what})"
    m = re.match(r"m_([ha])(v?)_s(\d)", feat)
    if m:
        team = home if m.group(1) == "h" else away
        return f"{team} {m.group(3)}+ goals likelihood{' (venue)' if m.group(2) else ''}"
    m = re.match(r"x_(\w+)_(h|a|diff)", feat)
    if m:
        who = {"h": home, "a": away, "diff": "difference"}[m.group(2)]
        what = {"mv": "squad market value", "clubelo": "ClubElo rating",
                "fifa": "FIFA ranking points"}.get(m.group(1), m.group(1))
        return f"{what} ({who})"
    m = re.match(r"([ha])_(s5|l10|ew|v)_(\w+)", feat)
    if m:
        team = home if m.group(1) == "h" else away
        win = WIN_TEXT[m.group(2)]
        if m.group(2) == "v":
            win = "home games" if m.group(1) == "h" else "away games"
        return f"{team} {STAT_TEXT.get(m.group(3), m.group(3))} ({win})"
    m = re.match(r"([ha])_(\w+)", feat)
    if m:
        team = home if m.group(1) == "h" else away
        return f"{team} {STAT_TEXT.get(m.group(2), m.group(2))}"
    return feat


# ---------------------------------------------------------------- evidence
def _counts(recs) -> dict:
    n = len(recs)
    if not n:
        return {"n": 0}
    gf = np.array([r[GF] for r in recs]); ga = np.array([r[GA] for r in recs])
    xgf = np.array([r[XGF] for r in recs], float); xga = np.array([r[XGA] for r in recs], float)
    return {
        "n": n, "w": int((gf > ga).sum()), "d": int((gf == ga).sum()), "l": int((gf < ga).sum()),
        "scored": int((gf > 0).sum()), "scored2": int((gf > 1).sum()),
        "scored3": int((gf > 2).sum()), "conceded": int((ga > 0).sum()),
        "clean": int((ga == 0).sum()), "btts": int(((gf > 0) & (ga > 0)).sum()),
        "o25": int((gf + ga > 2).sum()), "gf": float(gf.mean()), "ga": float(ga.mean()),
        "xgf": float(np.nanmean(xgf)) if np.isfinite(xgf).any() else None,
        "xga": float(np.nanmean(xga)) if np.isfinite(xga).any() else None,
    }


def evidence(state, home: str, away: str, neutral: bool = False) -> dict:
    hv, av = ("N", "N") if neutral else ("H", "A")
    hh = list(state.hist.get(home, ()))
    ah = list(state.hist.get(away, ()))
    hven = [r for r in state.venue.get((home, hv), ())]
    aven = [r for r in state.venue.get((away, av), ())]
    meets = list(state.h2h.get(frozenset((home, away)), ()))
    h2h = None
    if meets:
        res = [(m[1] - m[2]) if m[0] == home else (m[2] - m[1]) for m in meets]
        h2h = {"n": len(meets), "home_w": sum(r > 0 for r in res), "d": sum(r == 0 for r in res),
               "away_w": sum(r < 0 for r in res),
               "btts": sum((m[1] > 0 and m[2] > 0) for m in meets),
               "o25": sum(m[1] + m[2] > 2 for m in meets),
               "goals": float(np.mean([m[1] + m[2] for m in meets])),
               "scores": [f"{m[0]} {m[1]}-{m[2]}" for m in meets[-3:]]}
    return {"home": {"last": _counts(hh), "venue": _counts(hven), "venue_label": "home" if not neutral else "neutral"},
            "away": {"last": _counts(ah), "venue": _counts(aven), "venue_label": "away" if not neutral else "neutral"},
            "h2h": h2h}


# ----------------------------------------------------------------- drivers
DRIVER_MARKETS = {"1x2": "Home win", "o25": "Over 2.5", "btts": "BTTS",
                  "h_o15": "Home over 1.5", "a_o15": "Away over 1.5"}


def drivers(direct, row, fcols, home: str, away: str, top: int = 4) -> dict:
    """Top feature contributions (log-odds) per market for this fixture."""
    X = row[fcols].values.astype(np.float32)
    out = {}
    for k, label in DRIVER_MARKETS.items():
        model = direct.gbm.get(k)
        if model is None:
            continue
        contrib = model.booster_.predict(X, pred_contrib=True)[0]
        F = len(fcols)
        if k == "1x2":
            contrib = contrib[:F + 1]          # class 0 = home win
        vals = contrib[:F]
        order = np.argsort(-np.abs(vals))[:top]
        out[k] = {"label": label,
                  "items": [(humanize(fcols[i], home, away), float(vals[i]),
                             float(row[fcols[i]].iloc[0])) for i in order]}
    return out
