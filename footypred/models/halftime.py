"""First-half model: the score distribution at half-time, and from it the
first-half markets (1X2, over/under 0.5 / 1.5 / 2.5, BTTS).

Candidates, each tested out of sample on the trainer's later folds (fitted
on earlier data only):

* "scaled": the full-time model's expected goals turned into first-half
  rates, log λ_HT = a + b·log λ_FT(own) + c·log λ_FT(opponent), fitted on
  half-time scores (about 45% of goals come before the break), with a
  Dixon-Coles low-score adjustment (first halves end 0-0 about 30% of
  the time). It stays consistent with the full-time prediction.
* the goal models fitted directly on half-time scores, using the same
  pre-match features (Dixon-Coles and Poisson regression by default).
* a 50/50 blend of the best two. Its weights are fixed, so its score is as
  honest as the others'.

The best one is kept and refitted on everything. Matches without a
half-time score (football-data.co.uk's Eliteserien file has none) are only
left out of this model; it still predicts those teams.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from footypred.logging_utils import get_logger
from footypred.models.metrics import binary_logloss, ece, multi_logloss
from footypred.models.scorematrix import market_probs

log = get_logger("models.halftime")

HT_G = 7                                  # 0..6 first-half goals per side
HT_MODELS = ["poisson", "dixon_coles"]
HT_MARKETS = ["1x2", "o05", "o15", "o25", "btts"]
HT_LABELS = {"1x2": "HT 1X2", "o05": "HT over 0.5", "o15": "HT over 1.5", "o25": "HT over 2.5",
             "btts": "HT BTTS"}
MIN_MATCHES = 400


def ht_probs(grids) -> dict[str, np.ndarray]:
    p = market_probs(grids)
    out = {"1x2": np.column_stack([p["home"], p["draw"], p["away"]])}
    out.update({k: p[k] for k in ("o05", "o15", "o25", "btts", "h_o05", "a_o05")})
    return out


def ht_outcomes(yh, ya) -> dict[str, np.ndarray]:
    yh, ya = np.asarray(yh, int), np.asarray(ya, int)
    return {"1x2": np.where(yh > ya, 0, np.where(yh == ya, 1, 2)),
            "o05": (yh + ya > 0).astype(int), "o15": (yh + ya > 1).astype(int),
            "o25": (yh + ya > 2).astype(int), "btts": ((yh > 0) & (ya > 0)).astype(int),
            "h_o05": (yh > 0).astype(int), "a_o05": (ya > 0).astype(int)}


def evaluate_ht(probs: dict, yh, ya) -> dict:
    """Log loss, skill over the base rate, accuracy and calibration error per
    first-half market; combined = mean skill over HT_MARKETS."""
    out = ht_outcomes(yh, ya)
    res = {}
    y = out["1x2"]
    base = np.bincount(y, minlength=3) / max(len(y), 1)
    ll, ll0 = multi_logloss(probs["1x2"], y), multi_logloss(np.tile(base, (len(y), 1)), y)
    res["1x2"] = {"logloss": ll, "skill": 1 - ll / ll0 if ll0 > 0 else 0.0,
                  "accuracy": float((probs["1x2"].argmax(1) == y).mean()),
                  "ece": float(np.mean([ece(probs["1x2"][:, k], (y == k).astype(int)) for k in range(3)]))}
    for k in HT_MARKETS[1:] + ["h_o05", "a_o05"]:
        p, yk = probs[k], out[k]
        ll = binary_logloss(p, yk)
        ll0 = binary_logloss(np.full(len(yk), yk.mean()), yk)
        res[k] = {"logloss": ll, "skill": 1 - ll / ll0 if ll0 > 0 else 0.0,
                  "accuracy": float(((p > 0.5) == yk).mean()), "ece": ece(p, yk)}
    res["combined_skill"] = float(np.mean([res[k]["skill"] for k in HT_MARKETS]))
    return res


class ScaledHT:
    """First-half rates from the full-time expected goals (see module doc)."""
    name = "scaled"

    def fit(self, lh, la, yh, ya) -> "ScaledHT":
        from sklearn.linear_model import PoissonRegressor
        from footypred.models.goal_models import fit_rho
        lh, la = np.clip(lh, 0.05, 8), np.clip(la, 0.05, 8)
        self.mh = PoissonRegressor(alpha=1e-4, max_iter=500).fit(_xs(lh, la), yh)
        self.ma = PoissonRegressor(alpha=1e-4, max_iter=500).fit(_xs(la, lh), ya)
        rh, ra = self.rates(lh, la)
        self.rho = fit_rho(rh, ra, np.asarray(yh), np.asarray(ya))
        return self

    def rates(self, lh, la):
        lh, la = np.clip(lh, 0.05, 8), np.clip(la, 0.05, 8)
        return self.mh.predict(_xs(lh, la)), self.ma.predict(_xs(la, lh))

    def predict_grids(self, lh, la, G: int = HT_G) -> np.ndarray:
        from footypred.models.scorematrix import poisson_grids
        rh, ra = self.rates(np.atleast_1d(lh), np.atleast_1d(la))
        return poisson_grids(np.clip(rh, 0.02, 4), np.clip(ra, 0.02, 4), self.rho, G)


def _xs(own, opp):
    return np.column_stack([np.log(own), np.log(opp)])


def expected_goals(grids: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    k = np.arange(grids.shape[-1])
    return (grids.sum(axis=2) * k).sum(axis=1), (grids.sum(axis=1) * k).sum(axis=1)


@dataclass
class HalfTimeModel:
    models: dict
    weights: dict
    report: dict = field(default_factory=dict)
    G: int = HT_G

    def predict_grids(self, rows: pd.DataFrame, fcols: list[str], ft_lam=None) -> np.ndarray:
        """ft_lam: (home, away) full-time expected goals for the same rows,
        needed by the "scaled" model."""
        w = {n: v for n, v in self.weights.items() if v > 0 and (n != "scaled" or ft_lam is not None)}
        total = sum(w.values()) or 1.0
        out = 0
        for n, v in w.items():
            g = (self.models[n].predict_grids(ft_lam[0], ft_lam[1], self.G) if n == "scaled"
                 else self.models[n].predict_grids(rows, fcols, self.G))
            out = out + (v / total) * g
        return out


def train_halftime(frame: pd.DataFrame, fcols: list[str], tests: list, make,
                   names: list[str] | None = None, ft_lam: pd.DataFrame | None = None
                   ) -> HalfTimeModel | None:
    """frame: the trainer's feature frame (with its `fold` column); tests: its
    test folds; make(name) -> a fresh goal model; ft_lam: out-of-fold
    full-time expected goals (columns lh, la), indexed like frame."""
    t0 = time.time()
    names = list(names or HT_MODELS)
    ht = frame[frame["y_ht_h"].notna() & frame["y_ht_a"].notna()].copy()
    if len(ht) < MIN_MATCHES:
        log.info("first half: only %d matches with half-time scores — skipped", len(ht))
        return None
    ht["y_h"], ht["y_a"] = ht["y_ht_h"].astype(int), ht["y_ht_a"].astype(int)
    folds = [s for s in tests if (ht["fold"] == s).sum() >= 30 and (ht["fold"] < s).sum() >= 200]
    lam = ft_lam.reindex(ht.index) if ft_lam is not None else None
    log.info("first half: %d matches with half-time scores (%.0f%%)", len(ht), 100 * len(ht) / len(frame))
    report = {"matches": int(len(ht)), "coverage": round(len(ht) / len(frame), 3)}
    ev_folds = folds[1:]
    cand: dict[str, list] = {}
    if len(ev_folds):
        for s in ev_folds:                         # every candidate fitted on data before s only
            tr, te = ht[ht["fold"] < s], ht[ht["fold"] == s]
            for n in names:
                cand.setdefault(n, []).append(ht_probs(make(n).oof_grids(tr, te, fcols, HT_G)))
            if lam is not None:
                trl = tr[lam.loc[tr.index, "lh"].notna()]
                if len(trl) >= 200:
                    m = ScaledHT().fit(lam.loc[trl.index, "lh"], lam.loc[trl.index, "la"],
                                       trl["y_h"].values, trl["y_a"].values)
                    cand.setdefault("scaled", []).append(
                        ht_probs(m.predict_grids(lam.loc[te.index, "lh"].values,
                                                 lam.loc[te.index, "la"].values)))
        cat = lambda ps: {k: np.concatenate([p[k] for p in ps]) for k in ps[0]}
        cand = {n: cat(ps) for n, ps in cand.items() if len(ps) == len(ev_folds)}
        order = np.concatenate([ht.index[ht["fold"] == s] for s in ev_folds])
        yh, ya = ht.loc[order, "y_h"].values, ht.loc[order, "y_a"].values
        scores = {n: evaluate_ht(p, yh, ya) for n, p in cand.items()}
        top = sorted(scores, key=lambda n: -scores[n]["combined_skill"])[:2]
        if len(top) == 2:
            blend = {k: 0.5 * cand[top[0]][k] + 0.5 * cand[top[1]][k] for k in cand[top[0]]}
            scores["blend"] = evaluate_ht(blend, yh, ya)
        selected = max(scores, key=lambda n: scores[n]["combined_skill"])
        weights = {top[0]: 0.5, top[1]: 0.5} if selected == "blend" else {selected: 1.0}
        out = ht_outcomes(yh, ya)
        report.update({"eval_matches": int(len(order)), "candidates": scores, "selected": selected,
                       "weights": weights, "eval": scores[selected],
                       "base_rates": {"draw": float((out["1x2"] == 1).mean()),
                                      **{k: float(out[k].mean()) for k in ("o05", "o15", "o25", "btts")}}})
        log.info("first half: selected %s, combined skill %.4f out of sample (%d matches)",
                 selected, scores[selected]["combined_skill"], len(order))
    else:
        weights = {"scaled": 1.0} if lam is not None and lam["lh"].notna().sum() >= 200 else \
            {("dixon_coles" if "dixon_coles" in names else names[0]): 1.0}
        report.update({"eval_matches": 0, "selected": "+".join(weights), "weights": weights})
    models = {}
    for n in weights:                                 # refit the chosen one(s) on everything
        if n == "scaled":
            ok = lam["lh"].notna()
            models[n] = ScaledHT().fit(lam.loc[ok, "lh"], lam.loc[ok, "la"],
                                       ht.loc[ok, "y_h"].values, ht.loc[ok, "y_a"].values)
        else:
            models[n] = make(n).fit(ht, fcols)
    report["seconds"] = round(time.time() - t0, 1)
    return HalfTimeModel(models=models, weights=weights, report=report)
