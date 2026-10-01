"""Goal-rate model zoo. Every model maps a fixture to expected goals
(λ_home, λ_away) and from there to a Dixon-Coles score matrix.

Team-based (identity) models:   poisson-free Dixon-Coles, hierarchical
                                Bayesian (empirical-Bayes MAP)
Feature-based models:           Poisson GLM, XGBoost, LightGBM, CatBoost
                                (Poisson objectives), random forest, MLP
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from scipy.optimize import minimize, minimize_scalar
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import PoissonRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from footypred.logging_utils import get_logger
from footypred.models.scorematrix import dc_tau, poisson_grids

log = get_logger("models.goal")

DEFAULT_RHO = -0.06


def fit_rho(lh, la, gh, ga, w=None) -> float:
    """MLE of the Dixon-Coles dependence parameter given fitted rates."""
    w = np.ones_like(lh) if w is None else w
    low = (gh <= 1) & (ga <= 1)
    lh, la, gh, ga, w = lh[low], la[low], gh[low], ga[low], w[low]

    def nll(rho):
        t00, t01, t10, t11 = dc_tau(lh, la, rho)
        tau = np.select([(gh == 0) & (ga == 0), (gh == 0) & (ga == 1),
                         (gh == 1) & (ga == 0)], [t00, t01, t10], t11)
        return -np.sum(w * np.log(np.maximum(tau, 1e-9)))

    return float(minimize_scalar(nll, bounds=(-0.25, 0.1), method="bounded").x)


class GoalModel:
    name = "base"
    team_based = False

    def __init__(self, **kw):
        self.kw = kw
        self.rho = DEFAULT_RHO

    def fit(self, frame: pd.DataFrame, fcols: list[str]) -> "GoalModel":
        raise NotImplementedError

    def predict_rates(self, frame: pd.DataFrame, fcols: list[str]):
        raise NotImplementedError

    def predict_grids(self, frame, fcols, G: int = 11) -> np.ndarray:
        lh, la = self.predict_rates(frame, fcols)
        return poisson_grids(np.clip(lh, 0.05, 6), np.clip(la, 0.05, 6), self.rho, G)

    def oof_grids(self, train, test, fcols, G: int = 11) -> np.ndarray:
        self.fit(train, fcols)
        return self.predict_grids(test, fcols, G)

    def _fit_rho(self, frame, fcols):
        lh, la = self.predict_rates(frame, fcols)
        self.rho = fit_rho(lh, la, frame["y_h"].values, frame["y_a"].values)


# ======================================================================
# team-based models
# ======================================================================
class DixonColes(GoalModel):
    """Time-decayed Dixon-Coles with per-league base rate & home advantage.
    Poisson part fitted by L-BFGS with analytic gradients, then ρ by MLE."""

    name = "dixon_coles"
    team_based = True

    def __init__(self, half_life_days: float = 240, ridge: float = 1e-3, **kw):
        super().__init__(**kw)
        self.half_life = half_life_days
        self.ridge = ridge
        self.params = None

    # ---- design
    def _index(self, frame):
        teams = pd.Index(sorted(set(frame["home"]) | set(frame["away"])))
        leagues = pd.Index(sorted(set(frame["league"])))
        return teams, leagues

    def _weights(self, dates, ref):
        age = (ref - dates).dt.days.values.astype(float)
        return 0.5 ** (age / self.half_life)

    def _ridge(self, T):
        return self.ridge

    def fit(self, frame, fcols=None, ref_date=None, warm=None):
        teams, leagues = self._index(frame)
        T, L = len(teams), len(leagues)
        hi = teams.get_indexer(frame["home"]); ai = teams.get_indexer(frame["away"])
        li = leagues.get_indexer(frame["league"])
        nz = 1.0 - frame["neutral"].fillna(0).values.astype(float)
        gh = frame["y_h"].values.astype(float); ga = frame["y_a"].values.astype(float)
        ref = pd.Timestamp(ref_date) if ref_date is not None else frame["date"].max()
        w = self._weights(frame["date"], ref)

        x0 = np.zeros(2 * T + 2 * L)
        x0[2 * T:2 * T + L] = np.log(1.35)
        x0[2 * T + L:] = 0.2
        if warm is not None:  # warm start from a previous fit
            pt, pl = warm
            for i, t in enumerate(teams):
                if t in pt:
                    x0[i], x0[T + i] = pt[t]
            for j, lg in enumerate(leagues):
                if lg in pl:
                    x0[2 * T + j], x0[2 * T + L + j] = pl[lg]
        lam = self._ridge(T)

        def f(x):
            att, dfn = x[:T], x[T:2 * T]
            mu, hadv = x[2 * T:2 * T + L], x[2 * T + L:]
            eh = mu[li] + hadv[li] * nz + att[hi] - dfn[ai]
            ea = mu[li] + att[ai] - dfn[hi]
            lh, la = np.exp(eh), np.exp(ea)
            nll = -np.sum(w * (gh * eh - lh + ga * ea - la)) + lam * (att @ att + dfn @ dfn)
            rh, ra = w * (gh - lh), w * (ga - la)
            g = np.zeros_like(x)
            g[:T] = -(np.bincount(hi, rh, T) + np.bincount(ai, ra, T)) + 2 * lam * att
            g[T:2 * T] = (np.bincount(ai, rh, T) + np.bincount(hi, ra, T)) + 2 * lam * dfn
            g[2 * T:2 * T + L] = -np.bincount(li, rh + ra, L)
            g[2 * T + L:] = -np.bincount(li, rh * nz, L)
            return nll, g

        res = minimize(f, x0, jac=True, method="L-BFGS-B", options={"maxiter": 500})
        x = res.x
        self.params = (
            {t: (x[i], x[T + i]) for i, t in enumerate(teams)},
            {lg: (x[2 * T + j], x[2 * T + L + j]) for j, lg in enumerate(leagues)},
        )
        self._post_fit(x[:T], x[T:2 * T])
        lh, la = self.predict_rates(frame)
        self.rho = fit_rho(lh, la, gh.astype(int), ga.astype(int), w)
        return self

    def _post_fit(self, att, dfn):
        pass

    def predict_rates(self, frame, fcols=None):
        pt, pl = self.params
        mean_mu = np.mean([v[0] for v in pl.values()])
        mean_h = np.mean([v[1] for v in pl.values()])
        lh, la = [], []
        for h, a, lg, n in zip(frame["home"], frame["away"], frame["league"],
                               frame["neutral"].fillna(0)):
            ah, dh = pt.get(h, (0.0, 0.0))
            aa, da = pt.get(a, (0.0, 0.0))
            mu, hadv = pl.get(lg, (mean_mu, mean_h))
            hadv = 0.0 if n else hadv
            lh.append(np.exp(mu + hadv + ah - da))
            la.append(np.exp(mu + aa - dh))
        return np.array(lh), np.array(la)

    def oof_grids(self, train, test, fcols, G: int = 11) -> np.ndarray:
        """Walk-forward: refit at each month start on everything before it."""
        out = np.zeros((len(test), G, G))
        allm = pd.concat([train, test], ignore_index=True)
        months = test["date"].dt.to_period("M")
        warm = None
        for per in months.unique():
            start = per.to_timestamp()
            hist = allm[allm["date"] < start]
            self.fit(hist, ref_date=start, warm=warm)
            warm = self.params
            idx = np.where(months.values == per)[0]
            out[idx] = self.predict_grids(test.iloc[idx], fcols, G)
        return out


class HierarchicalBayes(DixonColes):
    """Partial pooling: att, def ~ N(0, σ²) within each league's level, σ²
    estimated by empirical Bayes (iterated MAP). Shrinks small-sample teams
    hard, trusts long histories."""

    name = "bayesian"

    def __init__(self, half_life_days: float = 360, sigma2: float = 0.05, **kw):
        super().__init__(half_life_days=half_life_days, **kw)
        self.sigma2 = sigma2
        self._eb_rounds = 0

    def _ridge(self, T):
        return 1.0 / (2 * self.sigma2)

    def _post_fit(self, att, dfn):
        # empirical-Bayes update of the prior variance (bounded for stability)
        s2 = float(np.mean(np.concatenate([att, dfn]) ** 2)) * 1.3
        self.sigma2 = float(np.clip(s2, 0.01, 0.2))

    def fit(self, frame, fcols=None, ref_date=None, warm=None):
        rounds = 3 if self._eb_rounds == 0 else 1
        for _ in range(rounds):
            super().fit(frame, fcols, ref_date, warm)
            warm = self.params
        self._eb_rounds += 1
        return self


# ======================================================================
# feature-based models
# ======================================================================
def _chrono_split(frame, frac=0.15):
    n = len(frame)
    cut = int(n * (1 - frac))
    return np.arange(cut), np.arange(cut, n)


class PoissonGLM(GoalModel):
    name = "poisson"

    def fit(self, frame, fcols):
        self.models = {}
        for tgt in ("y_h", "y_a"):
            m = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                              PoissonRegressor(alpha=self.kw.get("alpha", 0.02), max_iter=600))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                m.fit(frame[fcols].values, frame[tgt].values)
            self.models[tgt] = m
        self._fit_rho(frame, fcols)
        return self

    def predict_rates(self, frame, fcols):
        X = frame[fcols].values
        return self.models["y_h"].predict(X), self.models["y_a"].predict(X)


class _GBMBase(GoalModel):
    """Fit with early stopping on the latest 15% of the training window,
    then refit on the full window with the found number of rounds."""

    def _make(self, n_estimators):
        raise NotImplementedError

    def _fit_es(self, X, y, Xv, yv):
        raise NotImplementedError

    def fit(self, frame, fcols):
        self.models = {}
        tr, va = _chrono_split(frame)
        X = frame[fcols].values.astype(np.float32)
        for tgt in ("y_h", "y_a"):
            y = frame[tgt].values
            best = self._fit_es(X[tr], y[tr], X[va], y[va])
            n = max(50, int(best * 1.1))
            m = self._make(n)
            m.fit(X, y)
            self.models[tgt] = m
        self._fit_rho(frame, fcols)
        return self

    def predict_rates(self, frame, fcols):
        X = frame[fcols].values.astype(np.float32)
        return self.models["y_h"].predict(X), self.models["y_a"].predict(X)


class XGBoostGoals(_GBMBase):
    name = "xgboost"

    def _make(self, n, es=False):
        from xgboost import XGBRegressor
        return XGBRegressor(objective="count:poisson", n_estimators=n, learning_rate=0.03,
                            max_depth=3, subsample=0.8, colsample_bytree=0.5,
                            min_child_weight=30, reg_lambda=5.0, n_jobs=4,
                            random_state=self.kw.get("random_state", 42),
                            early_stopping_rounds=80 if es else None,
                            eval_metric="poisson-nloglik")

    def _fit_es(self, X, y, Xv, yv):
        m = self._make(1500, es=True)
        m.fit(X, y, eval_set=[(Xv, yv)], verbose=False)
        return m.best_iteration + 1


class LightGBMGoals(_GBMBase):
    name = "lightgbm"

    def _make(self, n):
        from lightgbm import LGBMRegressor
        return LGBMRegressor(objective="poisson", n_estimators=n, learning_rate=0.03,
                             num_leaves=12, min_child_samples=60, subsample=0.8,
                             subsample_freq=1, colsample_bytree=0.5, reg_lambda=5.0,
                             n_jobs=4, verbose=-1,
                             random_state=self.kw.get("random_state", 42))

    def _fit_es(self, X, y, Xv, yv):
        import lightgbm as lgb
        m = self._make(1500)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m.fit(X, y, eval_set=[(Xv, yv)],
                  callbacks=[lgb.early_stopping(80, verbose=False)])
        return m.best_iteration_ or 300


class CatBoostGoals(_GBMBase):
    name = "catboost"

    def _make(self, n):
        from catboost import CatBoostRegressor
        return CatBoostRegressor(loss_function="Poisson", iterations=n, learning_rate=0.05,
                                 depth=4, l2_leaf_reg=8, rsm=0.5, verbose=0, thread_count=4,
                                 random_seed=self.kw.get("random_state", 42))

    def _fit_es(self, X, y, Xv, yv):
        m = self._make(1500)
        m.fit(X, y, eval_set=(Xv, yv), early_stopping_rounds=80, verbose=False)
        return m.get_best_iteration() + 1



class RandomForestGoals(GoalModel):
    name = "random_forest"

    def fit(self, frame, fcols):
        self.imp = SimpleImputer(strategy="median").fit(frame[fcols].values)
        X = self.imp.transform(frame[fcols].values)
        self.model = RandomForestRegressor(
            n_estimators=250, min_samples_leaf=60, max_features=0.3, n_jobs=4,
            random_state=self.kw.get("random_state", 42))
        self.model.fit(X, frame[["y_h", "y_a"]].values)
        self.rho = DEFAULT_RHO  # in-sample forest rates are too sharp to fit ρ on
        return self

    def predict_rates(self, frame, fcols):
        p = self.model.predict(self.imp.transform(frame[fcols].values))
        return p[:, 0], p[:, 1]


class NeuralNetGoals(GoalModel):
    """MLP on standardized features predicting both teams' goals jointly."""

    name = "neural_net"

    def fit(self, frame, fcols):
        self.pipe = make_pipeline(SimpleImputer(strategy="median"), StandardScaler())
        X = np.clip(self.pipe.fit_transform(frame[fcols].values), -5, 5)
        self.model = MLPRegressor(hidden_layer_sizes=(48, 16), alpha=0.05,
                                  learning_rate_init=1e-3, max_iter=300, early_stopping=True,
                                  validation_fraction=0.15, n_iter_no_change=15,
                                  random_state=self.kw.get("random_state", 42))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.model.fit(X, frame[["y_h", "y_a"]].values)
        self._fit_rho(frame, fcols)
        return self

    def predict_rates(self, frame, fcols):
        X = np.clip(self.pipe.transform(frame[fcols].values), -5, 5)
        p = self.model.predict(X)
        return np.clip(p[:, 0], 0.1, 6), np.clip(p[:, 1], 0.1, 6)


REGISTRY = {
    "poisson": PoissonGLM, "dixon_coles": DixonColes, "bayesian": HierarchicalBayes,
    "xgboost": XGBoostGoals, "lightgbm": LightGBMGoals, "catboost": CatBoostGoals,
    "random_forest": RandomForestGoals, "neural_net": NeuralNetGoals,
}


def make_model(name: str, **kw) -> GoalModel:
    return REGISTRY[name](**kw)
