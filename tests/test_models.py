import numpy as np
import pandas as pd

from footypred.models.goal_models import DixonColes


def test_dixon_coles_recovers_strengths():
    rng = np.random.default_rng(1)
    teams = [f"T{i}" for i in range(16)]
    att = dict(zip(teams, rng.normal(0, 0.3, 16)))
    dfn = dict(zip(teams, rng.normal(0, 0.3, 16)))
    rows = []
    d0 = pd.Timestamp("2024-01-01")
    for rep in range(6):
        for h in teams:
            for a in teams:
                if h == a:
                    continue
                lh = np.exp(0.25 + 0.25 + att[h] - dfn[a])
                la = np.exp(0.25 + att[a] - dfn[h])
                rows.append({"date": d0 + pd.Timedelta(days=rep), "home": h, "away": a,
                             "league": "L", "neutral": 0,
                             "y_h": rng.poisson(lh), "y_a": rng.poisson(la)})
    frame = pd.DataFrame(rows)
    m = DixonColes(half_life_days=10_000).fit(frame)
    est = np.array([m.params[0][t][0] for t in teams])
    true = np.array([att[t] for t in teams])
    assert np.corrcoef(est, true)[0, 1] > 0.9
    mu, hadv = m.params[1]["L"]
    assert abs(hadv - 0.25) < 0.08
