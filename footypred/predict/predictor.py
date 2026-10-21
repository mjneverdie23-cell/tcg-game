"""Fixture prediction for the four target markets.

name resolution -> cached feature state (+ replay of any newer results)
-> every goal model's score matrix -> backbone (selected model/ensemble)
-> per-market head -> matrix reconciled to all markets -> report.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from footypred.data.db import Database
from footypred.data.names import NameResolver
from footypred.features.engineering import FeatureBuilder
from footypred.logging_utils import get_logger
from footypred.models.market_head import probs_from_grids, reconcile
from footypred.models.registry import ModelRegistry
from footypred.models.scorematrix import ScoreMatrix
from footypred.predict.explain import drivers, evidence
from footypred.predict.picks import FormIndex, base_rates, form_check

log = get_logger("predict")

# pick-strength labels; a 3-way market's favourite needs less probability
STRENGTH_2WAY = [(0.70, "strong"), (0.60, "solid"), (0.55, "lean"), (0.0, "toss-up")]
STRENGTH_3WAY = [(0.60, "strong"), (0.50, "solid"), (0.42, "lean"), (0.0, "toss-up")]


def strength(p: float, three_way: bool = False) -> str:
    table = STRENGTH_3WAY if three_way else STRENGTH_2WAY
    return next(lbl for t, lbl in table if p >= t)


@dataclass
class Prediction:
    home: str
    away: str
    date: str
    league: str
    league_name: str
    neutral: bool
    model: str
    version: str
    markets: dict
    picks: dict
    confidence: dict
    expected_goals: dict
    top_scores: list
    model_markets: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)
    drivers: dict = field(default_factory=dict)
    form: dict = field(default_factory=dict)          # last-5 form check + best pick
    halftime: dict = field(default_factory=dict)      # first-half markets (if the model has them)
    warnings: list = field(default_factory=list)
    # raw objects for charts (not serialised)
    score_matrix: ScoreMatrix | None = None
    model_matrices: dict = field(default_factory=dict)
    eval_preds: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        skip = {"score_matrix", "model_matrices", "eval_preds"}
        return {k: v for k, v in self.__dict__.items() if k not in skip}


def _market_view(p: dict) -> dict:
    """Flat market probabilities -> the four structured markets."""
    r = lambda x: round(float(x), 4)
    tt = lambda s: {f"over_{l}": r(p[f"{s}_o{l.replace('.', '')}"]) for l in ("0.5", "1.5", "2.5")}
    return {
        "1x2": {"home": r(p["1x2"][0]), "draw": r(p["1x2"][1]), "away": r(p["1x2"][2])},
        "over_under_2.5": {"over": r(p["o25"]), "under": r(1 - p["o25"])},
        "totals": {f"over_{l}": r(p[k]) for l, k in (("1.5", "o15"), ("2.5", "o25"),
                                                    ("3.5", "o35")) if k in p},
        "btts": {"yes": r(p["btts"]), "no": r(1 - p["btts"])},
        "team_totals": {"home": tt("h"), "away": tt("a")},
    }


def market_grids(res, rows: pd.DataFrame):
    """Final score matrices (n, G, G) for fixture feature rows: backbone
    (selected model or ensemble) -> per-market head -> reconciled. Also
    returns every model's own matrices (for agreement / divergence)."""
    fcols = res.feature_cols
    rows = rows.copy()
    for c in fcols:
        if c not in rows:
            rows[c] = np.nan
    G = int(res.config.get("max_goals", 10)) + 1
    mats = {name: m.predict_grids(rows, fcols, G) for name, m in res.models.items()}
    if res.selected == "ensemble":
        backbone = sum(w * mats[n] for n, w in res.weights.items() if w > 0)
    else:
        backbone = mats[res.selected]
    direct = res.direct.predict(rows, fcols) if res.head.needs_direct else None
    target = res.head.predict(probs_from_grids(backbone), direct)
    return reconcile(backbone, target), mats


