"""Train on everything in the database and save the model (`footy train`,
or the Train button in the web app)."""

from __future__ import annotations

import dataclasses
import logging
import threading
import time
from contextlib import contextmanager

from footypred.logging_utils import get_logger

log = get_logger("models.pipeline")

QUICK_MODELS = ["poisson", "dixon_coles", "lightgbm"]


@contextmanager
def forward_logs(say, level=logging.INFO):
    """Send this thread's footypred log lines to `say` (e.g. a web job)."""
    if say is None:
        yield
        return
    me = threading.get_ident()

    class Forward(logging.Handler):
        def emit(self, record):
            if record.thread == me:
                try:
                    say(record.getMessage())
                except Exception:
                    pass
    h = Forward(level)
    root = logging.getLogger("footypred")
    old = root.level
    root.setLevel(min(old, level) if old else level)   # INFO must get through
    root.addHandler(h)
    try:
        yield
    finally:
        root.removeHandler(h)
        root.setLevel(old)


def train_and_save(cfg, db, models: list[str] | None = None, say=None) -> dict:
    """Tune ratings, build features, nested-CV train, select and save.
    models: train only these (e.g. QUICK_MODELS) instead of the config's list."""
    from footypred.config import Section
    from footypred.features.engineering import FeatureBuilder, feature_columns
    from footypred.features.tuning import tune_ratings
    from footypred.models.registry import ModelRegistry
    from footypred.models.summary import render_training_report
    from footypred.models.trainer import Trainer
    t0 = time.time()
    matches = db.load_matches()
    if matches.empty:
        raise ValueError("no matches loaded yet — add your match file (or the demo data) first")
    if models:
        cfg = dataclasses.replace(cfg, training=Section({**cfg.training, "models": list(models)}))
    with forward_logs(say):
        log.info("training on %d matches (%s → %s), models: %s", len(matches),
                 matches["date"].min().date(), matches["date"].max().date(),
                 ", ".join(cfg.training["models"]))
        params = tune_ratings(matches) if cfg.features.get("auto_tune_ratings", True) else {}
        fb = FeatureBuilder(cfg, db, params)
        frame = fb.build_training_frame(matches)
        res = Trainer(cfg).train(frame, feature_columns(frame))
        res.feature_params = fb.params
        res.report["data_source"] = db.get_meta("data_source")
        version = ModelRegistry(cfg.paths.models_dir).save(res, fb.state)
        log.info("saved model %s (%s) in %.0fs", version, res.selected, time.time() - t0)
    return {"version": version, "selected": res.selected, "matches": len(matches),
            "seconds": round(time.time() - t0, 1), "report": render_training_report(res.report)}
