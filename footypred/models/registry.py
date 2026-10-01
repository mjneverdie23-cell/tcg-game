"""Versioned model bundles: models/<version>/bundle.pkl + report.json,
with models/LATEST pointing at the active version."""

from __future__ import annotations

import json
import pickle
import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from footypred import __version__
from footypred.logging_utils import get_logger

log = get_logger("models.registry")


@dataclass
class Bundle:
    version: str
    result: object            # TrainResult
    state: object             # FeatureState after replaying the training data
    created: str
    package_version: str


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return o


class ModelRegistry:
    def __init__(self, models_dir: str | Path, keep: int = 5):
        self.dir = Path(models_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.keep = keep

    def save(self, result, state) -> str:
        version = pd.Timestamp.now().strftime("v%Y%m%d-%H%M%S")
        vdir = self.dir / version
        vdir.mkdir(parents=True, exist_ok=False)
        bundle = Bundle(version, result, state, pd.Timestamp.now().isoformat(timespec="seconds"),
                        __version__)
        with open(vdir / "bundle.pkl", "wb") as fh:
            pickle.dump(bundle, fh, protocol=pickle.HIGHEST_PROTOCOL)
        with open(vdir / "report.json", "w", encoding="utf-8") as fh:
            json.dump(_jsonable({"version": version, "selected": result.selected,
                                 "feature_params": result.feature_params,
                                 **result.report}), fh, indent=2)
        (self.dir / "LATEST").write_text(version)
        self._prune()
        log.info("saved model bundle %s", version)
        return version

    def _prune(self):
        versions = sorted(p for p in self.dir.iterdir() if p.is_dir() and p.name.startswith("v"))
        for old in versions[:-self.keep]:
            shutil.rmtree(old, ignore_errors=True)

    def latest_version(self) -> str | None:
        p = self.dir / "LATEST"
        return p.read_text().strip() if p.exists() else None

    def load(self, version: str | None = None) -> Bundle:
        version = version or self.latest_version()
        if not version:
            raise FileNotFoundError("no trained model found - run `footy train` first")
        with open(self.dir / version / "bundle.pkl", "rb") as fh:
            return pickle.load(fh)

    def versions(self) -> list[str]:
        return sorted(p.name for p in self.dir.iterdir() if p.is_dir() and p.name.startswith("v"))