def halftime_view(res, row, fcols, lam_home: float, lam_away: float) -> tuple[dict, dict]:
    """First-half markets for one fixture: (view for the report/UI, flat
    probabilities ht_* for the pick engine). Empty when the model has no
    first-half part (bundles trained before 2.7)."""
    from footypred.models.halftime import ht_probs
    ht = getattr(res, "halftime", None)
    if ht is None:
        return {}, {}
    grid = ht.predict_grids(row, fcols, (np.array([lam_home]), np.array([lam_away])))
    p = {k: v[0] for k, v in ht_probs(grid).items()}
    sm = ScoreMatrix.from_grid(grid[0])
    r = lambda x: round(float(x), 4)
    pick2 = lambda q, yes, no: ({"pick": yes, "prob": r(q)} if q >= 0.5 else {"pick": no, "prob": r(1 - q)})
    k = int(np.argmax(p["1x2"]))
    picks = {"1x2": {"pick": ["Home", "Draw", "Away"][k], "prob": r(p["1x2"][k]),
                     "strength": strength(p["1x2"][k], three_way=True)},
             "btts": pick2(p["btts"], "BTTS Yes", "BTTS No")}
    for line, key in (("0.5", "o05"), ("1.5", "o15"), ("2.5", "o25")):
        picks[f"over_under_{line}"] = pick2(p[key], f"Over {line}", f"Under {line}")
    for v in picks.values():
        v["fair_odds"] = round(1 / max(v["prob"], 1e-9), 2)
        v.setdefault("strength", strength(v["prob"]))
    view = {"1x2": {"home": r(p["1x2"][0]), "draw": r(p["1x2"][1]), "away": r(p["1x2"][2])},
            "totals": {"over_0.5": r(p["o05"]), "over_1.5": r(p["o15"]), "over_2.5": r(p["o25"])},
            "btts": {"yes": r(p["btts"]), "no": r(1 - p["btts"])},
            "team_scores": {"home": r(p["h_o05"]), "away": r(p["a_o05"])},
            "expected_goals": {"home": round(sm.lam_home, 2), "away": round(sm.lam_away, 2),
                               "total": round(sm.lam_home + sm.lam_away, 2)},
            "top_scores": [(sc, round(q, 4)) for sc, q in sm.top_scores(5)],
            "picks": picks, "model": (ht.report or {}).get("selected"),
            "skill": ((ht.report or {}).get("eval") or {}).get("combined_skill")}
    flat = {"ht_1x2": p["1x2"], "ht_o05": p["o05"], "ht_o15": p["o15"], "ht_o25": p["o25"],
            "ht_btts": p["btts"]}
    return view, flat


