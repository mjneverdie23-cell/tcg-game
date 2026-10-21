"""Form check and best-pick engine.

For an upcoming fixture it looks at

    each team's last 5 matches, last 5 home games and last 5 away games
    each team's last 5 games against opponents rated like this opponent
    the last 5 head-to-head meetings

counts how often each team scored and conceded (1+, 2+, 3+), kept clean
sheets, failed to score, and how often games had BTTS / over 2.5, then
scores every selection in the four markets by how often it would have
landed in those windows (the *form rate*). The best pick is the selection
that the form supports most strongly, with the calibrated model
probability as a sanity check:

    score = form_weight * form_rate(shrunk) + (1 - form_weight) * model_prob

A selection is only eligible when both form and model back it
(form >= min_form, model >= min_model), it beats a typical game in that
league (min_lift), and its fair odds sit inside the style's range
(safe / balanced / bold). In a lopsided match the favourite's safe lines
are too short to be worth a bet, so the pick moves up the ladder: bigger
team lines, the win, total goals, BTTS. The "vs similar opponents" window
is what makes those bigger lines judgeable: it shows how the favourite
does against teams like this opponent, not against an average side.

Windows are read from match history strictly before the fixture date, so
the same code is used for live picks and for the out-of-sample backtest.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np
import pandas as pd

MARKETS = ("1x2", "totals", "btts", "team_totals")
MARKET_NAMES = {"1x2": "Match result", "totals": "Total goals", "btts": "Both teams to score",
                "team_totals": "Team goals"}
MARKET_ALIASES = {"ou25": "totals", "ou": "totals", "total": "totals"}

# pick styles = fair-odds range + how strongly form and model must agree
STYLES = {
    "safe":     {"min_odds": 1.15, "max_odds": 1.60, "min_model": 0.60, "min_form": 0.60},
    "balanced": {"min_odds": 1.25, "max_odds": 2.20, "min_model": 0.45, "min_form": 0.55},
    "bold":     {"min_odds": 1.60, "max_odds": 3.50, "min_model": 0.30, "min_form": 0.45},
}
DEFAULTS = {"window": 5, "style": "balanced", "form_weight": 0.6, "min_lift": 0.05,
            "shrink": 5.0, "markets": list(MARKETS), **STYLES["balanced"]}

# window weights: games against similar opponents count most, then the venue
# that matches the fixture
W_SIMILAR, W_VENUE, W_LAST, W_OTHER, W_H2H = 1.5, 1.25, 1.0, 0.5, 0.75


def resolve_opts(opts: dict | None) -> dict:
    """Defaults <- style preset <- explicit settings (None values ignored)."""
    opts = {k: v for k, v in (opts or {}).items() if v is not None}
    style = opts.get("style") or DEFAULTS["style"]
    if style not in STYLES:
        raise ValueError(f"style must be one of {', '.join(STYLES)}")
    o = {**DEFAULTS, **STYLES[style], **opts, "style": style}
    o["markets"] = [MARKET_ALIASES.get(m, m) for m in (o.get("markets") or MARKETS)]
    return o


# ---------------------------------------------------------------- history
class FormIndex:
    """Fast 'last n matches before date' lookups per team / venue / pair."""

    def __init__(self, matches: pd.DataFrame):
        m = matches.sort_values(["date", "match_id"]).reset_index(drop=True)
        self.date = m["date"].values.astype("datetime64[D]")
        self.home = m["home"].to_numpy()
        self.away = m["away"].to_numpy()
        self.gh = m["fthg"].to_numpy(int)
        self.ga = m["ftag"].to_numpy(int)
        self.neutral = m["neutral"].fillna(0).to_numpy(int) if "neutral" in m else np.zeros(len(m), int)
        allx, homex, awayx, pair = (defaultdict(list) for _ in range(4))
        for i, (h, a) in enumerate(zip(self.home, self.away)):
            allx[h].append(i); allx[a].append(i)
            homex[h].append(i); awayx[a].append(i)
            pair[frozenset((h, a))].append(i)
        conv = lambda d: {k: np.array(v, int) for k, v in d.items()}
        self.idx = {"all": conv(allx), "home": conv(homex), "away": conv(awayx)}
        self.pair = conv(pair)
        self._elo()

    def _elo(self) -> None:
        """Pre- and post-match Elo for both sides of every match, so the
        strength of any opponent *at the time* is known (no look-ahead)."""
        from footypred.features.ratings import Elo
        elo = Elo(k=20)
        n = len(self.home)
        self.elo_pre = np.zeros((n, 2))
        self.elo_post = np.zeros((n, 2))
        for i, (h, a) in enumerate(zip(self.home, self.away)):
            self.elo_pre[i] = elo.rating(h), elo.rating(a)
            elo.update(h, a, int(self.gh[i]), int(self.ga[i]), bool(self.neutral[i]))
            self.elo_post[i] = elo.rating(h), elo.rating(a)

    def rating(self, team: str, date) -> float:
        rows = self._before(self.idx["all"].get(team), date, 1)
        if not len(rows):
            return 1500.0
        i = rows[-1]
        return float(self.elo_post[i, 0 if self.home[i] == team else 1])

    def similar(self, team: str, opponent: str, date, n: int = 5,
                bands=(80.0, 160.0), lookback: int = 40) -> list[dict]:
        """`team`'s last n games against opponents rated (then) like
        `opponent` is rated now (within ±80 Elo, widened to ±160)."""
        target = self.rating(opponent, date)
        rows = self._before(self.idx["all"].get(team), date, lookback)
        for band in bands:
            keep = []
            for i in rows:
                opp_elo = self.elo_pre[i, 1 if self.home[i] == team else 0]
                if abs(opp_elo - target) <= band:
                    keep.append(i)
            if len(keep) >= 3:
                return [self._rec(i, team) for i in keep[-n:]]
        return []

    def _before(self, rows: np.ndarray | None, date, n: int) -> np.ndarray:
        if rows is None or not len(rows):
            return np.array([], int)
        cut = np.searchsorted(self.date[rows], np.datetime64(pd.Timestamp(date), "D"), "left")
        return rows[max(0, cut - n):cut]

    def window(self, team: str, kind: str, date, n: int = 5) -> list[dict]:
        """kind: 'all' | 'home' | 'away'. Records from `team`'s perspective."""
        rows = self._before(self.idx[kind].get(team), date, n)
        return [self._rec(i, team) for i in rows]

    def h2h(self, home: str, away: str, date, n: int = 5) -> list[dict]:
        rows = self._before(self.pair.get(frozenset((home, away))), date, n)
        return [self._rec(i, home) for i in rows]

    def _rec(self, i: int, team: str) -> dict:
        at_home = self.home[i] == team
        gf, ga = (self.gh[i], self.ga[i]) if at_home else (self.ga[i], self.gh[i])
        return {"date": str(self.date[i]), "opponent": self.away[i] if at_home else self.home[i],
                "venue": "N" if self.neutral[i] else ("H" if at_home else "A"),
                "gf": int(gf), "ga": int(ga),
                "result": "W" if gf > ga else ("D" if gf == ga else "L")}


