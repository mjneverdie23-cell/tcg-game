import pytest

from footypred.config import load_config
from footypred.data.db import Database
from footypred.data.synthetic import generate


@pytest.fixture(scope="session")
def cfg(tmp_path_factory):
    root = tmp_path_factory.mktemp("footy")
    c = load_config(root=root, overrides={
        "seasons": [2022, 2023, 2024, 2025],
        "training": {"models": ["poisson", "dixon_coles", "lightgbm"],
                     "dc_half_life_grid": [240, 480]},
    })
    c.paths.ensure()
    return c


@pytest.fixture(scope="session")
def matches():
    return generate([2022, 2023, 2024, 2025], cutoff="2026-06-30", seed=3,
                    leagues=["E0"], internationals=False)


@pytest.fixture(scope="session")
def populated_db(cfg, matches):
    db = Database(cfg.paths.db_file)
    db.upsert_matches(matches, source="synthetic")
    return db
