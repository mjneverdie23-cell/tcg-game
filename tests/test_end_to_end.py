import json

import numpy as np

from footypred.features.engineering import FeatureBuilder, feature_columns
from footypred.features.tuning import tune_ratings
from footypred.models.registry import ModelRegistry
from footypred.models.summary import render_training_report
from footypred.models.trainer import Trainer
from footypred.predict.charts import js_divergence, plot_evaluation, plot_prediction
from footypred.predict.predictor import Predictor
from footypred.predict.report import render


def test_full_pipeline(cfg, populated_db, tmp_path):
    params = tune_ratings(populated_db.load_matches())
    fb = FeatureBuilder(cfg, populated_db, params)
    frame = fb.build_training_frame()
    res = Trainer(cfg).train(frame, feature_columns(frame))
    res.feature_params = fb.params
    rep = res.report
    assert rep["selected"] in rep["candidates"]
    sel = rep["candidates"][rep["selected"]]
    # the 4-market pipeline must never be worse than the raw backbone on the combined score
    assert sel["final"]["combined_skill"] >= sel["raw"]["combined_skill"] - 0.002
    assert "◀ selected" in render_training_report(rep)
    ModelRegistry(cfg.paths.models_dir).save(res, fb.state)

    pred = Predictor(cfg, populated_db).predict("Arsenal", "Chelsea", date="2026-07-15")
    m = pred.markets
    assert abs(sum(m["1x2"].values()) - 1) < 1e-3
    assert abs(m["over_under_2.5"]["over"] + m["over_under_2.5"]["under"] - 1) < 1e-3
    for side in ("home", "away"):
        t = m["team_totals"][side]
        assert t["over_0.5"] >= t["over_1.5"] >= t["over_2.5"]
    assert m["btts"]["yes"] <= min(m["team_totals"]["home"]["over_0.5"],
                                   m["team_totals"]["away"]["over_0.5"]) + 1e-3
    assert 0 <= pred.confidence["overall"] <= 100
    assert pred.evidence["home"]["last"]["n"] == 10
    json.dumps(pred.to_dict(), default=float)
    text = render(pred)
    for section in ("MATCH RESULT", "TOTAL GOALS OVER/UNDER", "TEAM GOALS", "BOTH TEAMS TO SCORE",
                    "PAST-MATCH EVIDENCE"):
        assert section in text

    # first half: its own model, tested out of sample, consistent with full time
    h = rep["halftime"]
    assert h["selected"] in h["candidates"] and h["eval_matches"] > 100
    assert "First half (out of sample" in render_training_report(rep)
    ht = pred.halftime
    assert abs(sum(ht["1x2"].values()) - 1) < 1e-3
    assert ht["totals"]["over_0.5"] >= ht["totals"]["over_1.5"] >= ht["totals"]["over_2.5"]
    assert ht["btts"]["yes"] <= ht["totals"]["over_1.5"] + 1e-6         # both scoring = 2+ goals
    assert ht["expected_goals"]["total"] < pred.expected_goals["total"]
    assert ht["btts"]["yes"] < m["btts"]["yes"] and ht["totals"]["over_1.5"] < m["totals"]["over_1.5"]
    assert "FIRST HALF" in text
    # the first half as an opt-in best-pick market, judged on half-time scores
    f = Predictor(cfg, populated_db).predict("Arsenal", "Chelsea", date="2026-07-15",
                                             pick_opts={"markets": ["first_half"], "style": "bold",
                                                        "min_lift": 0})
    cands = [c for c in f.form["candidates"] if c["market"] == "first_half"]
    assert len(cands) == 9 and all(e["event"].endswith(("half-time", "by half-time")) or
                                   "half-time" in e["event"] for c in cands for e in c["evidence"])
    assert f.form["best_pick"] is None or f.form["best_pick"]["market"] == "first_half"
    assert "first_half" not in pred.form["settings"]["markets"]            # off by default

    old = Predictor(cfg, populated_db)                                     # a model saved
    old.res.halftime = None                                                # before 2.7
    o = old.predict("Arsenal", "Chelsea", date="2026-07-15")
    assert o.halftime == {} and "FIRST HALF" not in render(o)
    assert abs(sum(o.markets["1x2"].values()) - 1) < 1e-3

    out = plot_prediction(pred, tmp_path / "pred.png")
    assert out.stat().st_size > 50_000
    out = plot_evaluation(res, tmp_path / "eval.png")
    assert out.stat().st_size > 50_000


def test_js_divergence():
    p, q = np.array([0.5, 0.3, 0.2]), np.array([0.2, 0.3, 0.5])
    assert js_divergence(p, p) == 0.0
    assert 0 < js_divergence(p, q) <= 1 and abs(js_divergence(p, q) - js_divergence(q, p)) < 1e-12
