"""Walk-forward backtest over a date range ("as-of" testing).

The system is rebuilt as it stood on the start date: ratings tuned and
models trained on matches *before* it only. Then it steps through the range
one day at a time. Each day's matches are predicted from what was known
that morning, scored against the real results, and only then are those
results fed in (exactly what the live system does when new results arrive).
With `retrain_every` the models are also retrained on everything before
the day, every N days.

    footy backtest --from 2025-08-01 --to 2026-05-31 [--retrain-every 30]

Reported: per-market log loss / accuracy / calibration (vs the bookmaker
where the file has odds), how often each pick style's best pick landed,
and flat-stake profit at the bookmaker's odds for picks and value bets.
"""

from __future__ import annotations

import dataclasses
import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from footypred.logging_utils import get_logger
from footypred.models.market_head import probs_from_grids
from footypred.models.metrics import binary_logloss, evaluate, multi_logloss, outcomes
from footypred.predict.picks import FormIndex, backtest, base_rates

log = get_logger("predict.walkforward")

QUICK_MODELS = ["poisson", "dixon_coles", "lightgbm"]
STYLES = ("safe", "balanced", "bold")
# bookmaker odds column for a pick, where the match file has them
PICK_ODDS = {"home_win": "odds_h", "draw": "odds_d", "away_win": "odds_a",
             "over_2.5": "odds_o25", "under_2.5": "odds_u25"}
PROB_COLS = ["p_home", "p_draw", "p_away", "p_o15", "p_o25", "p_o35", "p_btts",
             "p_h_o05", "p_h_o15", "p_h_o25", "p_a_o05", "p_a_o15", "p_a_o25"]


@dataclass
class WalkForwardResult:
    start: str
    end: str
    rows: pd.DataFrame                 # one row per predicted match
    metrics: dict                      # per market (None when too few matches)
    bookmaker: dict | None             # model vs closing odds on matches that have them
    picks: dict                        # style -> best-pick backtest summary
    betting: dict                      # flat-stake profit: picks per style, value bets
    trainings: list = field(default_factory=list)
    settings: dict = field(default_factory=dict)
    seconds: float = 0.0

    def summary(self) -> dict:
        """JSON-friendly (no per-match table)."""
        d = dataclasses.asdict(self)
        d.pop("rows")
        return d


# ------------------------------------------------------------------ training
def train_until(cfg, db, matches: pd.DataFrame, cutoff, models: list[str] | None = None,
                tune: bool = True):
    """Train the full pipeline on matches strictly before `cutoff`. Returns
    (TrainResult, feature state after the last of those matches, info)."""
    from footypred.config import Section
    from footypred.features.engineering import FeatureBuilder, feature_columns
    from footypred.features.tuning import tune_ratings
    from footypred.models.trainer import Trainer
    t0 = time.time()
    hist = matches[matches["date"] < pd.Timestamp(cutoff)]
    if hist.empty:
        raise ValueError(f"no played matches before {pd.Timestamp(cutoff).date()}")
    if models:
        cfg = dataclasses.replace(cfg, training=Section({**cfg.training, "models": list(models)}))
    params = tune_ratings(hist) if tune and cfg.features.get("auto_tune_ratings", True) else {}
    fb = FeatureBuilder(cfg, db, params)
    frame = fb.build_training_frame(hist)
    res = Trainer(cfg).train(frame, feature_columns(frame))
    res.feature_params = fb.params
    info = {"cutoff": str(pd.Timestamp(cutoff).date()), "matches": int(len(hist)),
            "first": str(hist["date"].min().date()), "model": res.selected,
            "models": list(res.models), "folds": res.report.get("fold_mode", "season"),
            "seconds": round(time.time() - t0, 1)}
    log.info("trained on %d matches before %s (%s) in %.0fs", len(hist), info["cutoff"],
             res.selected, info["seconds"])
    return res, fb.state, info


def _predict_day(res, state, games: list[dict]) -> np.ndarray:
    from footypred.predict.predictor import market_grids
    feats = []
    for r in games:
        neutral = bool(r.get("neutral") or 0)
        f = state.features(r["home"], r["away"], r["date"], r["league"], neutral, r["match_id"])
        feats.append({**f, "home": r["home"], "away": r["away"], "league": r["league"],
                      "neutral": float(neutral), "date": r["date"]})
    grids, _ = market_grids(res, pd.DataFrame(feats))
    return grids