def form_counts(recs: list[dict]) -> dict:
    n = len(recs)
    gf = np.array([r["gf"] for r in recs]); ga = np.array([r["ga"] for r in recs])
    c = lambda mask: int(mask.sum()) if n else 0
    return {
        "n": n, "w": c(gf > ga), "d": c(gf == ga), "l": c(gf < ga),
        "scored": c(gf > 0), "scored2": c(gf > 1), "scored3": c(gf > 2),
        "conceded": c(ga > 0), "conceded2": c(ga > 1), "conceded3": c(ga > 2),
        "clean_sheets": c(ga == 0), "failed_to_score": c(gf == 0),
        "btts": c((gf > 0) & (ga > 0)), "o15": c(gf + ga > 1), "o25": c(gf + ga > 2),
        "o35": c(gf + ga > 3),
        "gf_avg": float(gf.mean()) if n else None, "ga_avg": float(ga.mean()) if n else None,
        "results": [f"{r['result']} {r['gf']}-{r['ga']} {'v' if r['venue'] == 'H' else '@'} "
                    f"{r['opponent']}" for r in reversed(recs)],
    }


def profile(c: dict) -> list[str]:
    """Plain-language tags for a window (needs at least 3 games)."""
    n = c["n"]
    if n < 3:
        return []
    tags = []
    r = lambda k: c[k] / n
    if r("scored") >= 0.8:
        tags.append(f"scores often ({c['scored']}/{n})")
    elif r("scored") <= 0.4:
        tags.append(f"struggles to score ({c['scored']}/{n})")
    if r("scored2") >= 0.6:
        tags.append(f"scores 2+ regularly ({c['scored2']}/{n})")
    if r("clean_sheets") >= 0.6:
        tags.append(f"keeps clean sheets ({c['clean_sheets']}/{n})")
    elif r("conceded") >= 0.8:
        tags.append(f"concedes often ({c['conceded']}/{n})")
    if r("conceded2") >= 0.6:
        tags.append(f"concedes 2+ regularly ({c['conceded2']}/{n})")
    if r("o25") >= 0.8:
        tags.append(f"high-scoring games ({c['o25']}/{n} over 2.5)")
    elif r("o25") <= 0.2:
        tags.append(f"low-scoring games ({n - c['o25']}/{n} under 2.5)")
    if r("btts") >= 0.8:
        tags.append(f"BTTS in {c['btts']}/{n}")
    return tags


