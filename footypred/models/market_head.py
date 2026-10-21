"""The 4-market optimisation layer.

1. DirectMarkets — classifiers trained straight on each market outcome
   (1X2, O2.5, BTTS, home/away over 0.5/1.5/2.5) from the past-match
   features. They capture what a Poisson structure cannot (game management,
   tempo volatility, over-dispersion). Two learners per market: gradient
   boosting and an L2 logistic regression.

2. MarketStacker — per market, a logistic stack on out-of-fold logits of
   [score-matrix probability, direct GBM, direct logistic]. This is both
   the blend and the calibration (fitted only on out-of-fold predictions).

3. reconcile() — iterative proportional fitting of the score matrix to the
   stacked market probabilities: the minimum-KL adjustment of the joint
   score distribution that agrees with all four markets at once. Reported
   probabilities are read back off the reconciled matrix, so they are
   always mutually coherent (e.g. BTTS <= P(home scores), O2.5 consistent
   with both team totals), and the scoreline grid matches the markets.
"""

from __future__ import annotations

import warnings

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from footypred.logging_utils import get_logger
from footypred.models.metrics import outcomes
from footypred.models.scorematrix import BINARY_MARKETS, EXTRA_MARKETS, market_probs, masks

log = get_logger("models.market_head")

EPS = 1e-6


def _logit(p):
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))


def probs_from_grids(grids) -> dict[str, np.ndarray]:
    p = market_probs(grids)
    out = {"1x2": np.column_stack([p["home"], p["draw"], p["away"]])}
    out.update({k: p[k] for k in BINARY_MARKETS + EXTRA_MARKETS})
    return out


def mix_probs(per_model: list[dict], weights) -> dict[str, np.ndarray]:
    """Market probabilities of a mixture of score matrices are the same
    mixture of the per-model market probabilities (linearity)."""
    out = {}
    for k in per_model[0]:
        out[k] = sum(w * pm[k] for w, pm in zip(weights, per_model))
    return out


# ======================================================================
class DirectMarkets:
    """Per-market classifiers on the feature set."""

    def __init__(self, random_state: int = 42):
        self.rs = random_state
        self.gbm: dict = {}
        self.lin: dict = {}

    def _gbm(self, n, multiclass=False):
        from lightgbm import LGBMClassifier
        return LGBMClassifier(
            objective="multiclass" if multiclass else "binary", n_estimators=n,
            learning_rate=0.03, num_leaves=7, min_child_samples=80, subsample=0.8,
            subsample_freq=1, colsample_bytree=0.5, reg_lambda=10.0, n_jobs=4,
            verbose=-1, random_state=self.rs)

    def fit(self, frame, fcols):
        import lightgbm as lgb
        X = frame[fcols].values.astype(np.float32)
        out = outcomes(frame["y_h"].values, frame["y_a"].values)
        n = len(frame)
        cut = int(n * 0.85)
        for k in ["1x2"] + BINARY_MARKETS:
            y = out[k]
            multi = k == "1x2"
            es = self._gbm(1500, multi)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                es.fit(X[:cut], y[:cut], eval_set=[(X[cut:], y[cut:])],
                       callbacks=[lgb.early_stopping(80, verbose=False)])
                best = max(40, int((es.best_iteration_ or 200) * 1.1))
                self.gbm[k] = self._gbm(best, multi).fit(X, y)
                lin = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                                    LogisticRegression(C=0.02, max_iter=2000))
                self.lin[k] = lin.fit(X, y)
        return self

    def predict(self, frame, fcols) -> dict[str, dict[str, np.ndarray]]:
        X = frame[fcols].values.astype(np.float32)
        res = {"gbm": {}, "lin": {}}
        for k in self.gbm:
            for kind, models in (("gbm", self.gbm), ("lin", self.lin)):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    p = models[k].predict_proba(X)
                res[kind][k] = p if k == "1x2" else p[:, 1]
        return res


