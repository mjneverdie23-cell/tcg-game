"""Online team ratings, updated match by match (leakage-safe by design:
read the pre-match value, then update with the result).

* Elo with goal-margin multiplier (World Football Elo style)
* Online Poisson attack/defence ratings: stochastic gradient ascent on
  the Poisson log-likelihood, giving pre-match expected goals directly.
  Run twice: on goals, and on a goals/xG blend (more stable signal).
"""

from __future__ import annotations

import math
from collections import defaultdict


class Elo:
    def __init__(self, k: float = 20.0, home_adv: float = 60.0, init: float = 1500.0):
        self.k, self.home_adv, self.init = k, home_adv, init
        self.delta: dict[str, float] = defaultdict(float)   # rating - init (picklable)

    def rating(self, team: str) -> float:
        return self.init + self.delta.get(team, 0.0)

    def expected(self, home: str, away: str, neutral: bool = False) -> float:
        d = self.rating(home) - self.rating(away) + (0 if neutral else self.home_adv)
        return 1.0 / (1.0 + 10 ** (-d / 400))

    def update(self, home: str, away: str, gh: int, ga: int, neutral: bool = False) -> None:
        exp = self.expected(home, away, neutral)
        score = 1.0 if gh > ga else (0.5 if gh == ga else 0.0)
        gd = abs(gh - ga)
        mult = 1.0 if gd <= 1 else (1.5 if gd == 2 else (11 + gd) / 8)
        delta = self.k * mult * (score - exp)
        self.delta[home] += delta
        self.delta[away] -= delta


class PoissonRatings:
    """log λ_home = mu_L + home_L + att_h - def_a ; log λ_away = mu_L + att_a - def_h"""

    def __init__(self, lr: float = 0.06, league_lr: float = 0.004,
                 init_mu: float = math.log(1.35), init_home: float = 0.2):
        self.lr, self.league_lr = lr, league_lr
        self.att: dict[str, float] = defaultdict(float)
        self.dfn: dict[str, float] = defaultdict(float)
        self.init_mu, self.init_home = init_mu, init_home
        self.mu: dict[str, float] = {}
        self.home: dict[str, float] = {}
        self.n: dict[str, int] = defaultdict(int)

    def rates(self, home: str, away: str, league: str, neutral: bool = False):
        mu = self.mu.get(league, self.init_mu)
        h = 0.0 if neutral else self.home.get(league, self.init_home)
        lh = math.exp(mu + h + self.att.get(home, 0.0) - self.dfn.get(away, 0.0))
        la = math.exp(mu + self.att.get(away, 0.0) - self.dfn.get(home, 0.0))
        return lh, la

    def update(self, home: str, away: str, league: str, yh: float, ya: float,
               neutral: bool = False) -> None:
        lh, la = self.rates(home, away, league, neutral)
        rh, ra = yh - lh, ya - la                       # d logL / d log λ
        # faster learning for new teams, settling down with experience
        sh = self.lr * (1 + 2.0 / (1 + self.n[home] / 5))
        sa = self.lr * (1 + 2.0 / (1 + self.n[away] / 5))
        self.att[home] += sh * rh / max(lh, 0.3) ** 0.5
        self.dfn[away] -= sa * rh / max(lh, 0.3) ** 0.5
        self.att[away] += sa * ra / max(la, 0.3) ** 0.5
        self.dfn[home] -= sh * ra / max(la, 0.3) ** 0.5
        self.mu[league] = self.mu.get(league, self.init_mu) + self.league_lr * (rh + ra)
        if not neutral:
            self.home[league] = (self.home.get(league, self.init_home)
                                 + self.league_lr * 0.5 * (rh - ra))
        self.n[home] += 1
        self.n[away] += 1
