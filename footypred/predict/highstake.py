"""High stake mode: picks at odds of 1.70 and up, and an upset factor for
clubs with an American owner (or largest investor) or a betting-company
sponsor.

Which clubs are flagged comes from config/club_flags.csv (edit it to add or
remove clubs). How much the flags count is the user's slider (0-100%).

How the factor works, for a match where at least one side is flagged:

1. Each team's recent record (its last 40 matches) is compared with what
   pre-match Elo ratings expected: how often it failed to win as the
   favourite, and how often it avoided defeat as the underdog. Each is a
   ratio to the expected count, pulled towards 1 when the sample is small.
2. The match's upset ratio is the geometric mean of the favourite's ratio
   and the underdog's ratio (kept between 0.5 and 2).
3. The favourite's chance of not winning is multiplied by
   1 + slider x flag weight x (upset ratio - 1). The flag weight is 0.5 per
   flag (American owner, betting sponsor, on either side), at most 1.
4. The score grid is reweighted: favourite-win scorelines scaled down,
   draws and underdog wins scaled up (or the other way round when the
   teams' upset ratio is below 1), so every market moves consistently.

At 0% (or with no flagged club) nothing changes.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

MIN_ODDS = 1.70
COUNTED_STAKES = {"majority", "joint", "largest investor"}
WINDOW = 40                 # each team's last 40 matches
PRIOR = 3.0                 # pseudo-events pulling each ratio towards 1
RATIO_RANGE = (0.5, 2.0)
NON_WIN_RANGE = (0.02, 0.90)
WARMUP = 10                 # both teams need 10 earlier matches before a match is used
GAP_BINS = np.array([0, 25, 50, 75, 100, 150, 200, 250, 300, 400, np.inf])


@dataclass
class ClubFlags:
    team: str
    league: str = ""
    owner: str = ""
    owner_stake: str = ""
    owner_since: str = ""
    sponsor: str = ""
    sponsor_deal: str = ""
    sponsor_season: str = ""
    note: str = ""

    @property
    def american(self) -> bool:
        return bool(self.owner) and self.owner_stake in COUNTED_STAKES

    @property
    def betting(self) -> bool:
        return bool(self.sponsor)

    @property
    def count(self) -> int:
        return int(self.american) + int(self.betting)

    def alerts(self) -> list[str]:
        out = []
        if self.american:
            kind = {"majority": "American owner", "joint": "American co-owner",
                    "largest investor": "American largest investor"}[self.owner_stake]
            out.append(f"{kind}: {self.owner}")
        if self.betting:
            when = "" if self.sponsor_season in ("", "2026-27") else f", {self.sponsor_season}"
            deal = f" ({self.sponsor_deal}{when})" if self.sponsor_deal or when else ""
            out.append(f"Betting sponsor: {self.sponsor}{deal}")
        return out

    def to_dict(self) -> dict:
        return {**asdict(self), "american": self.american, "betting": self.betting,
                "alerts": self.alerts()}


def flags_path(cfg) -> Path | None:
    from footypred.config import PROJECT_ROOT
    own = ((cfg.raw.get("high_stake") or {}).get("flags_file") if cfg is not None else None)
    tries = []
    if own:
        own = Path(own).expanduser()
        tries.append(own if own.is_absolute() else Path(cfg.paths.root) / own)
    if cfg is not None:
        tries.append(Path(cfg.paths.root) / "config" / "club_flags.csv")
    tries.append(PROJECT_ROOT / "config" / "club_flags.csv")
    return next((p for p in tries if p.exists()), None)


def _strict(known: list[str], aliases: dict | None):
    """Match a name from the flags file to a team in the data: exact, then
    the same name ignoring case/accents, then a known alias. Never fuzzy -
    a wrong match would put an alert on the wrong club."""
    from footypred.data.names import BUILTIN_ALIASES, _norm, canonical
    norm = {_norm(t): t for t in known}
    al = {**BUILTIN_ALIASES, **(aliases or {})}

    def resolve(name: str) -> str:
        if name in known:
            return name
        if _norm(name) in norm:
            return norm[_norm(name)]
        c = canonical(name, al)
        return c if c in known else name
    return resolve


def load_flags(path: Path | str | None, known: list[str] | None = None,
               aliases: dict | None = None) -> dict[str, ClubFlags]:
    """team (as named in your data) -> ClubFlags. Rows starting with # are skipped."""
    if not path or not Path(path).exists():
        return {}
    resolve = _strict(known, aliases) if known else (lambda s: s)
    out = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            team = (row.get("team") or "").strip()
            if not team or team.startswith("#"):
                continue
            get = lambda k: (row.get(k) or "").strip()            # noqa: E731
            fl = ClubFlags(team=resolve(team), league=get("league"), owner=get("american_owner"),
                           owner_stake=get("owner_stake").lower(), owner_since=get("owner_since"),
                           sponsor=get("betting_sponsor"), sponsor_deal=get("sponsor_deal"),
                           sponsor_season=get("sponsor_season"), note=get("note"))
            out[fl.team] = fl
    return out


