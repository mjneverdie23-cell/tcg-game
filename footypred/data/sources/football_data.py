"""football-data.co.uk: results, half-time scores, shots, corners, cards,
closing 1X2 and Over/Under 2.5 odds. This is the backbone of the
past-match-detail features."""

from __future__ import annotations

import io

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
    "AR": "ar",
}
# closing odds preferred, opening as fallback; first available column wins
ODDS = {
    "odds_h": ["PSCH", "AvgCH", "B365CH", "PSH", "AvgH", "B365H"],
    "odds_d": ["PSCD", "AvgCD", "B365CD", "PSD", "AvgD", "B365D"],
    "odds_a": ["PSCA", "AvgCA", "B365CA", "PSA", "AvgA", "B365A"],
    "odds_o25": ["PC>2.5", "AvgC>2.5", "B365C>2.5", "P>2.5", "Avg>2.5", "B365>2.5"],
    "odds_u25": ["PC<2.5", "AvgC<2.5", "B365C<2.5", "P<2.5", "Avg<2.5", "B365<2.5"],
}


def season_code(season: int) -> str:
    return f"{season % 100:02d}{(season + 1) % 100:02d}"


def parse_csv(raw: bytes, league: str, season: int) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw), encoding="latin-1", on_bad_lines="skip")
    df = df.dropna(subset=["HomeTeam", "AwayTeam", "Date"])
    out = df.rename(columns=COLMAP)[[c for c in COLMAP.values() if c in df.rename(columns=COLMAP)]]
    out = out.copy()
    out["date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    if "Time" in df:
        out["kickoff"] = df["Time"].astype(str).where(df["Time"].notna(), None)
    for target, candidates in ODDS.items():
        col = next((c for c in candidates if c in df.columns), None)
        out[target] = pd.to_numeric(df[col], errors="coerce") if col else None
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