class Predictor:
    def __init__(self, cfg, db: Database | None = None, version: str | None = None):
        self.cfg = cfg
        from footypred.data.localfile import cup_codes, sync_db
        if db is None:
            db = Database(cfg.paths.db_file)
            sync_db(cfg, db)                     # your match file, if it changed
        self.db = db
        self.bundle = ModelRegistry(cfg.paths.models_dir).load(version)
        self.res = self.bundle.result
        self.state = self._sync_state()
        self.resolver = NameResolver(self.db.teams(), self.db.load_aliases())
        self.cups = cup_codes(cfg)
        self.team_league = self.db.team_league(self.cups)
        self.competitions = set(self.db.load_matches()["league"].unique())
        matches = self.db.load_matches()
        self.form_index = FormIndex(matches)
        self.base_rates = base_rates(matches)
        self.pick_opts = dict((cfg.raw.get("picks") or {}))

    def _sync_state(self):
        """Use the cached state; replay only results newer than it. Fall back
        to a full rebuild if older history changed underneath it."""
        state = self.bundle.state
        m = self.db.load_matches()
        if state is None or state.last_date is None:
            return self._rebuild()
        old = m[m["date"] <= state.last_date]
        if len(old) != state.n_matches:
            log.info("history changed since training; rebuilding feature state")
            return self._rebuild()
        new = m[m["date"] > state.last_date]
        if len(new):
            log.info("replaying %d results newer than the model", len(new))
            state.replay(new)
        return state

    def _rebuild(self):
        fb = FeatureBuilder(self.cfg, self.db, self.res.feature_params)
        fb.build_training_frame()
        return fb.state

    def _league_for(self, home, away, competition=None):
        """The competition the fixture is played in: given explicitly, else
        the shared league; teams from different domestic leagues meet in the
        Champions League (when that's in your data)."""
        if competition:
            if competition not in self.competitions:
                raise ValueError(f"unknown competition '{competition}'; known: "
                                 f"{', '.join(sorted(self.competitions))}")
            return competition
        lh, la = self.team_league.get(home), self.team_league.get(away)
        if "INT" in (lh, la):
            return "INT"
        if lh and la and lh != la:
            cup = next((c for c in ("CL",) if c in self.competitions), None)
            if cup and (lh in self.cups or la in self.cups or
                        (lh not in self.cups and la not in self.cups)):
                return cup
        return lh or la or "UNK"

    def predict(self, home: str, away: str, date=None, neutral: bool = False,
                pick_opts: dict | None = None, competition: str | None = None) -> Prediction:
        home, away = self.resolver.resolve(home), self.resolver.resolve(away)
        if home == away:
            raise ValueError("home and away must be different teams")
        date = pd.Timestamp(date) if date is not None else pd.Timestamp.today().normalize()
        league = self._league_for(home, away, competition)
        res = self.res

        f = self.state.features(home, away, date, league, neutral)
        row = pd.DataFrame([{**f, "home": home, "away": away, "league": league,
                             "neutral": float(neutral), "date": date}])
        fcols = res.feature_cols
        for c in fcols:
            if c not in row:
                row[c] = np.nan
        finals, mats = market_grids(res, row)
        final = finals[0]
        sm = ScoreMatrix.from_grid(final)
        p = {k: v[0] for k, v in probs_from_grids(final[None]).items()}
        markets = _market_view(p)

        model_markets = {}
        for name, g in mats.items():
            mp = {k: v[0] for k, v in probs_from_grids(g).items()}
            model_markets[name] = _market_view(mp)

        picks, conf = self._picks_and_confidence(p, markets, model_markets, f, home, away)
        halftime, ht_flat = halftime_view(res, row, fcols, sm.lam_home, sm.lam_away)
        p_all = {**p, **ht_flat}                  # first-half lines for the pick engine
        warn = []
        nh, na = f.get("h_n_hist", 0), f.get("a_n_hist", 0)
        if min(nh, na) < self.cfg.features.get("min_history", 3):
            warn.append("very little match history for one side - treat with caution")
        if league == "UNK":
            warn.append("league unknown; using global scoring levels")
        lh, la = self.team_league.get(home), self.team_league.get(away)
        if lh and la and lh != la and league not in ("INT",) and league not in self.cups:
            warn.append(f"cross-league fixture ({lh} vs {la}): scoring level of the home "
                        "side's league is used")
        elif lh and la and lh != la and league in self.cups and not competition:
            warn.append(f"teams from different leagues ({lh} vs {la}): treated as a "
                        f"{league} match (choose another competition to override)")
        trained_on = (res.report or {}).get("data_source")
        now_on = self.db.get_meta("data_source")
        if trained_on and now_on and trained_on != now_on:
            warn.append(f"the model was trained on {trained_on} data but {now_on} data is "
                        "loaded — train it again (Data tab > Model, or `footy train`)")
        last = self.state.last_date
        if last is not None and date < last:
            warn.append(f"date is before the latest result on record ({last.date()}); the "
                        "model already knows later results, so this is not a fair backtest (use the "
                        "Backtest tab, or `footy backtest`, for that)")

        return Prediction(
            home=home, away=away, date=str(date.date()), league=league,
            league_name=(self.cfg.leagues.get(league, {}) or {}).get(
                "name", "International" if league == "INT" else league),
            neutral=neutral,
            model=res.selected, version=self.bundle.version, markets=markets, picks=picks,
            confidence=conf,
            expected_goals={"home": round(sm.lam_home, 2), "away": round(sm.lam_away, 2),
                            "total": round(sm.lam_home + sm.lam_away, 2)},
            top_scores=[(s, round(q, 4)) for s, q in sm.top_scores(6)],
            model_markets=model_markets, evidence=evidence(self.state, home, away, neutral),
            drivers=drivers(res.direct, row, fcols, home, away),
            form=form_check(self.form_index, home, away, date, p_all,
                            {**self.pick_opts, **(pick_opts or {})}, neutral,
                            self.base_rates.get(league) or self.base_rates.get("_all")),
            warnings=warn, halftime=halftime,
            score_matrix=sm, model_matrices={n: ScoreMatrix.from_grid(g[0]) for n, g in mats.items()},
            eval_preds=res.eval_preds,
        )

    def _picks_and_confidence(self, p, markets, model_markets, f, home, away):
        picks, conf = {}, {}
        hist = min(f.get("h_n_hist", 0) or 0, f.get("a_n_hist", 0) or 0)
        data_q = min(hist / 20.0, 1.0)

        def spread(getter):
            vals = [getter(mm) for mm in model_markets.values()]
            return float(np.std(vals)) if len(vals) > 1 else 0.0

        def score(prob_pick, decis, sp):
            agree = max(0.0, 1 - sp / 0.12)
            return round(100 * (0.5 * decis + 0.3 * agree + 0.2 * data_q))

        # 1X2
        probs = p["1x2"]
        k = int(np.argmax(probs))
        side = [f"{home} win", "Draw", f"{away} win"][k]
        picks["1x2"] = {"pick": side, "prob": round(float(probs[k]), 4),
                        "fair_odds": round(1 / probs[k], 2),
                        "strength": strength(probs[k], three_way=True)}
        conf["1x2"] = score(probs[k], (probs[k] - 1 / 3) / (2 / 3),
                            spread(lambda mm: mm["1x2"]["home"]))
        # O/U 2.5 and BTTS
        for key, yes, no, getter in (
                ("over_under_2.5", "Over 2.5", "Under 2.5", lambda mm: mm["over_under_2.5"]["over"]),
                ("btts", "BTTS Yes", "BTTS No", lambda mm: mm["btts"]["yes"])):
            q = p["o25"] if key == "over_under_2.5" else p["btts"]
            pick, pp = (yes, q) if q >= 0.5 else (no, 1 - q)
            picks[key] = {"pick": pick, "prob": round(float(pp), 4),
                          "fair_odds": round(1 / pp, 2), "strength": strength(pp)}
            conf[key] = score(pp, abs(q - 0.5) * 2, spread(getter))
        # team totals: best line per team
        tt_conf = []
        picks["team_totals"] = {}
        for side, team in (("h", home), ("a", away)):
            lines = []
            for line in ("0.5", "1.5", "2.5"):
                q = p[f"{side}_o{line.replace('.', '')}"]
                pick, pp = (f"Over {line}", q) if q >= 0.5 else (f"Under {line}", 1 - q)
                lines.append({"line": line, "pick": pick, "prob": round(float(pp), 4),
                              "fair_odds": round(1 / pp, 2), "strength": strength(pp)})
                tkey = "home" if side == "h" else "away"
                sp = spread(lambda mm, t=tkey, l=line: mm["team_totals"][t][f"over_{l}"])
                tt_conf.append(score(pp, abs(q - 0.5) * 2, sp))
            picks["team_totals"][team] = lines
        conf["team_totals"] = round(float(np.mean(tt_conf)))
        conf["overall"] = round(float(np.mean([conf["1x2"], conf["over_under_2.5"],
                                               conf["btts"], conf["team_totals"]])))
        return picks, conf