# ------------------------------------------------------------- candidates
@dataclass(frozen=True)
class Candidate:
    key: str
    market: str            # 1x2 | ou25 | btts | team_totals
    label: str             # with {home}/{away} placeholders
    model_key: str         # flat market key in the model probabilities
    negate: bool           # probability is 1 - model_key
    test_home_side: object  # f(gf, ga) on home-team-perspective records (and H2H)
    test_away_side: object  # f(gf, ga) on away-team-perspective records
    desc_home_side: str     # what a hit means in the home team's games
    desc_away_side: str     # ... in the away team's games
    desc_h2h: str           # ... in head-to-head meetings


def _goals(k: int, verb: str, under: bool) -> str:
    if not under:
        return f"{verb} {k + 1}+"
    if k == 0:
        return {"scored": "failed to score", "conceded": "kept a clean sheet"}[verb]
    return f"{verb} {k} or fewer"


def _candidates() -> list[Candidate]:
    both = lambda d: (d, d, d)
    C = [
        Candidate("home_win", "1x2", "{home} to win", "1x2:0", False,
                  lambda f, a: f > a, lambda f, a: f < a, "{home} won", "{away} lost", "{home} won"),
        Candidate("draw", "1x2", "Draw", "1x2:1", False,
                  lambda f, a: f == a, lambda f, a: f == a, *both("drawn")),
        Candidate("away_win", "1x2", "{away} to win", "1x2:2", False,
                  lambda f, a: f < a, lambda f, a: f > a, "{home} lost", "{away} won", "{away} won"),
    ]
    for k, line in ((1, "1.5"), (2, "2.5"), (3, "3.5")):
        mk = "o" + line.replace(".", "")
        C += [Candidate(f"over_{line}", "totals", f"Over {line} goals", mk, False,
                        lambda f, a, k=k: f + a > k, lambda f, a, k=k: f + a > k,
                        *both(f"{k + 1}+ goals in the game")),
              Candidate(f"under_{line}", "totals", f"Under {line} goals", mk, True,
                        lambda f, a, k=k: f + a <= k, lambda f, a, k=k: f + a <= k,
                        *both(f"{k} or fewer goals in the game"))]
    C += [
        Candidate("btts_yes", "btts", "Both teams to score", "btts", False,
                  lambda f, a: f > 0 and a > 0, lambda f, a: f > 0 and a > 0,
                  *both("both teams scored")),
        Candidate("btts_no", "btts", "BTTS — No", "btts", True,
                  lambda f, a: not (f > 0 and a > 0), lambda f, a: not (f > 0 and a > 0),
                  *both("at least one side failed to score")),
    ]
    for k, line in ((0, "0.5"), (1, "1.5"), (2, "2.5")):
        mk = line.replace(".", "")
        for under in (False, True):
            word = "under" if under else "over"
            # home team goals: home-side records count its goals (f); away-side
            # records count the away team's concessions (a); H2H from home view
            th = (lambda f, a, k=k: f <= k) if under else (lambda f, a, k=k: f > k)
            ta = (lambda f, a, k=k: a <= k) if under else (lambda f, a, k=k: a > k)
            C.append(Candidate(f"home_{word}_{line}", "team_totals",
                               "{home} " + f"{word} {line} goals", f"h_o{mk}", under, th, ta,
                               "{home} " + _goals(k, "scored", under),
                               "{away} " + _goals(k, "conceded", under),
                               "{home} " + _goals(k, "scored", under)))
            th2 = (lambda f, a, k=k: a <= k) if under else (lambda f, a, k=k: a > k)
            ta2 = (lambda f, a, k=k: f <= k) if under else (lambda f, a, k=k: f > k)
            C.append(Candidate(f"away_{word}_{line}", "team_totals",
                               "{away} " + f"{word} {line} goals", f"a_o{mk}", under, th2, ta2,
                               "{home} " + _goals(k, "conceded", under),
                               "{away} " + _goals(k, "scored", under),
                               "{away} " + _goals(k, "scored", under)))
    return C


