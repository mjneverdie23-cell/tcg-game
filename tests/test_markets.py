import numpy as np

from footypred.models.market_head import probs_from_grids, reconcile
from footypred.models.metrics import evaluate, outcomes
from footypred.models.scorematrix import (BINARY_MARKETS, ScoreMatrix, market_probs,
                                          poisson_grids)


def test_market_identities():
    g = poisson_grids([1.7, 0.6, 2.4], [1.1, 1.9, 0.3], rho=-0.08)
    p = market_probs(g)
    np.testing.assert_allclose(p["home"] + p["draw"] + p["away"], 1, atol=1e-9)
    assert np.all(p["btts"] <= np.minimum(p["h_o05"], p["a_o05"]) + 1e-12)
    assert np.all(p["h_o05"] >= p["h_o15"]) and np.all(p["h_o15"] >= p["h_o25"])
    # O2.5 must be at least P(home scores 3+)
    assert np.all(p["o25"] >= p["h_o25"])
    assert np.all(p["o15"] >= p["o25"]) and np.all(p["o25"] >= p["o35"])


def test_poisson_marginals_and_dc():
    sm = ScoreMatrix.poisson(1.6, 1.1, rho=0.0)
    assert abs(sm.lam_home - 1.6) < 1e-3 and abs(sm.lam_away - 1.1) < 1e-3
    indep = poisson_grids(1.2, 1.0, 0.0)[0]
    dc = poisson_grids(1.2, 1.0, -0.1)[0]
    assert dc[0, 0] > indep[0, 0] and dc[1, 1] > indep[1, 1]   # ρ<0 inflates low draws


def test_reconcile_hits_consistent_targets():
    start = poisson_grids([1.4, 0.9], [1.2, 1.6])
    truth = poisson_grids([1.7, 0.7], [0.9, 1.8], rho=-0.1)
    target = probs_from_grids(truth)
    out = probs_from_grids(reconcile(start, target, iters=300))
    for k in ["1x2"] + BINARY_MARKETS:              # the markets reconciliation targets
        np.testing.assert_allclose(out[k], target[k], atol=2e-3)


def test_reconcile_output_is_coherent_even_for_rough_targets():
    g = poisson_grids([1.5], [1.2])
    target = probs_from_grids(g)
    target["btts"] = np.array([0.95])           # incompatible with the team totals
    r = reconcile(g, target)
    p = market_probs(r)
    np.testing.assert_allclose(r.sum(), 1, atol=1e-9)
    assert p["btts"][0] <= min(p["h_o05"][0], p["a_o05"][0]) + 1e-9


def test_metrics_skill_signs():
    rng = np.random.default_rng(0)
    lh, la = rng.uniform(0.5, 2.5, 3000), rng.uniform(0.5, 2.0, 3000)
    yh, ya = rng.poisson(lh), rng.poisson(la)
    good = evaluate(probs_from_grids(poisson_grids(lh, la)), yh, ya)
    flat = evaluate(probs_from_grids(poisson_grids(np.full(3000, lh.mean()),
                                                   np.full(3000, la.mean()))), yh, ya)
    assert good["combined_skill"] > 0.02
    assert good["combined_skill"] > flat["combined_skill"]
    assert set(good["groups"]) == {"1x2", "o25", "btts", "team_totals"}
    o = outcomes([2, 0, 1], [1, 0, 1])
    assert list(o["1x2"]) == [0, 1, 1] and list(o["btts"]) == [1, 0, 1]