# --------------------------------------------------------------- the walk
def walk_forward(cfg, db, start, end=None, competitions: list[str] | None = None,
                 retrain_every: int | None = None, models: list[str] | None = None,
                 pick_opts: dict | None = None, tune: bool = True, value_edge: float = 0.05,
                 progress=None, should_stop=None) -> WalkForwardResult:
    """progress(fraction 0..1, message); should_stop() -> True cancels."""
    t0 = time.time()
    say = progress or (lambda *_: None)
    allm = db.load_matches().sort_values(["date", "match_id"]).reset_index(drop=True)
    if allm.empty:
        raise ValueError("no played matches in the database")
    start = pd.Timestamp(start).normalize()
    end = pd.Timestamp(end).normalize() if end is not None else allm["date"].max()
    if end < start:
        raise ValueError("the end date is before the start date")
    if start <= allm["date"].min():
        raise ValueError(f"the start date must be after the first match on record "
                         f"({allm['date'].min().date()}): the model needs history to learn from")
    test = allm[(allm["date"] >= start) & (allm["date"] <= end)]
    comps = {c.strip() for c in competitions} if competitions else None
    scored = test if comps is None else test[test["league"].isin(comps)]
    if scored.empty:
        raise ValueError(f"no played matches between {start.date()} and {end.date()}"
                         + (f" in {', '.join(sorted(comps))}" if comps else ""))

    say(0.0, f"training on matches before {start.date()} ...")
    res, state, info = train_until(cfg, db, allm, start, models, tune)
    trainings = [info]
    last_train = start

    days = sorted(test["date"].unique())
    by_day = {d: g.to_dict("records") for d, g in test.groupby("date")}
    out_rows, out_grids = [], []
    for i, day in enumerate(days):
        if should_stop and should_stop():
            raise InterruptedError("backtest cancelled")
        day = pd.Timestamp(day)
        if retrain_every and (day - last_train).days >= retrain_every:
            say(i / len(days), f"retraining on matches before {day.date()} ...")
            res, state, info = train_until(cfg, db, allm, day, models, tune)
            trainings.append(info)
            last_train = day
        games = by_day[day]
        mine = [g for g in games if comps is None or g["league"] in comps]
        if mine:
            out_grids.append(_predict_day(res, state, mine))
            out_rows += [{**g, "model_version": len(trainings)} for g in mine]
        for g in games:                    # results go in only after the predictions
            state.update(g)
        if i % 7 == 0 or i == len(days) - 1:
            say((i + 1) / len(days), f"{day.date()}  ·  {len(out_rows)} matches predicted")

    grids = np.concatenate(out_grids)
    rows = pd.DataFrame(out_rows).reset_index(drop=True)
    probs = probs_from_grids(grids)
    return _score(cfg, allm, start, end, rows, grids, probs, trainings, pick_opts, value_edge,
                  {"competitions": sorted(comps) if comps else None,
                   "retrain_every": retrain_every, "models": trainings[0]["models"],
                   "tune": tune, "value_edge": value_edge}, t0)


# ----------------------------------------------------------------- scoring
def _score(cfg, allm, start, end, rows, grids, probs, trainings, pick_opts, value_edge,
           settings, t0) -> WalkForwardResult:
    yh, ya = rows["fthg"].to_numpy(int), rows["ftag"].to_numpy(int)
    G = grids.shape[-1]
    k = np.arange(G)
    rows["xg_home"] = np.round((grids.sum(axis=2) * k).sum(axis=1), 2)
    rows["xg_away"] = np.round((grids.sum(axis=1) * k).sum(axis=1), 2)
    for c, key in zip(PROB_COLS, [("1x2", 0), ("1x2", 1), ("1x2", 2), "o15", "o25", "o35", "btts",
                                  "h_o05", "h_o15", "h_o25", "a_o05", "a_o15", "a_o25"]):
        rows[c] = np.round(probs[key[0]][:, key[1]] if isinstance(key, tuple) else probs[key], 4)
    out = outcomes(yh, ya)
    rows["result"] = np.array(["H", "D", "A"])[out["1x2"]]
    rows["predicted"] = np.array(["H", "D", "A"])[probs["1x2"].argmax(1)]

    metrics = evaluate(probs, yh, ya) if len(rows) >= 30 and len(set(out["1x2"])) == 3 else None
    bookmaker = _vs_bookmaker(rows, probs, out)

    # best picks per style, form windows strictly before each match
    index = FormIndex(allm)
    typical = base_rates(allm[allm["date"] < start])
    base_opts = {**(cfg.raw.get("picks") or {}), **(pick_opts or {})}
    picks, betting = {}, {}
    for style in STYLES:
        r = backtest(index, rows, probs, {**base_opts, "style": style}, base=typical,
                     keep_rows=True)
        prs = r.pop("rows")
        rows[f"pick_{style}"] = [p.get("label") for p in prs]
        rows[f"pick_{style}_hit"] = [p.get("hit") for p in prs]
        rows[f"pick_{style}_fair_odds"] = [p.get("odds") for p in prs]
        rows[f"pick_{style}_book_odds"] = [
            _book(rows.iloc[i], p.get("pick")) for i, p in enumerate(prs)]
        picks[style] = r
        betting[f"picks_{style}"] = _flat_stake(rows[f"pick_{style}_book_odds"],
                                                rows[f"pick_{style}_hit"])
    betting["value_1x2"], betting["value_ou25"] = _value_bets(rows, probs, out, value_edge)
    rows["date"] = pd.to_datetime(rows["date"]).dt.strftime("%Y-%m-%d")
    return WalkForwardResult(start=str(start.date()), end=str(end.date()), rows=rows,
                             metrics=metrics, bookmaker=bookmaker, picks=picks, betting=betting,
                             trainings=trainings, settings=settings,
                             seconds=round(time.time() - t0, 1))


