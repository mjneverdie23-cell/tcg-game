"""Scoring rules for the four target markets.

Model selection uses the *combined 4-market skill*: the mean over
{1X2, O/U 2.5, BTTS, team totals} of log-loss skill relative to the base
rate (1 - LL / LL_base). Normalising by the base rate puts the 3-way and
binary markets on the same scale, so no market dominates selection.
"""

from __future__ import annotations

import numpy as np

from footypred.models.scorematrix import BINARY_MARKETS

EPS = 1e-12
TEAM_TOTALS = ["h_o05", "h_o15", "h_o25", "a_o05", "a_o15", "a_o25"]
MARKET_GROUPS = {"1x2": ["1x2"], "o25": ["o25"], "btts": ["btts"], "team_totals": TEAM_TOTALS}


def outcomes(y_h, y_a) -> dict[str, np.ndarray]:
    y_h, y_a = np.asarray(y_h), np.asarray(y_a)
    res = np.where(y_h > y_a, 0, np.where(y_h == y_a, 1, 2))
    return {
        "1x2": res,
        "o15": (y_h + y_a > 1).astype(int), "o25": (y_h + y_a > 2).astype(int),
        "o35": (y_h + y_a > 3).astype(int), "btts": ((y_h > 0) & (y_a > 0)).astype(int),
        "h_o05": (y_h > 0).astype(int), "h_o15": (y_h > 1).astype(int),
        "h_o25": (y_h > 2).astype(int), "a_o05": (y_a > 0).astype(int),
        "a_o15": (y_a > 1).astype(int), "a_o25": (y_a > 2).astype(int),
    }


def binary_logloss(p, y) -> float:
    p = np.clip(p, EPS, 1 - EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def multi_logloss(P, y) -> float:
    P = np.clip(P, EPS, 1)
    return float(-np.mean(np.log(P[np.arange(len(y)), y])))


def brier_binary(p, y) -> float:
    return float(np.mean((p - y) ** 2))


def brier_multi(P, y) -> float:
    Y = np.eye(P.shape[1])[y]
    return float(np.mean(np.sum((P - Y) ** 2, axis=1)))


def rps(P, y) -> float:
    """Ranked probability score for ordered H/D/A outcomes."""
    Y = np.eye(3)[y]
    cp, cy = np.cumsum(P, axis=1), np.cumsum(Y, axis=1)
    return float(np.mean(np.sum((cp - cy)[:, :2] ** 2, axis=1) / 2))


def ece(p, y, bins: int = 10) -> float:
    """Expected calibration error (binary)."""
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges) - 1, 0, bins - 1)
    err = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            err += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(err)


def evaluate(probs: dict[str, np.ndarray], y_h, y_a) -> dict:
    """probs: '1x2' -> (n,3) array; binary markets -> (n,) arrays.
    Returns per-market metrics plus group skills and the combined score."""
    out = outcomes(y_h, y_a)
    res: dict = {}
    P = probs["1x2"]
    y = out["1x2"]
    base = np.bincount(y, minlength=3) / len(y)
    ll = multi_logloss(P, y)
    ll0 = multi_logloss(np.tile(base, (len(y), 1)), y)
    res["1x2"] = {"logloss": ll, "skill": 1 - ll / ll0, "rps": rps(P, y),
                  "brier": brier_multi(P, y), "accuracy": float((P.argmax(1) == y).mean()),
                  "ece": float(np.mean([ece(P[:, k], (y == k).astype(int)) for k in range(3)]))}
    for k in BINARY_MARKETS:
        p, yk = probs[k], out[k]
        ll = binary_logloss(p, yk)
        ll0 = binary_logloss(np.full(len(yk), yk.mean()), yk)
        res[k] = {"logloss": ll, "skill": 1 - ll / ll0 if ll0 > 0 else 0.0,
                  "brier": brier_binary(p, yk), "accuracy": float(((p > 0.5) == yk).mean()),
                  "ece": ece(p, yk)}
    for k in ("o15", "o35"):              # extra lines: reported, not part of selection
        if k in probs:
            p, yk = probs[k], out[k]
            ll = binary_logloss(p, yk)
            ll0 = binary_logloss(np.full(len(yk), yk.mean()), yk)
            res[k] = {"logloss": ll, "skill": 1 - ll / ll0 if ll0 > 0 else 0.0,
                      "brier": brier_binary(p, yk), "accuracy": float(((p > 0.5) == yk).mean()),
                      "ece": ece(p, yk)}
    groups = {g: float(np.mean([res[m]["skill"] for m in ms])) for g, ms in MARKET_GROUPS.items()}
    res["groups"] = groups
    res["combined_skill"] = float(np.mean(list(groups.values())))
    return res


def combined_loss(probs: dict[str, np.ndarray], out: dict[str, np.ndarray],
                  base_ll: dict[str, float]) -> float:
    """Differentiable-friendly objective used to fit ensemble weights:
    mean over market groups of LL / LL_base (lower is better)."""
    g1 = multi_logloss(probs["1x2"], out["1x2"]) / base_ll["1x2"]
    g2 = binary_logloss(probs["o25"], out["o25"]) / base_ll["o25"]
    g3 = binary_logloss(probs["btts"], out["btts"]) / base_ll["btts"]
    g4 = np.mean([binary_logloss(probs[k], out[k]) / base_ll[k] for k in TEAM_TOTALS])
    return float((g1 + g2 + g3 + g4) / 4)


def base_logloss(out: dict[str, np.ndarray]) -> dict[str, float]:
    y = out["1x2"]
    base = np.bincount(y, minlength=3) / len(y)
    res = {"1x2": multi_logloss(np.tile(base, (len(y), 1)), y)}
    for k in BINARY_MARKETS:
        res[k] = binary_logloss(np.full(len(out[k]), out[k].mean()), out[k])
    return res