CANDIDATES = _candidates()


def _model_prob(probs: dict, c: Candidate) -> float | None:
    """None when the model output lacks this line (e.g. a bundle trained
    before total O/U 1.5/3.5 existed): the selection is then skipped."""
    if c.model_key.startswith("1x2:"):
        p = float(np.asarray(probs["1x2"]).ravel()[int(c.model_key[-1])])
    elif c.model_key not in probs:
        return None
    else:
        p = float(np.asarray(probs[c.model_key]).ravel()[0])
    return 1 - p if c.negate else p


# ----------------------------------------------------------------- engine
def gather_windows(index: FormIndex, home: str, away: str, date, n: int = 5) -> dict:
    return {
        "home_last": index.window(home, "all", date, n),
        "home_home": index.window(home, "home", date, n),
        "home_away": index.window(home, "away", date, n),
        "away_last": index.window(away, "all", date, n),
        "away_away": index.window(away, "away", date, n),
        "away_home": index.window(away, "home", date, n),
        "home_similar": index.similar(home, away, date, n),
        "away_similar": index.similar(away, home, date, n),
        "h2h": index.h2h(home, away, date, n),
    }


# (window key, side, weight, label)
WINDOW_SPEC = [("home_similar", "home", W_SIMILAR, "{home}'s last {n} vs teams rated like {away}"),
               ("away_similar", "away", W_SIMILAR, "{away}'s last {n} vs teams rated like {home}"),
               ("home_home", "home", W_VENUE, "{home}'s last {n} home games"),
               ("home_last", "home", W_LAST, "{home}'s last {n} games"),
               ("home_away", "home", W_OTHER, "{home}'s last {n} away games"),
               ("away_away", "away", W_VENUE, "{away}'s last {n} away games"),
               ("away_last", "away", W_LAST, "{away}'s last {n} games"),
               ("away_home", "away", W_OTHER, "{away}'s last {n} home games"),
               ("h2h", "h2h", W_H2H, "last {n} meetings")]