def _book(r, pick) -> float | None:
    col = PICK_ODDS.get(pick or "")
    v = r.get(col) if col else None
    return float(v) if v is not None and not pd.isna(v) and v > 1 else None


def _flat_stake(odds: pd.Series, hit: pd.Series) -> dict:
    """1 unit on every pick that has bookmaker odds."""
    m = odds.notna() & hit.notna()
    if not m.any():
        return {"bets": 0}
    o, h = odds[m].astype(float).to_numpy(), hit[m].astype(bool).to_numpy()
    profit = np.where(h, o - 1, -1.0)
    return {"bets": int(m.sum()), "hit_rate": float(h.mean()), "mean_odds": float(o.mean()),
            "profit": round(float(profit.sum()), 2), "roi": float(profit.mean()),
            "curve": np.round(np.cumsum(profit), 2).tolist()}


def _odds(rows, cols):
    if any(c not in rows for c in cols):
        return None
    o = rows[cols].astype(float).to_numpy(copy=True)
    o[(o <= 1) | np.isnan(o)] = np.nan
    return o


def _vs_bookmaker(rows, probs, out) -> dict | None:
    """Model vs the bookmaker's de-margined closing prices, same matches."""
    res = {}
    o = _odds(rows, ["odds_h", "odds_d", "odds_a"])
    if o is not None:
        m = ~np.isnan(o).any(axis=1)
        if m.sum() >= 30:
            inv = 1 / o[m]
            book = inv / inv.sum(axis=1, keepdims=True)
            res["1x2"] = {"matches": int(m.sum()),
                          "model_logloss": multi_logloss(probs["1x2"][m], out["1x2"][m]),
                          "book_logloss": multi_logloss(book, out["1x2"][m]),
                          "model_accuracy": float((probs["1x2"][m].argmax(1) == out["1x2"][m]).mean()),
                          "book_accuracy": float((book.argmax(1) == out["1x2"][m]).mean())}
    o = _odds(rows, ["odds_o25", "odds_u25"])
    if o is not None:
        m = ~np.isnan(o).any(axis=1)
        if m.sum() >= 30:
            io, iu = 1 / o[m, 0], 1 / o[m, 1]
            book = io / (io + iu)
            y = out["o25"][m]
            res["o25"] = {"matches": int(m.sum()),
                          "model_logloss": binary_logloss(probs["o25"][m], y),
                          "book_logloss": binary_logloss(book, y),
                          "model_accuracy": float(((probs["o25"][m] > 0.5) == y).mean()),
                          "book_accuracy": float(((book > 0.5) == y).mean())}
    return res or None


