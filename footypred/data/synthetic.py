"""Realistic synthetic match generator for offline use and tests.

Not a toy Poisson draw: each match is simulated minute by minute with
game-state effects, so the data carries the structure that past match
details are supposed to reveal:

* latent attack/defence strengths that drift weekly (mean-reverting) and
  jump between seasons
* league scoring levels and home advantage
* a per-team *volatility* trait -> shared gamma "tempo" frailty per match
  (over-dispersed totals, positively correlated scores: drives O/U & BTTS
  beyond what attack/defence alone explain)
* a per-team *game-management* trait -> when leading, the team suppresses
  the opponent (fewer BTTS), when trailing, teams push
* late-game draw protection, red cards, first/second-half intensity
* xG = integrated scoring intensity with noise (a better strength signal
  than goals, as in reality), shots, shots on target, corners, cards
* bookmaker closing odds (1X2, O/U 2.5) with margin, as an external
  benchmark — never used as a model feature
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import poisson

from footypred.logging_utils import get_logger

log = get_logger("data.synthetic")

LEAGUES = {
    "E0": (0.15, 0.20, ["Manchester City", "Arsenal", "Liverpool", "Chelsea",
                        "Newcastle United", "Tottenham", "Aston Villa", "Manchester United",
                        "Brighton", "Crystal Palace", "Bournemouth", "Brentford", "Fulham",
                        "Nottingham Forest", "West Ham", "Everton", "Wolverhampton", "Leeds",
                        "Burnley", "Sunderland"]),
    "SP1": (0.03, 0.24, ["Real Madrid", "Barcelona", "Atletico Madrid", "Athletic Bilbao",
                         "Villarreal", "Real Sociedad", "Real Betis", "Girona", "Sevilla",
                         "Valencia", "Celta Vigo", "Osasuna", "Rayo Vallecano", "Getafe",
                         "Mallorca", "Espanyol", "Alaves", "Levante", "Elche", "Real Oviedo"]),
    "I1": (0.08, 0.19, ["Inter Milan", "Napoli", "Juventus", "AC Milan", "Atalanta",
                        "AS Roma", "Lazio", "Fiorentina", "Bologna", "Como", "Torino",
                        "Udinese", "Genoa", "Cagliari", "Lecce", "Parma", "Hellas Verona",
                        "Sassuolo", "Cremonese", "Pisa"]),
    "D1": (0.23, 0.21, ["Bayern Munich", "Bayer Leverkusen", "Borussia Dortmund", "RB Leipzig",
                        "Eintracht Frankfurt", "Stuttgart", "Freiburg", "Wolfsburg",
                        "Borussia Monchengladbach", "Mainz 05", "Hoffenheim", "Werder Bremen",
                        "Union Berlin", "Augsburg", "Heidenheim", "St Pauli", "Hamburg",
                        "Cologne"]),
    "F1": (0.10, 0.22, ["Paris Saint-Germain", "Marseille", "Monaco", "Lille", "Lyon", "Nice",
                        "Lens", "Rennes", "Strasbourg", "Toulouse", "Brest", "Nantes",
                        "Auxerre", "Angers", "Le Havre", "Lorient", "Paris FC", "Metz"]),
    "N1": (0.27, 0.25, ["PSV", "Ajax", "Feyenoord", "AZ Alkmaar", "Twente", "Utrecht",
                        "Go Ahead Eagles", "NEC Nijmegen", "Heerenveen", "Sparta Rotterdam",
                        "Fortuna Sittard", "Groningen", "Heracles", "PEC Zwolle", "NAC Breda",
                        "Excelsior", "Telstar", "Volendam"]),
    "P1": (0.04, 0.26, ["Benfica", "Porto", "Sporting CP", "Braga", "Vitoria Guimaraes",
                        "Famalicao", "Gil Vicente", "Moreirense", "Estoril", "Casa Pia",
                        "Rio Ave", "Santa Clara", "Arouca", "Nacional", "Estrela Amadora",
                        "Alverca", "Tondela", "AVS"]),
}
# (log base scoring rate, log home advantage, teams strongest -> weakest)

NATIONS = ["Argentina", "France", "Spain", "England", "Brazil", "Portugal", "Netherlands",
           "Belgium", "Germany", "Croatia", "Italy", "Morocco", "Colombia", "Uruguay",
           "USA", "Mexico", "Japan", "Switzerland", "Senegal", "Denmark", "Iran",
           "South Korea", "Austria", "Ecuador", "Australia", "Ukraine", "Turkey", "Sweden",
           "Poland", "Wales", "Norway", "Nigeria"]
INTL_CODE = "INT"
INTL_BASE, INTL_HOME = 0.02, 0.25
CL_CODE = "CL"
CL_BASE, CL_HOME = 0.12, 0.20
# league strength on a common scale (for games between leagues)
LEAGUE_LEVEL = {"E0": 0.10, "SP1": 0.07, "I1": 0.05, "D1": 0.05, "F1": 0.0, "N1": -0.12,
                "P1": -0.08}
CL_PLACES = {"E0": 4, "SP1": 4, "I1": 4, "D1": 4, "F1": 3, "N1": 2, "P1": 3}


def _cl_fixtures(rng, pools, seasons, cutoff):
    """A Champions League per season: 24-team league phase (8 games each),
    two-legged last 16 / quarters / semis, a neutral-venue final."""
    rows = []
    for s in seasons:
        entrants = []
        for code, k in CL_PLACES.items():
            if code in pools:
                teams = list(pools[code][2])
                order = sorted(range(len(teams)), key=lambda i: i + rng.normal(0, 1.5))
                entrants += [teams[i] for i in order[:k]]
        if len(entrants) < 8:
            return rows
        n = len(entrants) - len(entrants) % 2
        order = list(rng.permutation(entrants[:n]))
        start = pd.Timestamp(f"{s}-09-16")
        for r in range(8):                                    # league phase
            d = start + pd.Timedelta(days=int(r * 133 / 7))
            d += pd.Timedelta(days=(1 - d.dayofweek) % 7)     # Tuesday
            for i in range(n // 2):
                h, a = order[i], order[n - 1 - i]
                if r % 2:
                    h, a = a, h
                dd = d + pd.Timedelta(days=int(rng.integers(0, 2)))
                if dd <= cutoff:
                    rows.append((dd, CL_CODE, s, h, a, 0))
            order = [order[0]] + [order[-1]] + order[1:-1]
        strength = {t: rng.normal() for t in entrants}
        alive = sorted(entrants, key=lambda t: -strength[t])[:16]
        for days, size in ((("03-03", "03-10"), 16), (("04-07", "04-14"), 8),
                           (("04-28", "05-05"), 4)):
            if len(alive) < size:              # small field: start at a later round
                continue
            alive = list(rng.permutation(alive[:size]))
            pairs = [(alive[i], alive[i + 1]) for i in range(0, size, 2)]
            for leg, md in enumerate(days):
                d = pd.Timestamp(f"{s + 1}-{md}")
                d += pd.Timedelta(days=(1 - d.dayofweek) % 7)     # Tuesday
                if d > cutoff:
                    continue
                for h, a in pairs:
                    rows.append((d, CL_CODE, s, *((h, a) if leg == 0 else (a, h)), 0))
            alive = [p[int(rng.random() < 0.5)] for p in pairs]
        final = pd.Timestamp(f"{s + 1}-05-30")
        if len(alive) >= 2 and final <= cutoff:
            rows.append((final, CL_CODE, s, alive[0], alive[1], 1))
    return rows


# ------------------------------------------------------------------ schedule
def _league_fixtures(rng, code, teams, season, cutoff):
    """Double round robin (circle method), one round per ~week."""
    n = len(teams)
    order = list(rng.permutation(teams))
    rounds = []
    for r in range(n - 1):
        pairs = [(order[i], order[n - 1 - i]) for i in range(n // 2)]
        rounds.append([(a, b) if (r + i) % 2 == 0 else (b, a) for i, (a, b) in enumerate(pairs)])
        order = [order[0]] + [order[-1]] + order[1:-1]
    rounds += [[(b, a) for a, b in rnd] for rnd in rounds]
    start = pd.Timestamp(f"{season}-08-15")
    end = pd.Timestamp(f"{season + 1}-05-24")
    span = (end - start).days
    rows = []
    for k, rnd in enumerate(rounds):
        base = start + pd.Timedelta(days=int(k * span / (len(rounds) - 1)))
        base -= pd.Timedelta(days=(base.dayofweek - 5) % 7)  # snap to Saturday
        for h, a in rnd:
            d = base + pd.Timedelta(days=int(rng.choice([0, 0, 1, 1, 2, -1])))
            if d <= cutoff:
                rows.append((d, code, season, h, a, 0))
    return rows


def _intl_fixtures(rng, seasons, cutoff):
    rows = []
    windows = []
    for s in seasons:
        for month, day in ((9, 6), (10, 11), (11, 15), (3, 23), (6, 8)):
            year = s if month >= 7 else s + 1
            windows.append((s, pd.Timestamp(f"{year}-{month:02d}-{day:02d}")))
    for season, w in windows:
        for leg in range(2):
            order = rng.permutation(NATIONS)
            d = w + pd.Timedelta(days=3 * leg)
            if d > cutoff:
                continue
            neutral = 1 if w.month == 6 else 0   # summer tournaments
            for i in range(0, len(order), 2):
                rows.append((d, INTL_CODE, season, order[i], order[i + 1], neutral))
    return rows


# -------------------------------------------------------------- team latents
def _team_traits(rng, teams_by_pool):
    traits = {}
    for pool, (base, home, teams) in teams_by_pool.items():
        n = len(teams)
        for rank, t in enumerate(teams):
            q = 1 - 2 * rank / (n - 1)                       # +1 best .. -1 worst
            traits[t] = {
                "att": 0.30 * q + rng.normal(0, 0.06),
                "def": 0.26 * q + rng.normal(0, 0.06),
                "vol": rng.uniform(0.0, 0.16),               # tempo volatility
                "gm": rng.uniform(0.0, 1.0),                 # game management
                "home_x": rng.normal(0, 0.06),               # team-specific home boost
            }
    return traits


def _latent_paths(rng, traits, weeks):
    """Weekly mean-reverting walk + season shocks for att/def."""
    paths = {}
    n = len(weeks)
    season_idx = np.array([w.year if w.month >= 7 else w.year - 1 for w in weeks])
    for t, tr in traits.items():
        out = {}
        for key in ("att", "def"):
            x = np.empty(n)
            cur = tr[key]
            for i in range(n):
                if i > 0 and season_idx[i] != season_idx[i - 1]:
                    cur += rng.normal(0, 0.07)
                cur = tr[key] + 0.985 * (cur - tr[key]) + rng.normal(0, 0.018)
                x[i] = cur
            out[key] = x
        paths[t] = out
    return paths


# ---------------------------------------------------------------- simulation
def _simulate(rng, lam_h, lam_a, vol, gm_h, gm_a):
    """Minute-level simulation, vectorised across matches."""
    n = len(lam_h)
    shape = 1.0 / np.maximum(vol, 1e-3)
    tempo = rng.gamma(shape, 1.0 / shape)                  # mean-1 frailty
    tempo = np.where(vol < 1e-3, 1.0, tempo)
    gh = np.zeros(n, int); ga = np.zeros(n, int)
    hth = np.zeros(n, int); hta = np.zeros(n, int)
    red_h = np.zeros(n, bool); red_a = np.zeros(n, bool)
    int_h = np.zeros(n); int_a = np.zeros(n)               # integrated intensity (xG basis)
    minutes = 94
    for m in range(1, minutes + 1):
        prof = 0.88 if m <= 45 else (1.08 if m <= 75 else 1.18)
        rh = lam_h * tempo * prof / 90.0
        ra = lam_a * tempo * prof / 90.0
        diff = gh - ga
        # leader sits back; strong game-managers suppress the chaser more
        rh = np.where(diff > 0, rh * (1 - 0.12 * gm_h), rh)
        ra = np.where(diff > 0, ra * (1.10 - 0.30 * gm_h), ra)
        ra = np.where(diff < 0, ra * (1 - 0.12 * gm_a), ra)
        rh = np.where(diff < 0, rh * (1.10 - 0.30 * gm_a), rh)
        late_level = (m > 78) & (diff == 0)
        rh = np.where(late_level, rh * 0.80, rh)
        ra = np.where(late_level, ra * 0.80, ra)
        rh = np.where(red_h, rh * 0.70, np.where(red_a, rh * 1.30, rh))
        ra = np.where(red_a, ra * 0.70, np.where(red_h, ra * 1.30, ra))
        red_h |= rng.random(n) < 0.06 / 90
        red_a |= rng.random(n) < 0.07 / 90
        int_h += rh; int_a += ra
        gh += rng.random(n) < rh
        ga += rng.random(n) < ra
        if m == 47:  # half-time (incl. stoppage)
            hth, hta = gh.copy(), ga.copy()
    return gh, ga, hth, hta, int_h, int_a, red_h, red_a


def _book_probs(lam_h, lam_a, vol, margin_1x2=0.05, margin_ou=0.06, rng=None):
    """Bookmaker view: noisy rates, Poisson-mixture totals, overround."""
    noise = rng.lognormal(0, 0.07, size=(2, len(lam_h)))
    lh, la = lam_h * noise[0], lam_a * noise[1]
    k = np.arange(11)
    ph = poisson.pmf(k[None, :], lh[:, None])
    pa = poisson.pmf(k[None, :], la[:, None])
    grid = ph[:, :, None] * pa[:, None, :]
    grid[:, 0, 0] *= 1.10; grid[:, 1, 1] *= 1.06           # draw inflation
    grid /= grid.sum(axis=(1, 2), keepdims=True)
    hw = np.tril(np.ones((11, 11)), -1)
    pH = (grid * hw).sum(axis=(1, 2)); pA = (grid * hw.T).sum(axis=(1, 2))
    pD = 1 - pH - pA
    tot = k[:, None] + k[None, :]
    pU = (grid * (tot <= 2)).sum(axis=(1, 2))
    pU = np.clip(pU + 0.25 * vol * (0.5 - pU), 0.02, 0.98)  # volatility widens totals
    odds = lambda p, mg: np.round(1.0 / (p * (1 + mg)), 2)
    return (odds(pH, margin_1x2), odds(pD, margin_1x2), odds(pA, margin_1x2),
            odds(1 - pU, margin_ou), odds(pU, margin_ou))


def generate(seasons: list[int], cutoff: str | pd.Timestamp | None = None,
             seed: int = 7, leagues: list[str] | None = None,
             internationals: bool = True, champions_league: bool = True) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    cutoff = pd.Timestamp(cutoff) if cutoff is not None else pd.Timestamp.today().normalize()
    pools = {c: v for c, v in LEAGUES.items() if leagues is None or c in leagues}
    if internationals:
        pools[INTL_CODE] = (INTL_BASE, INTL_HOME, NATIONS)
    traits = _team_traits(rng, pools)

    rows = []
    for s in seasons:
        for code, (_, _, teams) in pools.items():
            if code != INTL_CODE:
                rows += _league_fixtures(rng, code, teams, s, cutoff)
    if internationals:
        rows += _intl_fixtures(rng, seasons, cutoff)
    league_of = {t: c for c, (_, _, ts) in pools.items() if c != INTL_CODE for t in ts}
    if champions_league and sum(c in pools for c in CL_PLACES) >= 2:
        rows += _cl_fixtures(rng, pools, seasons, cutoff)
        pools = {**pools, CL_CODE: (CL_BASE, CL_HOME, [])}
    fx = pd.DataFrame(rows, columns=["date", "league", "season", "home", "away", "neutral"])
    fx = fx.sort_values(["date", "league", "home"]).reset_index(drop=True)
    if fx.empty:
        return fx

    weeks = pd.date_range(fx["date"].min() - pd.Timedelta(days=7), fx["date"].max(), freq="7D")
    paths = _latent_paths(rng, traits, weeks)
    wk = np.clip(np.searchsorted(weeks.values, fx["date"].values) - 1, 0, len(weeks) - 1)

    base = fx["league"].map({c: v[0] for c, v in pools.items()}).to_numpy()
    hadv = fx["league"].map({c: v[1] for c, v in pools.items()}).to_numpy()
    hadv = np.where(fx["neutral"].to_numpy() == 1, 0.0, hadv)
    att_h = np.array([paths[t]["att"][w] for t, w in zip(fx["home"], wk)])
    def_h = np.array([paths[t]["def"][w] for t, w in zip(fx["home"], wk)])
    att_a = np.array([paths[t]["att"][w] for t, w in zip(fx["away"], wk)])
    def_a = np.array([paths[t]["def"][w] for t, w in zip(fx["away"], wk)])
    hx = np.array([traits[t]["home_x"] for t in fx["home"]]) * (hadv > 0)
    # games between leagues: put both sides on the common strength scale
    cross = (fx["league"] == CL_CODE).to_numpy()
    if cross.any():
        lv_h = np.array([LEAGUE_LEVEL.get(league_of.get(t, ""), 0.0) for t in fx["home"]])
        lv_a = np.array([LEAGUE_LEVEL.get(league_of.get(t, ""), 0.0) for t in fx["away"]])
        att_h, def_h = att_h + cross * lv_h, def_h + cross * lv_h
        att_a, def_a = att_a + cross * lv_a, def_a + cross * lv_a
    lam_h = np.exp(base + hadv + hx + att_h - def_a)
    lam_a = np.exp(base + att_a - def_h)
    vol = np.array([(traits[h]["vol"] + traits[a]["vol"]) / 2
                    for h, a in zip(fx["home"], fx["away"])])
    gm_h = np.array([traits[t]["gm"] for t in fx["home"]])
    gm_a = np.array([traits[t]["gm"] for t in fx["away"]])

    gh, ga, hth, hta, ih, ia, red_h, red_a = _simulate(rng, lam_h, lam_a, vol, gm_h, gm_a)
    n = len(fx)
    fx["fthg"], fx["ftag"], fx["hthg"], fx["htag"] = gh, ga, hth, hta
    fx["home_xg"] = np.round(ih * rng.lognormal(0, 0.18, n), 2)
    fx["away_xg"] = np.round(ia * rng.lognormal(0, 0.18, n), 2)
    fx["hs"] = gh + rng.poisson(ih * 5.5 + 4)
    fx["as_"] = ga + rng.poisson(ia * 5.5 + 4)
    fx["hst"] = gh + rng.binomial(fx["hs"] - gh, 0.27)
    fx["ast"] = ga + rng.binomial(fx["as_"] - ga, 0.27)
    fx["hc"] = rng.poisson(2.6 + 1.5 * ih)
    fx["ac"] = rng.poisson(2.6 + 1.5 * ia)
    fx["hy"] = rng.poisson(1.7, n); fx["ay"] = rng.poisson(1.9, n)
    fx["hr"] = red_h.astype(int); fx["ar"] = red_a.astype(int)
    oh, od, oa, oo, ou = _book_probs(lam_h, lam_a, vol, rng=rng)
    fx["odds_h"], fx["odds_d"], fx["odds_a"], fx["odds_o25"], fx["odds_u25"] = oh, od, oa, oo, ou

    log.info("synthetic: %d matches, %d teams, %s -> %s, avg goals %.2f, "
             "BTTS %.1f%%, O2.5 %.1f%%", n, len(traits), fx["date"].min().date(),
             fx["date"].max().date(), (gh + ga).mean(),
             100 * ((gh > 0) & (ga > 0)).mean(), 100 * ((gh + ga) > 2).mean())
    return fx


def team_market_values(seasons: list[int], seed: int = 7) -> pd.DataFrame:
    """Squad market values consistent with team strength ordering."""
    rng = np.random.default_rng(seed + 1)
    rows = []
    scale = {"E0": 1100, "SP1": 900, "I1": 700, "D1": 800, "F1": 650, "N1": 250, "P1": 300}
    for code, (_, _, teams) in LEAGUES.items():
        for s in seasons:
            for rank, t in enumerate(teams):
                v = scale[code] * np.exp(-2.4 * rank / len(teams)) * rng.lognormal(0, 0.12)
                rows.append({"team": t, "date": f"{s}-08-01", "key": "market_value_m",
                             "value": round(float(v), 1)})
    return pd.DataFrame(rows)