def alerts_for(flags: dict[str, ClubFlags], team: str) -> dict | None:
    fl = flags.get(team)
    return fl.to_dict() if fl and fl.count else None


class UpsetProfiles:
    """How often each team's matches went against the favourite, compared
    with what pre-match Elo ratings expected. Built on the pick engine's
    FormIndex (same matches, same Elo walk, nothing after each kickoff)."""

    def __init__(self, index, home_adv: float = 60.0):
        self.index = index
        n = len(index.home)
        d = index.elo_pre[:, 0] - index.elo_pre[:, 1] + np.where(index.neutral > 0, 0.0, home_adv)
        self.home_fav = d >= 0
        gap = np.abs(d)
        fav_g = np.where(self.home_fav, index.gh, index.ga)
        dog_g = np.where(self.home_fav, index.ga, index.gh)
        self.fav_won = fav_g > dog_g
        self.dog_won = dog_g > fav_g
        # how many earlier matches each side had: early ratings are guesses
        prev = np.zeros((n, 2), int)
        seen: dict = {}
        for i, (h, a) in enumerate(zip(index.home, index.away)):
            prev[i] = seen.get(h, 0), seen.get(a, 0)
            seen[h] = seen.get(h, 0) + 1
            seen[a] = seen.get(a, 0) + 1
        self.warm = (prev >= WARMUP).all(axis=1)
        # P(favourite wins) by rating gap, from the warmed-up matches
        b = np.clip(np.searchsorted(GAP_BINS, gap, side="right") - 1, 0, len(GAP_BINS) - 2)
        rate = np.full(len(GAP_BINS) - 1, np.nan)
        for k in range(len(rate)):
            m = self.warm & (b == k)
            rate[k] = (self.fav_won[m].sum() + 1) / (m.sum() + 2)
        rate = np.maximum.accumulate(np.nan_to_num(rate, nan=0.45))   # bigger gap, never lower
        self.p_fav_win = rate[b]
        self.rate_by_gap = rate

    def profile(self, team: str, date) -> dict:
        rows = self.index._before(self.index.idx["all"].get(team), date, WINDOW)
        rows = rows[self.warm[rows]] if len(rows) else rows
        is_home = self.index.home[rows] == team
        fav = np.where(is_home, self.home_fav[rows], ~self.home_fav[rows])
        f, u = rows[fav], rows[~fav]
        slips = int((~self.fav_won[f]).sum())                  # favourite didn't win
        slips_exp = float((1 - self.p_fav_win[f]).sum())
        lost = int(self.dog_won[f].sum())
        bites = int((~self.fav_won[u]).sum())                  # underdog didn't lose
        bites_exp = float((1 - self.p_fav_win[u]).sum())
        won = int(self.dog_won[u].sum())
        return {"team": team, "games": int(len(rows)),
                "fav_games": int(len(f)), "fav_slips": slips, "fav_slips_expected": round(slips_exp, 1),
                "fav_lost": lost,
                "dog_games": int(len(u)), "dog_bites": bites, "dog_bites_expected": round(bites_exp, 1),
                "dog_won": won,
                "slip_ratio": round((slips + PRIOR) / (slips_exp + PRIOR), 3),
                "bite_ratio": round((bites + PRIOR) / (bites_exp + PRIOR), 3)}