def _value_bets(rows, probs, out, edge):
    """Bet the selection whose expected value at the bookmaker's price is
    highest, when it beats `edge` (0.05 = model thinks it's 5% +EV)."""
    res = []
    for cols, P, y in ((["odds_h", "odds_d", "odds_a"], probs["1x2"], out["1x2"]),
                       (["odds_o25", "odds_u25"],
                        np.column_stack([probs["o25"], 1 - probs["o25"]]), 1 - out["o25"])):
        o = _odds(rows, cols)
        if o is None:
            res.append({"bets": 0})
            continue
        ev = P * o - 1
        ev[np.isnan(ev)] = -np.inf
        best = ev.argmax(1)
        take = ev[np.arange(len(ev)), best] > edge
        if not take.any():
            res.append({"bets": 0})
            continue
        price = o[np.arange(len(o)), best][take]
        hit = (best == y)[take]
        profit = np.where(hit, price - 1, -1.0)
        res.append({"bets": int(take.sum()), "hit_rate": float(hit.mean()),
                    "mean_odds": float(price.mean()), "profit": round(float(profit.sum()), 2),
                    "roi": float(profit.mean()), "curve": np.round(np.cumsum(profit), 2).tolist(),
                    "dates": [str(pd.Timestamp(d).date()) for d in rows["date"].to_numpy()[take]]})
    return res[0], res[1]


# ------------------------------------------------------------------ report
def render(r: WalkForwardResult) -> str:
    pct = lambda x: f"{100 * x:.1f}%"
    t = r.trainings[0]
    L = [f"Walk-forward backtest {r.start} → {r.end}: {len(r.rows)} matches"
         + (f" ({', '.join(r.settings['competitions'])})" if r.settings.get("competitions") else ""),
         f"Trained on {t['matches']} matches {t['first']} → day before {t['cutoff']} "
         f"(selected: {t['model']}; folds: {t['folds']})"
         + (f"; retrained {len(r.trainings) - 1}× (every {r.settings['retrain_every']} days)"
            if len(r.trainings) > 1 else "; no retraining, results fed in day by day"),
         ""]
    if r.metrics:
        m = r.metrics
        L.append(f"{'market':<14}{'log loss':>10}{'skill':>9}{'accuracy':>10}{'calib. err':>12}")
        for key, name in (("1x2", "1X2"), ("o25", "Over 2.5"), ("btts", "BTTS"),
                          ("h_o05", "Home o0.5"), ("h_o15", "Home o1.5"), ("a_o05", "Away o0.5"),
                          ("a_o15", "Away o1.5"), ("o15", "Over 1.5"), ("o35", "Over 3.5")):
            if key in m:
                x = m[key]
                L.append(f"{name:<14}{x['logloss']:10.4f}{x['skill']:9.4f}{pct(x['accuracy']):>10}"
                         f"{pct(x['ece']):>12}")
        L.append(f"combined 4-market skill {m['combined_skill']:.4f} "
                 "(log-loss gain over always predicting the period's base rate)")
    else:
        L.append("(too few matches for per-market metrics)")
    if r.bookmaker:
        L.append("\nModel vs bookmaker closing odds (same matches):")
        for key, name in (("1x2", "1X2"), ("o25", "O/U 2.5")):
            if key in r.bookmaker:
                b = r.bookmaker[key]
                L.append(f"  {name:<8} log loss model {b['model_logloss']:.4f} vs book "
                         f"{b['book_logloss']:.4f}   accuracy {pct(b['model_accuracy'])} vs "
                         f"{pct(b['book_accuracy'])}   (n={b['matches']})")
    L.append(f"\n{'best pick':<10}{'picks':>7}{'landed':>9}{'model said':>12}{'avg odds':>10}"
             f"{'book bets':>11}{'profit':>9}{'ROI':>8}")
    for style in STYLES:
        p, b = r.picks[style], r.betting[f"picks_{style}"]
        if not p["picks"]:
            L.append(f"{style:<10}{0:>7}")
            continue
        money = (f"{b['bets']:>11}{b['profit']:>+9.1f}{pct(b['roi']):>8}" if b["bets"]
                 else f"{'-':>11}")
        L.append(f"{style:<10}{p['picks']:>7}{pct(p['hit_rate']):>9}{pct(p['mean_model']):>12}"
                 f"{p['mean_odds']:10.2f}{money}")
    for key, name in (("value_1x2", "1X2"), ("value_ou25", "O/U 2.5")):
        b = r.betting[key]
        if b["bets"]:
            L.append(f"Value bets {name} (model edge > {100 * r.settings['value_edge']:.0f}%): "
                     f"{b['bets']} bets, landed {pct(b['hit_rate'])}, avg odds "
                     f"{b['mean_odds']:.2f}, profit {b['profit']:+.1f} units, ROI {pct(b['roi'])}")
    if not any(r.betting[k]["bets"] for k in r.betting):
        L.append("(no bookmaker odds in these matches, so no profit figures)")
    L.append(f"\n({r.seconds:.0f}s)")
    return "\n".join(L)
