"""Walk-forward backtest: trains only on the past, predicts each day before
its results are known, and works with a short history (half-season folds)."""

import copy
import shutil
import sqlite3

import numpy as np
import pytest

from footypred.data.db import Database
from footypred.data.synthetic import generate
from footypred.predict import walkforward as wf

START, END = "2024-03-01", "2024-03-31"


@pytest.fixture(scope="module")
def short_db(tmp_path_factory):
    """Two leagues + Champions League, 2022/23 to 2023/24 only."""
    db = Database(tmp_path_factory.mktemp("wf") / "wf.sqlite")
    db.upsert_matches(generate([2022, 2023], cutoff="2024-06-30", seed=5,
                               leagues=["E0", "D1"], internationals=False), "synthetic")
    return db


@pytest.fixture(scope="module")
def cached_training():
    """Reuse one training per cut-off across runs (each run gets its own
    copy of the feature state, since the walk updates it)."""
    real, cache = wf.train_until, {}

    def train(cfg, db, matches, cutoff, models=None, tune=True):
        key = str(cutoff)
        if key not in cache:
            cache[key] = real(cfg, db, matches, cutoff, models, tune)
        res, state, info = cache[key]
        return res, copy.deepcopy(state), info
    return train


def test_walk_forward_is_out_of_sample(cfg, short_db, cached_training, monkeypatch, tmp_path):
    monkeypatch.setattr(wf, "train_until", cached_training)
    r = wf.walk_forward(cfg, short_db, START, END, tune=False)
    m = short_db.load_matches()
    in_range = m[(m["date"] >= START) & (m["date"] <= END)]
    assert len(r.rows) == len(in_range)
    t = r.trainings[0]
    assert t["matches"] == int((m["date"] < START).sum())
    assert t["folds"] == "half"                     # < 4 seasons of history
    assert r.metrics and 0.9 < r.metrics["1x2"]["logloss"] < 1.15
    p = r.rows[["p_home", "p_draw", "p_away"]].to_numpy()
    assert np.allclose(p.sum(axis=1), 1, atol=2e-3)
    assert r.picks["balanced"]["picks"] > 0 and r.betting["value_1x2"]["bets"] >= 0
    assert set(r.rows["league"]) >= {"E0", "D1"}
    h = r.metrics["halftime"]                                    # first half, same walk
    assert h["matches"] == len(r.rows) and 0.9 < h["1x2"]["logloss"] < 1.2
    assert {"p_ht_home", "p_ht_o05", "p_ht_btts"} <= set(r.rows.columns)
    assert (r.rows["p_ht_o05"] < 1 - 1e-9).all() and "first half" in wf.render(r)

    # change every result on the last day: that day's predictions must not move
    last = r.rows["date"].max()
    path = tmp_path / "changed.sqlite"
    shutil.copy(short_db.path, path)
    with sqlite3.connect(path) as con:
        con.execute("UPDATE matches SET fthg = fthg + 3 WHERE date = ?", (last,))
    r2 = wf.walk_forward(cfg, Database(path), START, END, tune=False)
    cols = ["p_home", "p_draw", "p_away", "p_o25", "p_btts", "p_h_o15", "pick_balanced"]
    a, b = r.rows[cols], r2.rows[cols]
    assert a.equals(b)
    assert not r.rows["fthg"].equals(r2.rows["fthg"])


def test_competition_filter_and_bad_ranges(cfg, short_db, cached_training, monkeypatch):
    monkeypatch.setattr(wf, "train_until", cached_training)
    r = wf.walk_forward(cfg, short_db, START, END, competitions=["D1"], tune=False)
    assert set(r.rows["league"]) == {"D1"}
    with pytest.raises(ValueError, match="before the start"):
        wf.walk_forward(cfg, short_db, END, START)
    with pytest.raises(ValueError, match="after the first match"):
        wf.walk_forward(cfg, short_db, "2020-01-01", END)
    text = wf.render(r)
    assert "Walk-forward backtest" in text and "balanced" in text


def test_high_stake_backtest(cfg, short_db, cached_training, monkeypatch, tmp_path):
    """One walk, scored in both modes: the model without the factor is the
    balanced model, the factor moves flagged matches only, picks are 1.70+,
    and a day's results never reach that day's high stake predictions."""
    monkeypatch.setattr(wf, "train_until", cached_training)
    run = wf.predict_range(cfg, short_db, START, END, competitions=["E0"], tune=False)
    bal = wf.score_range(cfg, short_db, run)
    zero = wf.score_range(cfg, short_db, run, mode="high", factor=0.0)
    hi = wf.score_range(cfg, short_db, run, mode="high", factor=1.0)
    cols = ["p_home", "p_draw", "p_away"]
    assert bal.rows[cols].equals(zero.rows[cols]) and not bal.high_stake
    assert zero.high_stake["adjusted"] == 0
    assert zero.high_stake["model"] == zero.high_stake["with_factor"]
    h = hi.high_stake
    assert h["matches"] == len(hi.rows) and h["adjusted"] > 0 and h["factor"] == 1.0
    assert h["model"] == zero.high_stake["model"]                     # same walk underneath
    assert h["with_factor"]["1x2"]["logloss"] != h["model"]["1x2"]["logloss"]
    fav = h["favourite_non_wins"]
    assert fav["all"]["matches"] == len(hi.rows) and 0 <= fav["all"]["actual"] <= len(hi.rows)
    assert fav["more_upsets"]["matches"] + fav["fewer_upsets"]["matches"] <= h["adjusted"]
    # the "model" columns are the balanced numbers; only flagged matches moved
    assert np.allclose(hi.rows["p_home_model"], bal.rows["p_home"], atol=1e-4)
    moved = hi.rows["factor_applied"].to_numpy(bool)
    d = (hi.rows["p_home"] - hi.rows["p_home_model"]).abs().to_numpy()
    assert (d[moved] > 0).any() and (d[~moved] < 1e-4).all()
    assert (hi.rows.loc[moved, "flags"] > 0).all()
    for style in ("safe", "balanced", "bold"):
        assert (hi.rows[f"pick_{style}_fair_odds"].dropna() >= 1.70).all()
        assert set(hi.picks[style].get("by_market", {})) <= {
            "1x2", "handicap", "combo", "totals", "btts", "team_totals"}
    assert hi.settings["mode"] == "high" and bal.settings["mode"] == "balanced"
    text = wf.render(hi)
    assert "owner & sponsor factor 100%" in text and "Favourite didn't win" in text
    with pytest.raises(ValueError, match="mode"):
        wf.score_range(cfg, short_db, run, mode="reckless")

    # change every result on the last day: that day's high stake numbers must not move
    last = hi.rows["date"].max()
    path = tmp_path / "changed_hs.sqlite"
    shutil.copy(short_db.path, path)
    with sqlite3.connect(path) as con:
        con.execute("UPDATE matches SET fthg = fthg + 3 WHERE date = ?", (last,))
    hi2 = wf.walk_forward(cfg, Database(path), START, END, competitions=["E0"], tune=False,
                          mode="high", factor=1.0)
    cols = ["p_home", "p_draw", "p_away", "p_o25", "upset_ratio", "pick_balanced"]
    assert hi.rows[cols].equals(hi2.rows[cols])