def _outcomes(grid: np.ndarray) -> list[float]:
    i, j = np.indices(grid.shape)
    return [float(grid[i > j].sum()), float(grid[i == j].sum()), float(grid[i < j].sum())]


def adjust(grid: np.ndarray, home: str, away: str, flags: dict[str, ClubFlags],
           profiles: UpsetProfiles | None, factor: float, date) -> tuple[np.ndarray, dict]:
    """Reweight a score grid for the owner/sponsor factor. Returns the new
    grid and what was done (for the page)."""
    grid = np.asarray(grid, float)
    before = _outcomes(grid)
    home_fav = before[0] >= before[2]
    fav, dog = (home, away) if home_fav else (away, home)
    fl = {t: flags[t] for t in (home, away) if t in flags and flags[t].count}
    n_flags = sum(f.count for f in fl.values())
    weight = min(1.0, 0.5 * n_flags)
    factor = float(min(max(factor, 0.0), 1.0))
    lam = factor * weight
    info = {"mode": "high", "factor": round(factor, 2), "flags": n_flags, "flag_weight": weight,
            "flagged": {t: f.alerts() for t, f in fl.items()}, "favourite": fav, "underdog": dog,
            "before": [round(x, 4) for x in before], "after": [round(x, 4) for x in before],
            "applied": False, "ratio": None, "profiles": {}}
    if profiles is not None:
        pf, pu = profiles.profile(fav, date), profiles.profile(dog, date)
        ratio = float(np.clip(np.sqrt(pf["slip_ratio"] * pu["bite_ratio"]), *RATIO_RANGE))
        info.update(profiles={"favourite": pf, "underdog": pu}, ratio=round(ratio, 3))
    else:
        ratio = 1.0
    if not n_flags:
        info["text"] = "Neither club is on the American-owner / betting-sponsor list, so the factor doesn't apply."
        return grid, info
    if lam == 0:
        info["text"] = "The owner & sponsor factor is at 0%, so the model's numbers are unchanged."
        return grid, info
    i, j = np.indices(grid.shape)
    fav_win = (i > j) if home_fav else (i < j)
    p_fw = float(grid[fav_win].sum())
    p_nw = 1.0 - p_fw
    new_nw = float(np.clip(p_nw * (1 + lam * (ratio - 1)), *NON_WIN_RANGE))
    out = grid.copy()
    if p_fw > 0 and p_nw > 0:
        out[fav_win] *= (1 - new_nw) / p_fw
        out[~fav_win] *= new_nw / p_nw
        out /= out.sum()
    after = _outcomes(out)
    info.update(after=[round(x, 4) for x in after], applied=True, lam=round(lam, 3))
    if ratio >= 1.03:
        record = f"have had more upsets than their ratings expected (upset ratio {ratio:.2f})"
    elif ratio <= 0.97:
        record = f"have had fewer upsets than their ratings expected (upset ratio {ratio:.2f})"
    else:
        record = (f"have had about as many upsets as their ratings expected (upset ratio {ratio:.2f}), "
                  "so the factor barely moves this match")
    fmt = ".1%" if round(p_nw * 100) == round(new_nw * 100) else ".0%"
    info["text"] = (f"{fav} and {dog} {record}. With the factor at {factor:.0%} and {n_flags} "
                    f"flag{'s' if n_flags != 1 else ''}, {fav}'s chance of not winning goes from "
                    f"{p_nw:{fmt}} to {new_nw:{fmt}}.")
    return out, info


def extra_probs(grid: np.ndarray) -> dict[str, float]:
    """Handicap +0.5 / +1.5 for each side and BTTS + over 2.5, off the grid."""
    g = np.asarray(grid, float)
    i, j = np.indices(g.shape)
    return {"hcp_h05": float(g[i >= j].sum()), "hcp_h15": float(g[i - j >= -1].sum()),
            "hcp_a05": float(g[j >= i].sum()), "hcp_a15": float(g[j - i >= -1].sum()),
            "btts_o25": float(g[(i > 0) & (j > 0) & (i + j > 2)].sum())}
