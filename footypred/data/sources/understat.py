"""Understat: per-match expected goals (xG) for the big-five leagues."""

from __future__ import annotations

import codecs
import json
import re

import pandas as pd

from footypred.data.http import HttpClient
from footypred.data.names import canonical
from footypred.logging_utils import get_logger

log = get_logger("sources.understat")

URL = "https://understat.com/league/{league}/{season}"
API = "https://understat.com/getLeagueData/{league}/{season}"


def _decode_embedded(html: str, var: str) -> list | None:
    m = re.search(rf"var\s+{var}\s*=\s*JSON\.parse\('(.+?)'\)", html)
    if not m:
        return None
    return json.loads(codecs.decode(m.group(1), "unicode_escape"))


def parse(payload, league_code: str, season: int) -> pd.DataFrame:
    rows = []
    for m in payload or []:
        if not m.get("isResult"):
            continue
        rows.append({
            "date": pd.to_datetime(m["datetime"]).normalize(),
            "home": canonical(m["h"]["title"]), "away": canonical(m["a"]["title"]),
            "home_xg": float(m["xG"]["h"]), "away_xg": float(m["xG"]["a"]),
            "fthg": int(m["goals"]["h"]), "ftag": int(m["goals"]["a"]),
            "league": league_code, "season": season,
        })
    return pd.DataFrame(rows)


def fetch(client: HttpClient, league_map: dict[str, str], seasons: list[int]) -> pd.DataFrame:
    """league_map: football-data code -> understat league slug."""
    frames = []
    for code, slug in league_map.items():
        for season in seasons:
            try:
                payload = None
                try:  # newer site: JSON endpoint
                    payload = json.loads(client.get_text(API.format(league=slug, season=season))
                                         ).get("dates")
                except Exception:
                    html = client.get_text(URL.format(league=slug, season=season))
                    payload = _decode_embedded(html, "datesData")
                frames.append(parse(payload, code, season))
            except Exception as exc:
                log.warning("understat %s %s failed: %s", slug, season, exc)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
