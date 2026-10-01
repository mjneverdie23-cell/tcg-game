import pickle

import numpy as np
import pandas as pd

from footypred.features.engineering import FeatureBuilder, FeatureState, feature_columns
from footypred.features.tuning import tune_ratings


def test_no_leakage_from_same_day_or_future(cfg, populated_db, matches):
    fb = FeatureBuilder(cfg, populated_db)
    base = fb.build_training_frame(populated_db.load_matches())
    m = populated_db.load_matches()
    cut = m["date"].iloc[len(m) // 2]
    tampered = m.copy()
    later = tampered["date"] >= cut
    tampered.loc[later, "fthg"] = 9            # rewrite every result from `cut` on
    tampered.loc[later, "home_xg"] = 5.0
    alt = FeatureBuilder(cfg, populated_db).build_training_frame(tampered)
    fc = feature_columns(base)
    on_or_before = base["date"] <= cut          # features for day `cut` itself too
    a = base.loc[on_or_before, fc].to_numpy(float)
    b = alt.loc[on_or_before, fc].to_numpy(float)
    np.testing.assert_allclose(np.nan_to_num(a, nan=-999), np.nan_to_num(b, nan=-999))
    # sanity: features after the cut do change
    assert not np.allclose(np.nan_to_num(base.loc[~on_or_before, fc].to_numpy(float)),
                           np.nan_to_num(alt.loc[~on_or_before, fc].to_numpy(float)))


def test_market_rate_features_present(cfg, populated_db):
    fr = FeatureBuilder(cfg, populated_db).build_training_frame()
    for col in ("h_l10_s1", "h_l10_s2", "h_l10_s3", "a_v_c1", "h_ew_btts", "a_ew_o25",
                "m_btts", "m_h_s2", "h2h_btts", "pr_btts", "pr_o25", "h_ew_btts_res"):
        assert col in fr.columns
    late = fr[fr["season"] == fr["season"].max()]
    assert late["h_l10_s1"].between(0, 1).all()


def test_state_pickle_and_incremental_replay(cfg, populated_db):
    m = populated_db.load_matches()
    first, rest = m.iloc[: len(m) - 60], m.iloc[len(m) - 60:]
    full = FeatureState(dict(cfg.features)); full.replay(m)
    part = FeatureState(dict(cfg.features)); part.replay(first)
    part = pickle.loads(pickle.dumps(part))
    part.replay(rest)
    d = m["date"].max() + pd.Timedelta(days=5)
    fa = full.features("Arsenal", "Chelsea", d, "E0")
    fb = part.features("Arsenal", "Chelsea", d, "E0")
    for k in fa:
        assert (np.isnan(fa[k]) and np.isnan(fb[k])) or abs(fa[k] - fb[k]) < 1e-9, k


def test_rating_tuning_returns_grid_values(populated_db):
    p = tune_ratings(populated_db.load_matches())
    assert 0.005 <= p["rt_lr"] <= 0.05
    assert 0.0 <= p["rx_xg_weight"] <= 1.0
