"""Club owner and sponsor as model features (categorical, one-hot, dated).

Two categorical variables per side (h_ = home team, a_ = away team):

    owner     us_majority | us_joint | us_largest | other | unknown
    sponsor   betting | none | unknown

Each category becomes its own 0/1 column (one-hot encoding), so every
model can use it: the Poisson GLM gets a coefficient per category, the
tree models can split on it. "unknown" is a category of its own, so a
club with missing data is never mistaken for one without an owner or
sponsor.

Where the values come from (config/club_flags.csv):

* owner: an American majority owner / co-owner / largest investor counts
  from owner_since when the file gives it; before that date the club had
  another owner ("other"). Without a date the current owner is taken to
  have held the club for the whole history. Minority stakes and
  unfinished sales count as "other".
* sponsor: a listed betting-company deal (on or off the shirt, this season
  or last) marks the club "betting". The file has no sponsorship history,
  so the deal is treated as a trait of the club across seasons.
* a club that isn't in the file is "other" / "none" when its competition
  was researched (the file lists at least one club from it) and
  "unknown" otherwise.

Owner *names* are deliberately not encoded: nearly every name belongs to
one club, so one-hot names would be a second team identifier (the ratings
already describe each team) and target-encoding them would leak results
into the features.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

OWNER_CATS = ("us_majority", "us_joint", "us_largest", "other", "unknown")
SPONSOR_CATS = ("betting", "none", "unknown")
STAKE_CAT = {"majority": "us_majority", "joint": "us_joint", "largest investor": "us_largest"}
PREFIXES = ("h_own_", "a_own_", "h_spn_", "a_spn_")


def columns() -> list[str]:
    return ([f"{p}_own_{c}" for p in ("h", "a") for c in OWNER_CATS]
            + [f"{p}_spn_{c}" for p in ("h", "a") for c in SPONSOR_CATS])


def is_club_column(name: str) -> bool:
    return name.startswith(PREFIXES)


def _since(v: str) -> np.datetime64 | None:
    v = (v or "").strip()
    if not v:
        return None
    try:
        t = pd.Timestamp(v + ("-01-01" if len(v) == 4 else "-01" if len(v) == 7 else ""))
    except ValueError:
        return None
    return np.datetime64(t.date(), "D")


class ClubCategories:
    """team -> owner / sponsor category on a date (picklable: plain dicts)."""

    def __init__(self, flags: dict, researched: set[str] | None = None):
        self.owner: dict[str, tuple[str, np.datetime64 | None]] = {}
        self.sponsor: dict[str, str] = {}
        self.researched = set(researched) if researched is not None else \
            {f.league for f in flags.values() if getattr(f, "league", "")}
        for team, f in flags.items():
            cat = STAKE_CAT.get(f.owner_stake) if f.owner else None
            self.owner[team] = (cat, _since(f.owner_since)) if cat else ("other", None)
            self.sponsor[team] = "betting" if f.betting else "none"

    def owner_category(self, team: str, league: str, date) -> str:
        if team not in self.owner:
            return "other" if league in self.researched else "unknown"
        cat, since = self.owner[team]
        if since is not None and np.datetime64(pd.Timestamp(date).date(), "D") < since:
            return "other"                          # before the American takeover
        return cat

    def sponsor_category(self, team: str, league: str) -> str:
        if team not in self.sponsor:
            return "none" if league in self.researched else "unknown"
        return self.sponsor[team]

    def encode(self, team: str, league: str, date, side: str) -> dict[str, float]:
        o, s = self.owner_category(team, league, date), self.sponsor_category(team, league)
        out = {f"{side}_own_{c}": float(c == o) for c in OWNER_CATS}
        out.update({f"{side}_spn_{c}": float(c == s) for c in SPONSOR_CATS})
        return out


def load(cfg, db) -> ClubCategories:
    """Categories from the club file (config/club_flags.csv)."""
    from footypred.predict import highstake
    return ClubCategories(highstake.load_flags(highstake.flags_path(cfg), db.teams(),
                                               db.load_aliases()))


def importance(importances: dict, models: dict, fcols: list[str]) -> dict:
    """What a trained model makes of the owner / sponsor columns: their share
    of the gradient-boosting gain (goal model and each market model) and the
    Poisson GLM's coefficients per category (on standardised inputs)."""
    fcols = list(fcols)
    cols = [c for c in fcols if is_club_column(c)]
    if not cols:
        return {}
    out = {"columns": cols, "gain_share": {}, "glm": {}}
    for market, imp in (importances or {}).items():
        out["gain_share"][market] = round(float(sum(imp.get(c, 0.0) for c in cols)), 5)
    glm = (models or {}).get("poisson")
    if glm is not None and getattr(glm, "models", None):
        for tgt, name in (("y_h", "home goals"), ("y_a", "away goals")):
            pipe = glm.models[tgt]
            imputer, reg = pipe[0], pipe[-1]
            # the imputer drops all-empty columns: coefficients follow the kept ones
            kept = [c for c, st in zip(fcols, imputer.statistics_) if not np.isnan(st)]
            coef = dict(zip(kept, np.ravel(reg.coef_)))
            out["glm"][name] = {c: round(float(coef.get(c, 0.0)), 5) for c in cols}
    return out