def base_rates(matches: pd.DataFrame, min_league_games: int = 200) -> dict:
    """How often each selection lands in a typical game, per league (and
    overall): the yardstick for whether a pick is notable for *this* match."""
    gh, ga = matches["fthg"].to_numpy(int), matches["ftag"].to_numpy(int)
    lg = matches["league"].to_numpy()
    out = {}
    for c in CANDIDATES:
        hits = np.array([bool(c.test_home_side(h, a)) for h, a in zip(gh, ga)])
        out.setdefault("_all", {})[c.key] = float(hits.mean()) if len(hits) else 0.5
        for league in np.unique(lg):
            m = lg == league
            if m.sum() >= min_league_games:
                out.setdefault(league, {})[c.key] = float(hits[m].mean())
    return out


def score_candidates(windows: dict, probs: dict, home: str, away: str, opts: dict | None = None,
                     neutral: bool = False, base: dict | None = None) -> list[dict]:
    o = resolve_opts(opts)
    out = []
    for c in CANDIDATES:
        if _model_prob(probs, c) is None:
            continue
        hits_w = n_w = 0.0
        evidence = []
        for key, side, w, label in WINDOW_SPEC:
            recs = windows[key]
            if not recs or (key == "h2h" and len(recs) < 2):
                continue
            if neutral and key in ("home_home", "home_away", "away_away", "away_home"):
                w = W_OTHER                     # venue matters less at a neutral ground
            test = c.test_away_side if side == "away" else c.test_home_side
            desc = {"home": c.desc_home_side, "away": c.desc_away_side, "h2h": c.desc_h2h}[side]
            hits = sum(bool(test(r["gf"], r["ga"])) for r in recs)
            hits_w += w * hits
            n_w += w * len(recs)
            evidence.append({"window": label.format(home=home, away=away, n=len(recs)),
                             "event": desc.format(home=home, away=away),
                             "hits": hits, "n": len(recs), "weight": w})
        p = _model_prob(probs, c)
        form = hits_w / n_w if n_w else None
        shrunk = (hits_w + o["shrink"] * p) / (n_w + o["shrink"]) if n_w else p
        score = o["form_weight"] * shrunk + (1 - o["form_weight"]) * p
        typical = (base or {}).get(c.key)
        lift = None if typical is None else p - typical
        odds = 1 / max(p, 1e-9)
        fails = [name for name, ok in (
            ("form", form is not None and form >= o["min_form"]),
            ("model", p >= o["min_model"]),
            ("too short", round(odds, 2) >= o["min_odds"]),
            ("too long", round(odds, 2) <= o.get("max_odds", 99.0)),
            ("ordinary", lift is None or lift >= o["min_lift"]),
            ("market off", c.market in o["markets"])) if not ok]
        eligible = not fails
        if form is None:
            agree = "no form data"
        elif abs(form - p) <= 0.15:
            agree = "form and model agree"
        elif form > p:
            agree = "form stronger than model"
        else:
            agree = "model stronger than form"
        out.append({"key": c.key, "market": c.market,
                    "label": c.label.format(home=home, away=away),
                    "model_prob": round(p, 4), "form_rate": None if form is None else round(form, 4),
                    "score": round(score, 4), "fair_odds": round(1 / max(p, 1e-9), 2),
                    "typical": None if typical is None else round(typical, 4),
                    "lift": None if lift is None else round(lift, 4),
                    "eligible": bool(eligible), "fails": fails, "agreement": agree,
                    "evidence": evidence})
    out.sort(key=lambda d: (d["eligible"], d["score"]), reverse=True)
    return out


