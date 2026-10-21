"""football-data.co.uk: results, half-time scores, shots, corners, cards,
closing 1X2 and Over/Under 2.5 odds. This is the backbone of the
past-match-detail features."""

from __future__ import annotations

import io

import numpy as np
import pandas as pd

from footypred.data.http import HttpClient
from footypred.data.names import canonical
from footypred.logging_utils import get_logger

log = get_logger("sources.football_data")

BASE = "https://www.football-data.co.uk/mmz4281/{code}/{league}.csv"

COLMAP = {
    "HomeTeam": "home", "AwayTeam": "away", "FTHG": "fthg", "FTAG": "ftag",
    "HTHG": "hthg", "HTAG": "htag", "HS": "hs", "AS": "as_", "HST": "hst",
    "AST": "ast", "HC": "hc", "AC": "ac", "HY": "hy", "AY": "ay", "HR": "hr",
    "AR": "ar", "HxG": "home_xg", "AxG": "away_xg",
}
# closing odds preferred, opening as fallback; per row, the first non-empty column wins
ODDS = {
    "odds_h": ["PSCH", "AvgCH", "B365CH", "PSH", "AvgH", "B365H"],
    "odds_d": ["PSCD", "AvgCD", "B365CD", "PSD", "AvgD", "B365D"],
    "odds_a": ["PSCA", "AvgCA", "B365CA", "PSA", "AvgA", "B365A"],
    "odds_o25": ["PC>2.5", "AvgC>2.5", "B365C>2.5", "P>2.5", "Avg>2.5", "B365>2.5"],
    "odds_u25": ["PC<2.5", "AvgC<2.5", "B365C<2.5", "P<2.5", "Avg<2.5", "B365<2.5"],
}


def parse_dates(values) -> pd.Series:
    """Match dates as football-data.co.uk writes them (dd/mm/yy or
    dd/mm/yyyy) or as ISO yyyy-mm-dd (Excel exports, other tools). ISO is
    detected first: `dayfirst=True` would misread 2012-03-05 as 3 May."""
    s = pd.Series(values).astype("string").str.strip()
    iso = s.dropna().str.match(r"^\d{4}-\d{1,2}-\d{1,2}")
    if len(iso) and iso.all():
        return pd.to_datetime(s.str[:10], format="%Y-%m-%d", errors="coerce")
    return pd.to_datetime(s, format="mixed", dayfirst=True, errors="coerce")


def first_available(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    """Per row, the first of `candidates` that has a number (e.g. Pinnacle
    closing, else market average, else Bet365): bookmakers come and go
    between seasons and some rows lack one."""
    cols = [pd.to_numeric(df[c], errors="coerce") for c in candidates if c in df.columns]
    if not cols:
        return pd.Series(np.nan, index=df.index)
    return pd.concat(cols, axis=1).bfill(axis=1).iloc[:, 0]


def season_code(season: int) -> str:
    return f"{season % 100:02d}{(season + 1) % 100:02d}"


def parse_csv(raw: bytes, league: str, season: int) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw), encoding="latin-1", on_bad_lines="skip")
    df = df.dropna(subset=["HomeTeam", "AwayTeam", "Date"])
    out = df.rename(columns=COLMAP)[[c for c in COLMAP.values() if c in df.rename(columns=COLMAP)]]
    out = out.copy()
    out["date"] = parse_dates(df["Date"]).values
    if "Time" in df:
        out["kickoff"] = df["Time"].astype(str).where(df["Time"].notna(), None)
    for target, candidates in ODDS.items():
        out[target] = first_available(df, candidates)
    out["home"] = out["home"].map(canonical)
    out["away"] = out["away"].map(canonical)
    out["league"] = league
    out["season"] = season
    out["neutral"] = 0
    return out.dropna(subset=["date"])


def fetch(client: HttpClient, leagues: list[str], seasons: list[int]) -> pd.DataFrame:
    frames = []
    for league in leagues:
        for season in seasons:
            url = BASE.format(code=season_code(season), league=league)
            try:
                frames.append(parse_csv(client.get_bytes(url), league, season))
            except Exception as exc:  # one bad file never stops the run
                log.warning("football-data %s %s failed: %s", league, season, exc)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
