"""Configuration loading (YAML -> typed, attribute-access objects)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "default.yaml"


@dataclass
class Paths:
    root: Path
    data_dir: Path
    db_file: Path
    cache_dir: Path
    models_dir: Path
    log_dir: Path

    def ensure(self) -> None:
        for p in (self.data_dir, self.cache_dir, self.models_dir, self.log_dir):
            p.mkdir(parents=True, exist_ok=True)
        self.db_file.parent.mkdir(parents=True, exist_ok=True)


class Section(dict):
    """dict with attribute access for config sections."""

    def __getattr__(self, item: str) -> Any:
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc


@dataclass
class Config:
    paths: Paths
    http: Section
    leagues: dict
    seasons: list
    sources: Section
    features: Section
    training: Section
    prediction: Section
    raw: dict = field(default_factory=dict)


LOCAL_SETTINGS = Path("config") / "local.yaml"   # your own settings (saved by the web app)


def settings_path(root: str | Path | None = None) -> Path:
    return Path(root or PROJECT_ROOT) / LOCAL_SETTINGS


def deep_update(base: dict, extra: dict) -> dict:
    """Merge `extra` into `base` in place, section by section."""
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_update(base[k], v)
        else:
            base[k] = v
    return base


def load_local_settings(root: str | Path | None = None) -> dict:
    p = settings_path(root)
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def save_local_settings(updates: dict, root: str | Path | None = None) -> Path:
    """Write settings (API key, match-file path, first season ...) to
    config/local.yaml, which is never committed; None removes a value."""
    cur = load_local_settings(root)
    deep_update(cur, updates)

    def prune(d):
        for k in list(d):
            if isinstance(d[k], dict):
                prune(d[k])
                if not d[k]:
                    del d[k]
            elif d[k] is None or d[k] == "":
                del d[k]
    prune(cur)
    p = settings_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("# Your own settings, saved by the web app (Data tab > Settings).\n"
                 "# They override config/default.yaml. Keep this file private: it can\n"
                 "# hold your football-data.org API key. It is never committed (.gitignore).\n")
        yaml.safe_dump(cur, fh, sort_keys=False, allow_unicode=True)
    return p


def _resolve(root: Path, value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else root / p


def load_config(path: str | Path | None = None, root: str | Path | None = None,
                overrides: dict | None = None) -> Config:
    """Load config from YAML. `root` relocates all relative paths
    (used by tests to isolate state in a temp directory)."""
    path = Path(path or os.environ.get("FOOTY_CONFIG") or DEFAULT_CONFIG)
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    deep_update(raw, load_local_settings(root))     # config/local.yaml, if you saved settings
    if overrides:
        for section, values in overrides.items():
            if isinstance(values, dict):
                raw.setdefault(section, {}).update(values)
            else:
                raw[section] = values
    base = Path(root) if root else PROJECT_ROOT
    rp = raw["paths"]
    paths = Paths(
        root=base,
        data_dir=_resolve(base, rp["data_dir"]),
        db_file=_resolve(base, rp["db_file"]),
        cache_dir=_resolve(base, rp["cache_dir"]),
        models_dir=_resolve(base, rp["models_dir"]),
        log_dir=_resolve(base, rp["log_dir"]),
    )
    return Config(
        paths=paths,
        http=Section(raw.get("http", {})),
        leagues=raw.get("leagues", {}),
        seasons=list(raw.get("seasons", [])),
        sources=Section(raw.get("sources", {})),
        features=Section(raw.get("features", {})),
        training=Section(raw.get("training", {})),
        prediction=Section(raw.get("prediction", {})),
        raw=raw,
    )