def form_check(index: FormIndex, home: str, away: str, date, probs: dict,
               opts: dict | None = None, neutral: bool = False, base: dict | None = None) -> dict:
    """Everything the UI needs: windows, counts, profiles, ranked picks."""
    o = resolve_opts(opts)
    win = gather_windows(index, home, away, date, int(o["window"]))
    counts = {k: form_counts(v) for k, v in win.items()}
    ranked = score_candidates(win, probs, home, away, o, neutral, base)
    allowed = set(o["markets"])
    ranked.sort(key=lambda d: (d["eligible"], d["score"]), reverse=True)
    best = ranked[0] if ranked and ranked[0]["eligible"] else None
    best_by_market = {}
    for mk in MARKETS:
        group = [r for r in ranked if r["market"] == mk]
        if group:
            top = max(group, key=lambda d: (d["eligible"] or mk not in allowed, d["score"]))
            best_by_market[mk] = {**top, "market_name": MARKET_NAMES[mk]}
    profiles = {
        "home": {"at home": profile(counts["home_home"]), "overall": profile(counts["home_last"]),
                 "away": profile(counts["home_away"]),
                 "vs similar": profile(counts["home_similar"])},
        "away": {"away": profile(counts["away_away"]), "overall": profile(counts["away_last"]),
                 "at home": profile(counts["away_home"]),
                 "vs similar": profile(counts["away_similar"])},
    }
    # lopsided match: the favourite's safe lines are too short -> say so
    too_short = next((r for r in ranked if r["fails"] == ["too short"]), None)
    p1 = np.asarray(probs["1x2"]).ravel()
    fav = int(np.argmax([p1[0], p1[2]]))
    gap = {"favourite": (home, away)[fav], "win_prob": round(float(max(p1[0], p1[2])), 4),
           "elo_gap": round(index.rating(home, date) - index.rating(away, date), 1),
           "lopsided": bool(max(p1[0], p1[2]) >= 0.62)}
    follow_ups = follow_up_picks(ranked, best)
    by_style = {}
    style_free = {k: v for k, v in (opts or {}).items()
                  if k not in ("style", "min_odds", "max_odds", "min_model", "min_form")}
    for name in STYLES:
        if name == o["style"]:
            by_style[name] = _slim(best) if best else None
            continue
        alt = score_candidates(win, probs, home, away, {**style_free, "style": name}, neutral, base)
        top = alt[0] if alt and alt[0]["eligible"] else None
        by_style[name] = _slim(top) if top else None
    # model leans one way, recent form clearly doesn't (>= 10 points lower)
    conflicts = [r for r in ranked if r["form_rate"] is not None and r["model_prob"] >= 0.5
                 and r["form_rate"] < o["min_form"] and r["form_rate"] <= r["model_prob"] - 0.10
                 and r["market"] != "1x2"][:3]
    return {"window": int(o["window"]), "counts": counts, "profiles": profiles,
            "best_pick": best, "top_picks": [r for r in ranked if r["eligible"]][:5],
            "follow_ups": follow_ups, "by_style": by_style,
            "too_short": too_short, "gap": gap,
            "best_by_market": best_by_market,
            "conflicts": conflicts, "candidates": ranked,
            "settings": {k: o[k] for k in ("style", "form_weight", "min_form", "min_model",
                                           "min_odds", "max_odds", "min_lift", "markets")},
            "reason": _reason(best, counts, profiles, home, away, too_short, gap)}


def _group(c: dict) -> str:
    """Market family of a pick: 1X2, totals, BTTS, or one team's goals."""
    if c["market"] == "team_totals":
        return "team_" + c["key"].split("_", 1)[0]
    return c["market"]


def _slim(c: dict, evidence: int = 2) -> dict:
    out = {k: c[k] for k in ("key", "market", "label", "model_prob", "form_rate", "fair_odds",
                             "score", "agreement", "lift", "typical") if k in c}
    out["evidence"] = sorted(c.get("evidence") or [], key=lambda e: -e["weight"])[:evidence]
    return out


WHY_NOT = {"form": "recent form below this style's bar", "model": "model below this style's bar",
           "too short": "odds below this style's range", "too long": "odds above this style's range",
           "ordinary": "hardly above a typical game"}


