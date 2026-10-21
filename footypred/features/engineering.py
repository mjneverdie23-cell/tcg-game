"""Leakage-safe pre-match features from past match details.

Matches are replayed in date order. For every date, features for all of
that day's fixtures are computed from the state *before* any of the day's
results are applied; then the state is updated. The same state object
produces features for future fixtures at prediction time, so training and
prediction features are identical by construction.

Feature families (h_ = home side, a_ = away side):

* market-event rates per window — the past-match details that drive the
  four markets: scored 1+/2+/3+ (team over 0.5/1.5/2.5), conceded 1+/2+/3+,
  BTTS rate, over-2.5 rate, win/draw rates, points per game
* volume/quality: goals, xG, shots on target for & against, 1st-half goals
* residuals vs the rating-implied expectation (goals, BTTS, over-2.5):
  a team's tendency beyond its strength (game management, tempo)
* totals dispersion: how volatile a team's match totals are
* windows: last 5, last 10, venue-specific (home team at home / away team
  away), and exponentially weighted
* matchup composites (e.g. home scored-1+ rate x away conceded-1+ rate)
* ratings: Elo, online Poisson attack/defence (goals and xG-blend), and
  the market probabilities those ratings imply
* head-to-head, league scoring environment, rest/congestion, external
  (ClubElo, market value, FIFA points), weather
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from functools import partial

import numpy as np
import pandas as pd

from footypred.features.ratings import Elo, PoissonRatings
from footypred.logging_utils import get_logger
from footypred.models.scorematrix import market_probs, poisson_grids

log = get_logger("features")

META_COLS = ["match_id", "date", "season", "league", "home", "away",
             "y_h", "y_a", "y_ht_h", "y_ht_a",           # targets (full time, half time)
             "odds_h", "odds_d", "odds_a", "odds_o25", "odds_u25"]

# record layout (per team, per past match)
GF, GA, HTF, HTA, XGF, XGA, SOTF, SOTA, EGF, EGA, PBT, PO25, VEN, DAY = range(14)

FULL_STATS = ["gf", "ga", "xgf", "xga", "sotf", "sota", "s1", "s2", "s3", "c1", "c2",
              "c3", "btts", "o25", "win", "draw", "ppg", "ht", "gf_res", "ga_res",
              "btts_res", "o25_res", "tot_disp"]
SHORT_STATS = ["gf", "ga", "xgf", "xga", "s1", "c1", "btts", "o25", "ppg"]
VENUE_STATS = ["gf", "ga", "xgf", "xga", "s1", "s2", "s3", "c1", "c2", "c3", "btts",
               "o25", "ppg"]


def _rec_values(r) -> dict[str, float]:
    gf, ga = r[GF], r[GA]
    tot = gf + ga
    etot = r[EGF] + r[EGA]
    return {
        "gf": gf, "ga": ga, "xgf": r[XGF], "xga": r[XGA], "sotf": r[SOTF], "sota": r[SOTA],
        "s1": gf >= 1, "s2": gf >= 2, "s3": gf >= 3,
        "c1": ga >= 1, "c2": ga >= 2, "c3": ga >= 3,
        "btts": (gf > 0) and (ga > 0), "o25": tot > 2,
        "win": gf > ga, "draw": gf == ga, "ppg": 3 * (gf > ga) + (gf == ga),
        "ht": r[HTF] + r[HTA],
        "gf_res": gf - r[EGF], "ga_res": ga - r[EGA],
        "btts_res": float((gf > 0) and (ga > 0)) - r[PBT],
        "o25_res": float(tot > 2) - r[PO25],
        "tot_disp": (tot - etot) ** 2 / max(etot, 0.5),
    }


def _nm(xs) -> float:
    """mean ignoring NaN; NaN when nothing is known (no warning)."""
    xs = [x for x in xs if not (isinstance(x, float) and math.isnan(x))]
    return sum(xs) / len(xs) if xs else np.nan


def _window(recs, stats) -> dict[str, float]:
    if not recs:
        return {s: np.nan for s in stats}
    vals = [_rec_values(r) for r in recs]
    out = {}
    for s in stats:
        xs = [float(v[s]) for v in vals if v[s] is not None and not
              (isinstance(v[s], float) and math.isnan(v[s]))]
        out[s] = sum(xs) / len(xs) if xs else np.nan
    return out


class _EW:
    """Exponentially weighted means with bias correction; NaN-aware."""

    def __init__(self, halflife: float):
        self.a = 1 - 0.5 ** (1 / halflife)
        self.s: dict[str, float] = defaultdict(float)
        self.w: dict[str, float] = defaultdict(float)

    def add(self, vals: dict) -> None:
        for k, v in vals.items():
            if v is None or (isinstance(v, float) and math.isnan(v)):
                continue
            self.s[k] = (1 - self.a) * self.s[k] + self.a * float(v)
            self.w[k] = (1 - self.a) * self.w[k] + self.a

    def get(self, k: str) -> float:
        w = self.w.get(k, 0.0)
        return self.s[k] / w if w > 0 else np.nan


class FeatureState:
    def __init__(self, fcfg: dict | None = None, team_info: pd.DataFrame | None = None,
                 weather: pd.DataFrame | None = None):
        f = fcfg or {}
        self.w_short, self.w_long = (f.get("windows") or [5, 10])[:2]
        self.w_venue = f.get("venue_window", 8)
        self.halflife = f.get("ew_halflife", 8)
        self.h2h_n = f.get("h2h_matches", 6)
        self.min_hist = f.get("min_history", 3)
        # partial() instead of lambdas keeps the state picklable (it is cached
        # in the model bundle so prediction needn't replay all history)
        self.hist: dict[str, deque] = defaultdict(partial(deque, maxlen=self.w_long))
        self.venue: dict[tuple, deque] = defaultdict(partial(deque, maxlen=self.w_venue))
        self.ew: dict[str, _EW] = defaultdict(partial(_EW, self.halflife))
        self.count: dict[str, int] = defaultdict(int)
        self.dates: dict[str, deque] = defaultdict(partial(deque, maxlen=8))
        self.h2h: dict[frozenset, deque] = defaultdict(partial(deque, maxlen=self.h2h_n))
        self.league_ew: dict[str, _EW] = defaultdict(partial(_EW, 150))
        self.last_date: pd.Timestamp | None = None
        self.n_matches = 0
        self.elo = Elo(k=f.get("elo_k", 20))
        self.rt = PoissonRatings(lr=f.get("rt_lr", 0.01))              # goals
        self.rx = PoissonRatings(lr=f.get("rx_lr", 0.03))              # goals/xG blend
        self.xg_w = f.get("rx_xg_weight", 0.5)
        self._ext = self._index_team_info(team_info)
        self._weather = ({r.match_id: r for r in weather.itertuples()}
                         if weather is not None and not weather.empty else {})

    # ------------------------------------------------------------ external
    @staticmethod
    def _index_team_info(ti):
        idx = {}
        if ti is None or ti.empty:
            return idx
        for (team, key), g in ti.groupby(["team", "key"]):
            g = g.sort_values("date")
            idx[(team, key)] = (g["date"].values.astype("datetime64[D]"), g["value"].values)
        return idx

    def _ext_value(self, team, key, date):
        e = self._ext.get((team, key))
        if e is None:
            return np.nan
        i = np.searchsorted(e[0], np.datetime64(date, "D"), side="left") - 1
        return float(e[1][i]) if i >= 0 else np.nan

    # ------------------------------------------------------------ features
    def _side(self, team, venue, date_ord, p) -> dict[str, float]:
        out = {}
        recs = list(self.hist.get(team, ()))
        for s, v in _window(recs[-self.w_short:], SHORT_STATS).items():
            out[f"{p}_s{self.w_short}_{s}"] = v
        for s, v in _window(recs, FULL_STATS).items():
            out[f"{p}_l{self.w_long}_{s}"] = v
        for s, v in _window(list(self.venue.get((team, venue), ())), VENUE_STATS).items():
            out[f"{p}_v_{s}"] = v
        ew = self.ew.get(team)
        for s in FULL_STATS:
            out[f"{p}_ew_{s}"] = ew.get(s) if ew is not None else np.nan
        n = self.count.get(team, 0)
        out[f"{p}_n_hist"] = min(n, 50)
        out[f"{p}_trusted"] = float(n >= self.min_hist)
        ds = self.dates.get(team, ())
        # clamp: a fixture dated before the latest stored result must not
        # produce negative rest (garbage the tree models would extrapolate on)
        out[f"{p}_rest"] = min(max(date_ord - ds[-1], 0), 21) if ds else np.nan
        out[f"{p}_cong21"] = sum(1 for d in ds if 0 <= date_ord - d <= 21)
        out[f"{p}_elo"] = self.elo.rating(team)
        out[f"{p}_rt_att"] = self.rt.att.get(team, 0.0)
        out[f"{p}_rt_def"] = self.rt.dfn.get(team, 0.0)
        out[f"{p}_rx_att"] = self.rx.att.get(team, 0.0)
        out[f"{p}_rx_def"] = self.rx.dfn.get(team, 0.0)
        return out

    def features(self, home, away, date, league, neutral=False, match_id=None) -> dict:
        date = pd.Timestamp(date)
        d_ord = date.toordinal()
        hv = "N" if neutral else "H"
        av = "N" if neutral else "A"
        f = {}
        f.update(self._side(home, hv, d_ord, "h"))
        f.update(self._side(away, av, d_ord, "a"))

        # ratings and what they imply for the four markets
        lh, la = self.rt.rates(home, away, league, neutral)
        xh, xa = self.rx.rates(home, away, league, neutral)
        f.update({"rt_lh": lh, "rt_la": la, "rx_lh": xh, "rx_la": xa,
                  "rx_sup": xh - xa, "rx_tot": xh + xa,
                  "elo_diff": f["h_elo"] - f["a_elo"],
                  "elo_exp": self.elo.expected(home, away, neutral)})
        pm = market_probs(poisson_grids(xh, xa, rho=-0.05))
        for k, v in pm.items():
            f[f"pr_{k}"] = float(v[0])

        # matchup composites: attack record of one side vs defence record of other
        g = lambda k: f.get(k, np.nan)
        for t in ("1", "2", "3"):
            f[f"m_h_s{t}"] = _nm([g(f"h_ew_s{t}"), g(f"a_ew_c{t}")])
            f[f"m_a_s{t}"] = _nm([g(f"a_ew_s{t}"), g(f"h_ew_c{t}")])
            f[f"m_hv_s{t}"] = _nm([g(f"h_v_s{t}"), g(f"a_v_c{t}")])
            f[f"m_av_s{t}"] = _nm([g(f"a_v_s{t}"), g(f"h_v_c{t}")])
        f["m_btts"] = _nm([g("h_ew_btts"), g("a_ew_btts")])
        f["m_btts_v"] = _nm([g("h_v_btts"), g("a_v_btts")])
        f["m_btts_prod"] = f["m_h_s1"] * f["m_a_s1"]
        f["m_o25"] = _nm([g("h_ew_o25"), g("a_ew_o25")])
        f["m_o25_v"] = _nm([g("h_v_o25"), g("a_v_o25")])
        f["m_btts_res"] = _nm([g("h_ew_btts_res"), g("a_ew_btts_res")])
        f["m_o25_res"] = _nm([g("h_ew_o25_res"), g("a_ew_o25_res")])
        f["m_disp"] = _nm([g("h_ew_tot_disp"), g("a_ew_tot_disp")])
        f["m_xg_h"] = _nm([g("h_ew_xgf"), g("a_ew_xga")])
        f["m_xg_a"] = _nm([g("a_ew_xgf"), g("h_ew_xga")])
        f["m_gl_h"] = _nm([g("h_ew_gf"), g("a_ew_ga")])
        f["m_gl_a"] = _nm([g("a_ew_gf"), g("h_ew_ga")])

        # head to head (any venue), from the current home side's view
        meet = list(self.h2h.get(frozenset((home, away)), ()))
        f["h2h_n"] = len(meet)
        if meet:
            f["h2h_tot"] = np.mean([m[1] + m[2] for m in meet])
            f["h2h_btts"] = np.mean([(m[1] > 0) and (m[2] > 0) for m in meet])
            f["h2h_o25"] = np.mean([m[1] + m[2] > 2 for m in meet])
            f["h2h_gd"] = np.mean([(m[1] - m[2]) if m[0] == home else (m[2] - m[1])
                                   for m in meet])
        else:
            f.update({"h2h_tot": np.nan, "h2h_btts": np.nan, "h2h_o25": np.nan,
                      "h2h_gd": np.nan})

        # league scoring environment
        le = self.league_ew.get(league)
        for k in ("gpm", "btts", "o25", "hw", "dr"):
            f[f"lg_{k}"] = le.get(k) if le is not None else np.nan

        # context
        f["neutral"] = float(neutral)
        f["intl"] = float(league == "INT")
        start = pd.Timestamp(year=date.year if date.month >= 7 else date.year - 1,
                             month=8, day=1)
        f["season_prog"] = min(max((date - start).days / 300, 0.0), 1.0)
        f["rest_diff"] = g("h_rest") - g("a_rest")

        # external
        for key, nm in (("clubelo", "clubelo"), ("market_value_m", "mv"), ("fifa_points", "fifa")):
            vh = self._ext_value(home, key, date)
            va = self._ext_value(away, key, date)
            if nm == "mv":
                vh, va = np.log1p(vh), np.log1p(va)
            f[f"x_{nm}_h"], f[f"x_{nm}_a"], f[f"x_{nm}_diff"] = vh, va, vh - va
        w = self._weather.get(match_id) if match_id else None
        f["w_temp"] = w.temp_c if w is not None else np.nan
        f["w_precip"] = w.precip_mm if w is not None else np.nan
        f["w_wind"] = w.wind_kmh if w is not None else np.nan
        return f

    # -------------------------------------------------------------- update
    def update(self, m) -> None:
        home, away, league = m["home"], m["away"], m["league"]
        neutral = bool(m.get("neutral", 0) or 0)
        gh, ga = int(m["fthg"]), int(m["ftag"])
        nanf = lambda v: float(v) if v is not None and not pd.isna(v) else np.nan
        hxg, axg = nanf(m.get("home_xg")), nanf(m.get("away_xg"))
        hth, hta = nanf(m.get("hthg")), nanf(m.get("htag"))
        hst, ast = nanf(m.get("hst")), nanf(m.get("ast"))
        d_ord = pd.Timestamp(m["date"]).toordinal()

        # rating-implied expectations *before* this result (for residuals)
        lh, la = self.rx.rates(home, away, league, neutral)
        pm = market_probs(poisson_grids(lh, la, rho=-0.05))
        p_btts, p_o25 = float(pm["btts"][0]), float(pm["o25"][0])

        hv = "N" if neutral else "H"
        av = "N" if neutral else "A"
        rec_h = (gh, ga, hth, hta, hxg, axg, hst, ast, lh, la, p_btts, p_o25, hv, d_ord)
        rec_a = (ga, gh, hta, hth, axg, hxg, ast, hst, la, lh, p_btts, p_o25, av, d_ord)
        for team, rec, ven in ((home, rec_h, hv), (away, rec_a, av)):
            self.hist[team].append(rec)
            self.venue[(team, ven)].append(rec)
            self.ew[team].add(_rec_values(rec))
            self.count[team] += 1
            self.dates[team].append(d_ord)
        self.h2h[frozenset((home, away))].append((home, gh, ga))
        self.league_ew[league].add({"gpm": gh + ga, "btts": float(gh > 0 and ga > 0),
                                    "o25": float(gh + ga > 2), "hw": float(gh > ga),
                                    "dr": float(gh == ga)})
        self.elo.update(home, away, gh, ga, neutral)
        self.rt.update(home, away, league, gh, ga, neutral)
        bh, ba = float(gh), float(ga)
        if self.xg_w and not (math.isnan(hxg) or math.isnan(axg)):
            bh = (1 - self.xg_w) * gh + self.xg_w * hxg
            ba = (1 - self.xg_w) * ga + self.xg_w * axg
        self.rx.update(home, away, league, bh, ba, neutral)
        day = pd.Timestamp(m["date"])
        self.last_date = day if self.last_date is None else max(self.last_date, day)
        self.n_matches += 1

    def replay(self, matches: pd.DataFrame) -> None:
        """Apply results (date-ordered) to the state without making features."""
        for r in matches.sort_values(["date", "match_id"]).to_dict("records"):
            self.update(r)


class FeatureBuilder:
    def __init__(self, cfg, db, params: dict | None = None):
        """params: tuned overrides of cfg.features (e.g. rating learning rates)."""
        self.cfg, self.db = cfg, db
        self.params = {**dict(cfg.features), **(params or {})}
        self.state: FeatureState | None = None

    def _new_state(self) -> FeatureState:
        return FeatureState(self.params, self.db.load_team_info(), self.db.load_weather())

    def build_training_frame(self, matches: pd.DataFrame | None = None) -> pd.DataFrame:
        """Replay all played matches; returns one leakage-safe row per match.
        Leaves the final state on self.state for predicting future fixtures."""
        m = self.db.load_matches() if matches is None else matches
        m = m.sort_values(["date", "match_id"]).reset_index(drop=True)
        state = self._new_state()
        rows = []
        records = m.to_dict("records")
        i = 0
        while i < len(records):
            day = records[i]["date"]
            j = i
            while j < len(records) and records[j]["date"] == day:
                j += 1
            batch = records[i:j]
            for r in batch:          # features first, from pre-day state ...
                f = state.features(r["home"], r["away"], r["date"], r["league"],
                                   bool(r.get("neutral") or 0), r["match_id"])
                f.update({k: r.get(k) for k in META_COLS if k in r})
                f["y_h"], f["y_a"] = int(r["fthg"]), int(r["ftag"])
                ht = r.get("hthg"), r.get("htag")
                f["y_ht_h"], f["y_ht_a"] = ((float(ht[0]), float(ht[1]))
                                            if not any(v is None or pd.isna(v) for v in ht)
                                            else (np.nan, np.nan))
                rows.append(f)
            for r in batch:          # ... then apply the day's results
                state.update(r)
            i = j
        self.state = state
        frame = pd.DataFrame(rows)
        log.info("feature frame: %d matches x %d features", len(frame),
                 len(feature_columns(frame)))
        return frame

    def fixture_features(self, home, away, date, league, neutral=False) -> pd.DataFrame:
        if self.state is None:
            self.build_training_frame()
        f = self.state.features(home, away, date, league, neutral)
        f.update({"home": home, "away": away, "date": pd.Timestamp(date), "league": league,
                  "neutral": float(neutral)})
        return pd.DataFrame([f])


def feature_columns(frame: pd.DataFrame) -> list[str]:
    meta = set(META_COLS)
    return [c for c in frame.columns if c not in meta
            and pd.api.types.is_numeric_dtype(frame[c])]
