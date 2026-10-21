"""Score matrices: the joint distribution of (home goals, away goals).

Every goal-rate model produces one; every market is read off it. Batched
as arrays of shape (n, G, G) where G = max_goals + 1 (row = home goals).

The four target markets:
    1X2               home / draw / away
    Over/Under 2.5    total goals > 2.5
    team totals       home/away goals over 0.5, 1.5, 2.5
    BTTS              both teams score
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import poisson

G_DEFAULT = 11  # 0..10 goals

# binary markets, in canonical order (1X2 handled separately as 3-way)
BINARY_MARKETS = ["o25", "btts", "h_o05", "h_o15", "h_o25", "a_o05", "a_o15", "a_o25"]
# extra total-goals lines: read off the reconciled matrix (not separately calibrated)
EXTRA_MARKETS = ["o15", "o35"]
MARKET_LABELS = {
    "1x2": "Match result (1X2)", "o25": "Over 2.5 goals", "btts": "Both teams to score",
    "h_o05": "Home over 0.5", "h_o15": "Home over 1.5", "h_o25": "Home over 2.5",
    "a_o05": "Away over 0.5", "a_o15": "Away over 1.5", "a_o25": "Away over 2.5",
}


def _masks(G: int) -> dict[str, np.ndarray]:
    i, j = np.indices((G, G))
    return {
        "home": i > j, "draw": i == j, "away": i < j,
        "o15": (i + j) > 1, "o25": (i + j) > 2, "o35": (i + j) > 3,
        "btts": (i > 0) & (j > 0),
        "h_o05": i > 0, "h_o15": i > 1, "h_o25": i > 2,
        "a_o05": j > 0, "a_o15": j > 1, "a_o25": j > 2,
    }


_MASK_CACHE: dict[int, dict[str, np.ndarray]] = {}


def masks(G: int) -> dict[str, np.ndarray]:
    if G not in _MASK_CACHE:
        _MASK_CACHE[G] = _masks(G)
    return _MASK_CACHE[G]


def dc_tau(lh, la, rho):
    """Dixon-Coles low-score adjustment factors for cells 00, 01, 10, 11."""
    return (1 - lh * la * rho, 1 + lh * rho, 1 + la * rho, 1 - rho)


def poisson_grids(lam_h, lam_a, rho=0.0, G: int = G_DEFAULT) -> np.ndarray:
    """Batch of (optionally Dixon-Coles adjusted) independent-Poisson grids."""
    lam_h = np.atleast_1d(np.asarray(lam_h, float))
    lam_a = np.atleast_1d(np.asarray(lam_a, float))
    k = np.arange(G)
    ph = poisson.pmf(k[None, :], lam_h[:, None])
    pa = poisson.pmf(k[None, :], lam_a[:, None])
    grid = ph[:, :, None] * pa[:, None, :]
    rho = np.broadcast_to(np.asarray(rho, float), lam_h.shape)
    if np.any(rho != 0):
        t00, t01, t10, t11 = dc_tau(lam_h, lam_a, rho)
        grid[:, 0, 0] *= np.maximum(t00, 1e-6)
        grid[:, 0, 1] *= np.maximum(t01, 1e-6)
        grid[:, 1, 0] *= np.maximum(t10, 1e-6)
        grid[:, 1, 1] *= np.maximum(t11, 1e-6)
    grid /= grid.sum(axis=(1, 2), keepdims=True)
    return grid


def market_probs(grids: np.ndarray) -> dict[str, np.ndarray]:
    """All target-market probabilities for a batch of grids."""
    grids = np.asarray(grids)
    if grids.ndim == 2:
        grids = grids[None]
    m = masks(grids.shape[-1])
    return {k: (grids * v).sum(axis=(1, 2)) for k, v in m.items()}


def outcome_array(grids: np.ndarray) -> np.ndarray:
    p = market_probs(grids)
    return np.column_stack([p["home"], p["draw"], p["away"]])


@dataclass
class ScoreMatrix:
    grid: np.ndarray            # (G, G)
    lam_home: float             # expected goals (mean of the grid)
    lam_away: float

    @classmethod
    def from_grid(cls, grid: np.ndarray) -> "ScoreMatrix":
        grid = np.asarray(grid, float)
        grid = grid / grid.sum()
        k = np.arange(grid.shape[0])
        return cls(grid, float((grid.sum(1) * k).sum()), float((grid.sum(0) * k).sum()))

    @classmethod
    def poisson(cls, lam_h: float, lam_a: float, rho: float = 0.0,
                G: int = G_DEFAULT) -> "ScoreMatrix":
        return cls.from_grid(poisson_grids(lam_h, lam_a, rho, G)[0])

    def markets(self) -> dict[str, float]:
        return {k: float(v[0]) for k, v in market_probs(self.grid).items()}

    def outcome_probs(self) -> np.ndarray:
        p = self.markets()
        return np.array([p["home"], p["draw"], p["away"]])

    def top_scores(self, n: int = 5) -> list[tuple[str, float]]:
        flat = np.argsort(self.grid, axis=None)[::-1][:n]
        G = self.grid.shape[0]
        return [(f"{i // G}-{i % G}", float(self.grid.flat[i])) for i in flat]

    def goal_diff_dist(self, span: int = 6) -> tuple[np.ndarray, np.ndarray]:
        G = self.grid.shape[0]
        d = np.subtract.outer(np.arange(G), np.arange(G))
        diffs = np.arange(-span, span + 1)
        return diffs, np.array([self.grid[d == x].sum() for x in diffs])
