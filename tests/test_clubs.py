"""Owner and sponsor as model features: dated categories, one-hot columns,
an explicit "unknown", and the switch to leave them out."""

import dataclasses

import numpy as np
import pandas as pd

from footypred.config import Section
from footypred.features import clubs
from footypred.features.engineering import FeatureBuilder, feature_columns
from footypred.predict import highstake as hs


def _cats():
    flags = {
        "Chelsea": hs.ClubFlags("Chelsea", "E0", "BlueCo", "majority", "2022-05", "Betway"),
        "Aston Villa": hs.ClubFlags("Aston Villa", "E0", "V Sports", "joint", "", "Betano"),
        "Crystal Palace": hs.ClubFlags("Crystal Palace", "E0", "W. Johnson", "largest investor"),
        "Manchester City": hs.ClubFlags("Manchester City", "E0", "Silver Lake", "minority", "", "Rekonix"),
        "Sevilla": hs.ClubFlags("Sevilla", "SP1", "Group", "pending"),
    }
    return clubs.ClubCategories(flags)


def test_categories_are_dated_and_unknown_is_explicit():
    c = _cats()
    assert c.researched == {"E0", "SP1"}
    assert c.owner_category("Chelsea", "E0", "2022-04-30") == "other"          # before BlueCo
    assert c.owner_category("Chelsea", "E0", "2022-05-01") == "us_majority"
    assert c.owner_category("Aston Villa", "E0", "2019-01-01") == "us_joint"    # no date: throughout
    assert c.owner_category("Crystal Palace", "E0", "2026-01-01") == "us_largest"
    assert c.owner_category("Manchester City", "E0", "2026-01-01") == "other"   # minority stake
    assert c.owner_category("Sevilla", "SP1", "2026-01-01") == "other"          # sale not completed
    assert c.owner_category("Brentford", "E0", "2026-01-01") == "other"         # researched league
    assert c.owner_category("Ajax", "N1", "2026-01-01") == "unknown"            # not researched
    assert c.sponsor_category("Chelsea", "E0") == "betting"
    assert c.sponsor_category("Sevilla", "SP1") == "none"
    assert c.sponsor_category("Ajax", "N1") == "unknown"
    f = c.encode("Chelsea", "E0", "2026-11-22", "h")
    assert set(f) == {k for k in clubs.columns() if k.startswith("h_")}
    assert f["h_own_us_majority"] == 1 and f["h_spn_betting"] == 1
    assert sum(v for k, v in f.items() if "_own_" in k) == 1        # exactly one category each
    assert sum(v for k, v in f.items() if "_spn_" in k) == 1
    u = c.encode("Ajax", "N1", "2026-11-22", "a")
    assert u["a_own_unknown"] == 1 and u["a_spn_unknown"] == 1
    assert len(clubs.columns()) == 16 and all(clubs.is_club_column(x) for x in clubs.columns())


def test_the_features_reach_the_training_frame(cfg, populated_db):
    frame = FeatureBuilder(cfg, populated_db).build_training_frame()
    cols = feature_columns(frame)
    assert set(clubs.columns()) <= set(cols)
    one_hot = frame[clubs.columns()]
    assert set(np.unique(one_hot.to_numpy())) <= {0.0, 1.0}
    for side in ("h", "a"):
        assert (frame[[f"{side}_own_{x}" for x in clubs.OWNER_CATS]].sum(axis=1) == 1).all()
        assert (frame[[f"{side}_spn_{x}" for x in clubs.SPONSOR_CATS]].sum(axis=1) == 1).all()
    # Everton (config/club_flags.csv: American majority owner since 2024-12) changes on that date
    ev = frame[frame["home"] == "Everton"]
    before, after = ev[ev["date"] < pd.Timestamp("2024-12-01")], ev[ev["date"] >= pd.Timestamp("2024-12-01")]
    assert len(before) and len(after)
    assert (before["h_own_other"] == 1).all() and (after["h_own_us_majority"] == 1).all()
    # switched off: no columns
    off = dataclasses.replace(cfg, features=Section({**cfg.features, "club_flags": False}))
    plain = FeatureBuilder(off, populated_db).build_training_frame()
    assert not any(clubs.is_club_column(c) for c in plain.columns)