def follow_up_picks(ranked: list[dict], best: dict | None, n: int = 4) -> list[dict]:
    """The next options after the best pick, from different markets first
    (one per market family), then the next-best of any market.

    Eligible picks (form and model both back them, odds fit the style) come
    first. If there are fewer than n, the list is topped up with *leans*:
    selections that miss one of the style's rules but are still backed by
    the model and recent form at 40%+, marked lean=True with the reason."""
    def diverse(pool, used, k):
        out = []
        for c in pool:                                # a new market family each
            if _group(c) not in used:
                out.append(c)
                used.add(_group(c))
            if len(out) == k:
                return out
        for c in pool:                                # then by score
            if len(out) == k:
                break
            if c not in out:
                out.append(c)
        return out
    skip = best["key"] if best else None
    used = {_group(best)} if best else set()
    strict = diverse([c for c in ranked if c["eligible"] and c["key"] != skip], used, n)
    strict.sort(key=lambda c: -c["score"])
    out = [_slim(c) for c in strict]
    if len(out) < n:
        # closest to the style first: fewest rules missed, "odds too short" last
        near = lambda c: (len(c["fails"]), "too short" in c["fails"], -c["score"])
        soft = sorted([c for c in ranked if not c["eligible"] and "market off" not in c["fails"]
                       and c["model_prob"] >= 0.40 and (c["form_rate"] is None or c["form_rate"] >= 0.40)],
                      key=near)
        for c in sorted(diverse(soft, set(used) | {_group(x) for x in strict}, n - len(out)), key=near):
            out.append({**_slim(c), "lean": True,
                        "why": "; ".join(WHY_NOT.get(f, f) for f in c["fails"])})
    return out


def _reason(best, counts, profiles, home, away, too_short=None, gap=None) -> str:
    short = ""
    if too_short is not None:
        short = (f"{too_short['label']} ({100 * too_short['model_prob']:.0f}%, odds "
                 f"{too_short['fair_odds']:.2f}) is too short to be worth it"
                 + (" in this lopsided match" if gap and gap["lopsided"] else "") + "; ")
    if best is None:
        return (short + "No clear pick: no selection is backed by both recent form "
                "and the model within the chosen odds range.")
    bits = []
    hp = profiles["home"]["at home"] or profiles["home"]["overall"]
    ap = profiles["away"]["away"] or profiles["away"]["overall"]
    if hp:
        bits.append(f"{home} at home: {', '.join(hp[:3])}")
    if ap:
        bits.append(f"{away} away: {', '.join(ap[:3])}")
    top = sorted(best["evidence"], key=lambda e: -e["weight"])[:3]
    ev = "; ".join(f"{e['event']} in {e['hits']}/{e['n']} of {e['window']}" for e in top)
    typ = (f" vs {100 * best['typical']:.0f}% in a typical game"
           if best.get("typical") is not None else "")
    return (short + f"{best['label']}: {ev}. "
            + (" · ".join(bits) + "." if bits else "")
            + f" Model {100 * best['model_prob']:.0f}%{typ}, form {100 * best['form_rate']:.0f}%"
            f" ({best['agreement']}).")


# ---------------------------------------------------------------- backtest
def eval_matches(db_matches: pd.DataFrame, eval_preds: dict, eval_seasons) -> pd.DataFrame:
    """Rows behind the stored out-of-fold predictions (same order)."""
    if "match_id" in eval_preds:
        m = db_matches.set_index("match_id").loc[list(eval_preds["match_id"])].reset_index()
    else:  # older bundles: rebuild the trainer's ordering
        m = db_matches.sort_values(["date", "match_id"])
        m = m[m["season"].isin(list(eval_seasons))].reset_index(drop=True)
    if len(m) != len(eval_preds["y_h"]) or not (
            (m["fthg"].to_numpy() == eval_preds["y_h"]).all()
            and (m["ftag"].to_numpy() == eval_preds["y_a"]).all()):
        raise ValueError("stored evaluation predictions don't line up with the database; "
                         "retrain with `footy train`")
    return m


