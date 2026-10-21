"""Training orchestration with nested, chronological evaluation.

Level 1 (expanding window by season): every goal model and the direct
market classifiers are fitted on seasons < s and predict season s, giving
out-of-fold (OOF) predictions for every test season.

Level 2 (honest evaluation of the optimisation layer): for each later
season s, ensemble weights and per-market stackers are fitted on the OOF
predictions of earlier test seasons only, then applied to season s. So
every reported number is out-of-sample at both levels.

Three pipelines are compared on the same matches:
    raw       score matrix as the model outputs it
    baseline  the v1 approach: multinomial 1X2 calibration, matrix rescaled
              to match 1X2 only (O/U, BTTS, team totals left uncalibrated)
    final     4-market pipeline: per-market calibration of the backbone,
              stacked with the direct market classifiers only in markets
              where that wins out of sample, then the score matrix is
              reconciled to all markets at once (IPF)

The candidate (single model or ensemble) with the best final combined
4-market skill is selected for production.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from footypred.logging_utils import get_logger
from footypred.models.goal_models import make_model
from footypred.models.market_head import (DirectMarkets, MarketHead, MarketStacker,
                                          mix_probs, probs_from_grids, reconcile)
from footypred.models.metrics import (base_logloss, binary_logloss, combined_loss, evaluate,
                                      multi_logloss, outcomes)
from footypred.models.scorematrix import masks

log = get_logger("models.trainer")


def usable_features(frame: pd.DataFrame, fcols: list[str], max_missing=0.97) -> list[str]:
    keep = []
    for c in fcols:
        col = frame[c]
        if col.isna().mean() > max_missing or col.nunique(dropna=True) <= 1:
            continue
        keep.append(c)
    return keep


def fit_ensemble_weights(per_model: list[dict], y_h, y_a) -> np.ndarray:
    """Simplex weights minimising the combined 4-market log loss of the
    *mixture* of score matrices (softmax parameterisation)."""
    out = outcomes(y_h, y_a)
    base = base_logloss(out)
    k = len(per_model)

    def loss(z):
        w = np.exp(z - z.max()); w /= w.sum()
        return combined_loss(mix_probs(per_model, w), out, base)

    res = minimize(loss, np.zeros(k), method="Nelder-Mead" if k <= 2 else "Powell",
                   options={"maxiter": 4000, "xtol": 1e-4, "ftol": 1e-7})
    w = np.exp(res.x - res.x.max()); w /= w.sum()
    w[w < 0.01] = 0
    return w / w.sum()


def _rescale_1x2(grids, p1x2):
    """v1-style baseline: rescale the H/D/A regions of each matrix to match
    calibrated 1X2 probabilities; other markets are left as they fall."""
    m = masks(grids.shape[-1])
    g = grids.copy()
    for c, key in enumerate(("home", "draw", "away")):
        cur = (g * m[key]).sum(axis=(1, 2))
        g = np.where(m[key][None], g * (p1x2[:, c] / np.maximum(cur, 1e-15))[:, None, None], g)
    return g / g.sum(axis=(1, 2), keepdims=True)


def _market_ll(p, y) -> float:
    return multi_logloss(p, y) if p.ndim == 2 else binary_logloss(p, y)


def bookmaker_probs(frame: pd.DataFrame) -> dict | None:
    cols = ["odds_h", "odds_d", "odds_a", "odds_o25", "odds_u25"]
    if any(c not in frame for c in cols) or frame[cols].isna().any(axis=1).mean() > 0.2:
        return None
    o = frame[cols].astype(float)
    inv = 1 / o[["odds_h", "odds_d", "odds_a"]].values
    p1 = inv / inv.sum(axis=1, keepdims=True)
    io, iu = 1 / o["odds_o25"].values, 1 / o["odds_u25"].values
    return {"1x2": p1, "o25": io / (io + iu), "mask": ~np.isnan(p1).any(axis=1)}


@dataclass
class TrainResult:
    models: dict
    direct: DirectMarkets
    weights: dict
    head: MarketHead
    selected: str
    feature_cols: list
    report: dict
    importances: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    feature_params: dict = field(default_factory=dict)
    eval_preds: dict = field(default_factory=dict)


class Trainer:
    def __init__(self, cfg):
        self.cfg = cfg
        t = cfg.training
        self.model_names = list(t.get("models"))
        self.min_train = int(t.get("cv_min_train_seasons", 2))
        self.rs = int(t.get("random_state", 42))
        self.G = int(t.get("max_goals", 10)) + 1
        self.hl_grid = list(t.get("dc_half_life_grid") or [t.get("dc_half_life_days", 240)])
        self.dc_half_life = float(t.get("dc_half_life_days", 240))

    def _make(self, name):
        kw = {"random_state": self.rs}
        if name == "dixon_coles":
            kw["half_life_days"] = self.dc_half_life
        if name == "bayesian":
            kw["half_life_days"] = self.dc_half_life * 1.5
        return make_model(name, **kw)

    # ------------------------------------------------------------- folds
    def _folds(self, frame):
        seasons = sorted(frame["season"].unique())
        tests = [s for s in seasons[self.min_train:] if (frame["season"] == s).sum() >= 40]
        if len(tests) < 2:
            raise ValueError("need at least min_train + 2 seasons of data for nested CV")
        return tests

    def _tune_dc(self, frame, fcols, s):
        tr, te = frame[frame["season"] < s], frame[frame["season"] == s]
        best, best_hl = -np.inf, self.dc_half_life
        for hl in self.hl_grid:
            m = make_model("dixon_coles", half_life_days=hl)
            r = evaluate(probs_from_grids(m.oof_grids(tr, te, fcols, self.G)),
                         te["y_h"].values, te["y_a"].values)
            log.info("  DC half-life %4d days: combined skill %.4f", hl, r["combined_skill"])
            if r["combined_skill"] > best:
                best, best_hl = r["combined_skill"], hl
        self.dc_half_life = float(best_hl)

    # ------------------------------------------------------------- train
    def train(self, frame: pd.DataFrame, fcols: list[str]) -> TrainResult:
        t0 = time.time()
        frame = frame.sort_values(["date", "match_id"]).reset_index(drop=True)
        fcols = usable_features(frame, fcols)
        tests = self._folds(frame)
        log.info("training on %d matches, %d features; test seasons %s",
                 len(frame), len(fcols), tests)
        if "dixon_coles" in self.model_names and len(self.hl_grid) > 1:
            self._tune_dc(frame, fcols, tests[0])

        # ---------------- level 1: OOF predictions
        oof_idx, oof_grids, oof_direct = [], {m: [] for m in self.model_names}, []
        for s in tests:
            tr, te = frame[frame["season"] < s], frame[frame["season"] == s]
            log.info("fold %s: train %d, test %d", s, len(tr), len(te))
            for name in self.model_names:
                t = time.time()
                oof_grids[name].append(self._make(name).oof_grids(tr, te, fcols, self.G))
                log.debug("  %s %.1fs", name, time.time() - t)
            oof_direct.append(DirectMarkets(self.rs).fit(tr, fcols).predict(te, fcols))
            oof_idx.append(te.index.values)
        idx = np.concatenate(oof_idx)
        fold_of = np.concatenate([np.full(len(i), s) for i, s in zip(oof_idx, tests)])
        grids = {m: np.concatenate(v) for m, v in oof_grids.items()}
        probs = {m: probs_from_grids(g) for m, g in grids.items()}
        direct = {kind: {k: np.concatenate([d[kind][k] for d in oof_direct])
                         for k in oof_direct[0][kind]} for kind in ("gbm", "lin")}
        yh, ya = frame.loc[idx, "y_h"].values, frame.loc[idx, "y_a"].values
        self.oof = {"idx": idx, "fold_of": fold_of, "tests": tests, "grids": grids,
                    "direct": direct, "y_h": yh, "y_a": ya}

        # ---------------- level 2: honest evaluation of the optimisation layer
        cands = self.model_names + ["ensemble"]
        use_direct = bool(self.cfg.training.get("direct_markets", True))
        ev = {c: {"raw": [], "baseline": [], "cal": [], "stk": [], "grid": []} for c in cands}
        direct_raw, weights_hist = [], []
        ev_mask = fold_of != tests[0]
        sel = lambda p, m: {k: v[m] for k, v in p.items()}
        for s in tests[1:]:
            trm, tem = fold_of < s, fold_of == s
            per_tr = [sel(probs[m], trm) for m in self.model_names]
            w = fit_ensemble_weights(per_tr, yh[trm], ya[trm])
            weights_hist.append(w)
            cand_tr = {**dict(zip(self.model_names, per_tr)), "ensemble": mix_probs(per_tr, w)}
            cand_grid = {**{m: grids[m][tem] for m in self.model_names},
                         "ensemble": sum(wi * grids[m][tem] for wi, m in zip(w, self.model_names))}
            d_tr = {kind: sel(direct[kind], trm) for kind in direct}
            d_te = {kind: sel(direct[kind], tem) for kind in direct}
            direct_raw.append(d_te["gbm"])
            for c in cands:
                g_te = cand_grid[c]
                p_te = probs_from_grids(g_te)
                cal = MarketStacker().fit([cand_tr[c]], yh[trm], ya[trm])
                t_cal = cal.predict([p_te])
                ev[c]["grid"].append(g_te)
                ev[c]["raw"].append(p_te)
                ev[c]["baseline"].append(probs_from_grids(_rescale_1x2(g_te, t_cal["1x2"])))
                ev[c]["cal"].append(t_cal)
                if use_direct:
                    stk = MarketStacker().fit([cand_tr[c], d_tr["gbm"], d_tr["lin"]],
                                              yh[trm], ya[trm])
                    ev[c]["stk"].append(stk.predict([p_te, d_te["gbm"], d_te["lin"]]))

        cat = lambda lst: {k: np.concatenate([d[k] for d in lst]) for k in lst[0]}
        yh_ev, ya_ev = yh[ev_mask], ya[ev_mask]
        out_ev = outcomes(yh_ev, ya_ev)
        report = {"candidates": {}, "eval_matches": int(ev_mask.sum()),
                  "eval_seasons": [int(s) for s in tests[1:]],
                  "dc_half_life_days": self.dc_half_life, "heads": {}}
        finals, final_probs, raw_probs = {}, {}, {}
        for c in cands:
            raw, cal_t = cat(ev[c]["raw"]), cat(ev[c]["cal"])
            choice = {k: "cal" for k in cal_t}
            if use_direct:
                stk_t = cat(ev[c]["stk"])
                for k in choice:
                    if _market_ll(stk_t[k], out_ev[k]) < _market_ll(cal_t[k], out_ev[k]):
                        choice[k] = "stk"
            # reconcile each eval fold's grids to its chosen per-market targets
            fin = []
            for f in range(len(ev[c]["grid"])):
                tgt = {k: (ev[c]["stk"][f] if choice[k] == "stk" else ev[c]["cal"][f])[k]
                       for k in choice}
                fin.append(probs_from_grids(reconcile(ev[c]["grid"][f], tgt)))
            fin = cat(fin)
            report["candidates"][c] = {"raw": evaluate(raw, yh_ev, ya_ev),
                                       "baseline": evaluate(cat(ev[c]["baseline"]), yh_ev, ya_ev),
                                       "final": evaluate(fin, yh_ev, ya_ev)}
            report["heads"][c] = choice
            finals[c] = report["candidates"][c]["final"]["combined_skill"]
            final_probs[c], raw_probs[c] = fin, raw
        report["candidates"]["direct_gbm"] = {"raw": evaluate(cat(direct_raw), yh_ev, ya_ev)}
        selected = max(finals, key=finals.get)
        report["selected"] = selected
        report["weights_by_fold"] = [dict(zip(self.model_names, map(float, w)))
                                     for w in weights_hist]
        book = bookmaker_probs(frame.loc[idx[ev_mask]])
        if book is not None:
            m = book["mask"]
            fp = final_probs[selected]
            report["bookmaker"] = {
                "1x2_logloss": multi_logloss(book["1x2"][m], out_ev["1x2"][m]),
                "o25_logloss": binary_logloss(book["o25"][m], out_ev["o25"][m]),
                "model_1x2_logloss": multi_logloss(fp["1x2"][m], out_ev["1x2"][m]),
                "model_o25_logloss": binary_logloss(fp["o25"][m], out_ev["o25"][m]),
            }
        log.info("selected: %s (final combined skill %.4f; heads %s)", selected,
                 finals[selected], report["heads"][selected])

        # ---------------- production fit on everything
        log.info("final fit on all %d matches", len(frame))
        models = {m: self._make(m).fit(frame, fcols) for m in self.model_names}
        w_all = fit_ensemble_weights([probs[m] for m in self.model_names], yh, ya)
        weights = dict(zip(self.model_names, map(float, w_all)))
        src = (mix_probs([probs[m] for m in self.model_names], w_all)
               if selected == "ensemble" else probs[selected])
        head = MarketHead(report["heads"][selected]).fit(src, direct, yh, ya)
        dm = DirectMarkets(self.rs).fit(frame, fcols)
        importances = self._importances(dm, models, fcols)
        report["train_seconds"] = round(time.time() - t0, 1)
        report["n_matches"] = len(frame)
        report["n_features"] = len(fcols)
        report["ensemble_weights"] = weights
        eval_preds = {"final": final_probs[selected], "raw": raw_probs[selected],
                      "y_h": yh_ev, "y_a": ya_ev,
                      "match_id": frame.loc[idx[ev_mask], "match_id"].to_numpy()}
        return TrainResult(models=models, direct=dm, weights=weights, head=head,
                           selected=selected, feature_cols=fcols, report=report,
                           importances=importances, config=dict(self.cfg.training),
                           eval_preds=eval_preds)

    @staticmethod
    def _importances(dm: DirectMarkets, models: dict, fcols) -> dict:
        """Normalised gain importance per market (direct GBMs) + goal model."""
        res = {}
        for k, m in dm.gbm.items():
            g = m.booster_.feature_importance("gain")
            res[k] = dict(zip(fcols, (g / max(g.sum(), 1e-9)).tolist()))
        if "lightgbm" in models:
            g = sum(models["lightgbm"].models[t].booster_.feature_importance("gain")
                    for t in ("y_h", "y_a"))
            res["goals"] = dict(zip(fcols, (g / max(g.sum(), 1e-9)).tolist()))
        return res
