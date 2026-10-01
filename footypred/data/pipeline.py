"""Data orchestration: `bootstrap` (offline synthetic) and `update` (scrape)."""

from __future__ import annotations

import pandas as pd

from footypred.data import synthetic
from footypred.data.db import Database
from footypred.data.http import HttpClient
from footypred.logging_utils import get_logger

log = get_logger("data.pipeline")


def bootstrap(cfg, db: Database, cutoff=None, seed: int = 7) -> int:
    """Fill the DB with the synthetic dataset (no network needed)."""
    df = synthetic.generate(cfg.seasons, cutoff=cutoff, seed=seed)
    n = db.upsert_matches(df, source="synthetic")
    db.upsert_team_info(synthetic.team_market_values(cfg.seasons, seed=seed))
    db.set_meta("data_source", "synthetic")
    db.set_meta("last_update", pd.Timestamp.now().isoformat(timespec="seconds"))
    return n


def update(cfg, db: Database, client: HttpClient | None = None) -> dict:
    """Refresh every enabled source; each fails in isolation."""
    from footypred.data.sources import (clubelo, fifa, football_data, transfermarkt,
                                        understat, weather)
    client = client or HttpClient.from_config(cfg)
    leagues = list(cfg.leagues)
    report: dict[str, int | str] = {}

    def run(name, fn):
        if not cfg.sources.get(name, False):
            return
        try:
            report[name] = fn()
        except Exception as exc:
            log.error("source %s failed: %s", name, exc)
            report[name] = f"failed: {exc}"

    run("football_data", lambda: db.upsert_matches(
        football_data.fetch(client, leagues, cfg.seasons), "football_data"))
    us_map = {c: m["understat"] for c, m in cfg.leagues.items() if m.get("understat")}
    run("understat", lambda: db.upsert_matches(
        understat.fetch(client, us_map, cfg.seasons), "understat"))

    def _elo():
        months = pd.date_range(f"{min(cfg.seasons)}-08-01", pd.Timestamp.today(), freq="MS")
        return db.upsert_team_info(clubelo.fetch(client, list(months)))
    run("clubelo", _elo)
    run("transfermarkt", lambda: db.upsert_team_info(
        transfermarkt.fetch(client, leagues, cfg.seasons)))
    run("fifa", lambda: db.upsert_team_info(fifa.fetch(client)))

    def _weather():
        m = db.load_matches()
        done = set(db.load_weather()["match_id"])
        return db.upsert_weather(weather.fetch(client, m[~m["match_id"].isin(done)]))
    run("weather", _weather)

    got = any(isinstance(v, int) and v > 0 for v in report.values())
    if got:
        db.set_meta("data_source", "scraped")
        db.set_meta("last_update", pd.Timestamp.now().isoformat(timespec="seconds"))
    log.info("update report: %s", report)
    return report