def backtest(index: FormIndex, matches: pd.DataFrame, probs: dict, opts: dict | None = None,
             mask: np.ndarray | None = None, base: dict | None = None,
             keep_rows: bool = False) -> dict:
    """Best pick per match from pre-match form + out-of-fold model
    probabilities; reports how often picks landed vs what was claimed.
    keep_rows: also return the per-match picks (out["rows"])."""
    o = resolve_opts(opts)
    cand = {c.key: c for c in CANDIDATES}
    rows = []
    rng = range(len(matches)) if mask is None else np.where(mask)[0]
    for i in rng:
        r = matches.iloc[i]
        win = gather_windows(index, r["home"], r["away"], r["date"], int(o["window"]))
        p_i = {k: (v[i] if np.ndim(v) == 1 else v[i]) for k, v in probs.items()}
        b = (base or {}).get(r["league"]) or (base or {}).get("_all")
        ranked = score_candidates(win, p_i, r["home"], r["away"], o, bool(r.get("neutral") or 0), b)

        best = ranked[0] if ranked and ranked[0]["eligible"] else None
        if best is None:
            rows.append({"pick": None})
            continue
        hit = bool(cand[best["key"]].test_home_side(int(r["fthg"]), int(r["ftag"])))
        rows.append({"pick": best["key"], "label": best["label"], "market": best["market"],
                     "hit": hit, "model": best["model_prob"], "form": best["form_rate"],
                     "score": best["score"], "odds": best["fair_odds"]})
    df = pd.DataFrame(rows)
    picked = df[df["pick"].notna()] if "pick" in df else df
    out = {"matches": len(df), "picks": int(len(picked)),
           "coverage": float(len(picked) / max(len(df), 1))}
    if len(picked):
        out.update({"hit_rate": float(picked["hit"].mean()),
                    "mean_model": float(picked["model"].mean()),
                    "mean_form": float(picked["form"].mean()),
                    "mean_odds": float(picked["odds"].mean()),
                    "by_market": {k: {"n": int(len(g)), "hit_rate": float(g["hit"].mean()),
                                      "mean_model": float(g["model"].mean()),
                                      "mean_form": float(g["form"].mean())}
                                  for k, g in picked.groupby("market")},
                    "by_pick": picked["pick"].value_counts().head(6).to_dict()})
    if keep_rows:
        out["rows"] = rows
    return out


def form_reliability(index: FormIndex, matches: pd.DataFrame, n: int = 5, limit: int | None = None,
                     bins=(0.0, 0.4, 0.6, 0.8, 1.01)) -> list[dict]:
    """How often selections actually landed, grouped by their raw last-n
    form rate (are 5/5 streaks really 100%?)."""
    recs = []
    rows = matches if limit is None else matches.tail(limit)
    for _, r in rows.iterrows():
        win = gather_windows(index, r["home"], r["away"], r["date"], n)
        dummy = {"1x2": np.array([1 / 3] * 3), **{k: 0.5 for k in
                 ("o15", "o25", "o35", "btts", "h_o05", "h_o15", "h_o25", "a_o05", "a_o15",
                  "a_o25")}}
        for c in score_candidates(win, dummy, r["home"], r["away"], {"min_odds": 0}):
            if c["form_rate"] is None:
                continue
            hit = bool({x.key: x for x in CANDIDATES}[c["key"]].test_home_side(
                int(r["fthg"]), int(r["ftag"])))
            recs.append((c["form_rate"], hit))
    a = np.array(recs, float)
    out = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (a[:, 0] >= lo) & (a[:, 0] < hi)
        if m.any():
            out.append({"form_from": lo, "form_to": min(hi, 1.0), "n": int(m.sum()),
                        "mean_form": float(a[m, 0].mean()), "hit_rate": float(a[m, 1].mean())})
    return out