# ======================================================================
class MarketStacker:
    """Per-market logistic stacking/calibration over probability sources."""

    def __init__(self, C: float = 1.0):
        self.C = C
        self.models: dict = {}

    @staticmethod
    def _design(sources: list[dict], k: str) -> np.ndarray:
        if k == "1x2":
            cols = []
            for s in sources:
                P = np.clip(s["1x2"], EPS, 1)
                cols += [np.log(P[:, 0] / P[:, 1]), np.log(P[:, 2] / P[:, 1])]
            return np.column_stack(cols)
        return np.column_stack([_logit(s[k]) for s in sources])

    def fit(self, sources: list[dict], y_h, y_a) -> "MarketStacker":
        out = outcomes(y_h, y_a)
        for k in ["1x2"] + BINARY_MARKETS:
            X = self._design(sources, k)
            m = LogisticRegression(C=self.C, max_iter=1000)
            m.fit(X, out[k])
            self.models[k] = m
        return self

    def predict(self, sources: list[dict]) -> dict[str, np.ndarray]:
        res = {}
        for k, m in self.models.items():
            p = m.predict_proba(self._design(sources, k))
            res[k] = p if k == "1x2" else p[:, 1]
        return res


# ======================================================================
def _partitions(G: int):
    m = masks(G)
    i, j = np.indices((G, G))
    hg = [i == 0, i == 1, i == 2, i >= 3]
    ag = [j == 0, j == 1, j == 2, j >= 3]
    return {
        "1x2": [m["home"], m["draw"], m["away"]],
        "o25": [m["o25"], ~m["o25"]],
        "btts": [m["btts"], ~m["btts"]],
        "home_goals": hg,
        "away_goals": ag,
    }


def _team_targets(p05, p15, p25):
    """Team-total over probabilities -> P(0), P(1), P(2), P(3+), monotone."""
    p05 = np.clip(p05, EPS, 1 - EPS)
    p15 = np.minimum(np.clip(p15, EPS, 1 - EPS), p05 - EPS)
    p25 = np.minimum(np.clip(p25, EPS, 1 - EPS), p15 - EPS)
    t = np.column_stack([1 - p05, p05 - p15, p15 - p25, p25])
    t = np.clip(t, EPS, 1)
    return t / t.sum(axis=1, keepdims=True)


def reconcile(grids: np.ndarray, target: dict[str, np.ndarray], iters: int = 60,
              tol: float = 1e-7) -> np.ndarray:
    """Iterative proportional fitting: rescale cell groups of each grid
    until every market's probabilities match `target` (I-projection)."""
    g = np.array(grids, dtype=float, copy=True)
    n, G, _ = g.shape
    parts = _partitions(G)
    tgt = {
        "1x2": np.clip(target["1x2"], EPS, 1),
        "o25": np.column_stack([target["o25"], 1 - target["o25"]]),
        "btts": np.column_stack([target["btts"], 1 - target["btts"]]),
        "home_goals": _team_targets(target["h_o05"], target["h_o15"], target["h_o25"]),
        "away_goals": _team_targets(target["a_o05"], target["a_o15"], target["a_o25"]),
    }
    tgt["1x2"] = tgt["1x2"] / tgt["1x2"].sum(axis=1, keepdims=True)
    g = np.maximum(g, 1e-12)
    for _ in range(iters):
        worst = 0.0
        for name, cells in parts.items():
            t = tgt[name]
            for c, mask in enumerate(cells):
                cur = (g * mask).sum(axis=(1, 2))
                worst = max(worst, float(np.max(np.abs(cur - t[:, c]))))
                ratio = t[:, c] / np.maximum(cur, 1e-15)
                g = np.where(mask[None], g * ratio[:, None, None], g)
            g /= g.sum(axis=(1, 2), keepdims=True)
        if worst < tol:
            break
    return g


# ======================================================================
class MarketHead:
    """Per-market choice between two heads, decided out of sample:
        'cal' — calibrate the backbone's own probability (logistic on its logit)
        'stk' — stack the backbone with the direct classifiers
    The direct classifiers only enter markets where they earned it."""

    def __init__(self, choice: dict[str, str]):
        self.choice = choice
        self.cal: MarketStacker | None = None
        self.stk: MarketStacker | None = None

    @property
    def needs_direct(self) -> bool:
        return any(v == "stk" for v in self.choice.values())

    def fit(self, backbone: dict, direct: dict | None, y_h, y_a) -> "MarketHead":
        self.cal = MarketStacker().fit([backbone], y_h, y_a)
        if self.needs_direct:
            self.stk = MarketStacker().fit([backbone, direct["gbm"], direct["lin"]], y_h, y_a)
        return self

    def predict(self, backbone: dict, direct: dict | None) -> dict[str, np.ndarray]:
        t_cal = self.cal.predict([backbone])
        if not self.needs_direct:
            return t_cal
        t_stk = self.stk.predict([backbone, direct["gbm"], direct["lin"]])
        return {k: (t_stk if self.choice.get(k) == "stk" else t_cal)[k] for k in t_cal}
