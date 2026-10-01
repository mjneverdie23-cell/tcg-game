"""SQLite store. One `matches` row per fixture; sources merge into it
column-wise (a source only fills the columns it knows about)."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

from footypred.logging_utils import get_logger

log = get_logger("data.db")

MATCH_COLUMNS = {
    "match_id": "TEXT PRIMARY KEY",
    "date": "TEXT NOT NULL",
    "season": "INTEGER",
    "league": "TEXT",
    "home": "TEXT NOT NULL",
    "away": "TEXT NOT NULL",
    "neutral": "INTEGER DEFAULT 0",
    "fthg": "INTEGER", "ftag": "INTEGER",        # full-time goals
    "hthg": "INTEGER", "htag": "INTEGER",        # half-time goals
    "hs": "INTEGER", "as_": "INTEGER",           # shots
    "hst": "INTEGER", "ast": "INTEGER",          # shots on target
    "hc": "INTEGER", "ac": "INTEGER",            # corners
    "hy": "INTEGER", "ay": "INTEGER",            # yellow cards
    "hr": "INTEGER", "ar": "INTEGER",            # red cards
    "home_xg": "REAL", "away_xg": "REAL",
    "odds_h": "REAL", "odds_d": "REAL", "odds_a": "REAL",   # closing 1X2
    "odds_o25": "REAL", "odds_u25": "REAL",                 # closing O/U 2.5
    "source": "TEXT",
}

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS matches (
    {", ".join(f"{k} {v}" for k, v in MATCH_COLUMNS.items())}
);
CREATE INDEX IF NOT EXISTS ix_matches_date ON matches(date);
CREATE INDEX IF NOT EXISTS ix_matches_teams ON matches(home, away);

CREATE TABLE IF NOT EXISTS team_info (      -- dated per-team external data
    team TEXT NOT NULL, date TEXT NOT NULL, key TEXT NOT NULL, value REAL,
    PRIMARY KEY (team, date, key)
);
CREATE TABLE IF NOT EXISTS weather (
    match_id TEXT PRIMARY KEY, temp_c REAL, precip_mm REAL, wind_kmh REAL
);
CREATE TABLE IF NOT EXISTS aliases (alias TEXT PRIMARY KEY, team TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


def make_match_id(date: str, home: str, away: str) -> str:
    norm = lambda s: "".join(c for c in s.lower() if c.isalnum())
    return f"{date}_{norm(home)}_{norm(away)}"


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path)
        try:
            yield con
            con.commit()
        finally:
            con.close()

    # ------------------------------------------------------------- matches
    def upsert_matches(self, df: pd.DataFrame, source: str) -> int:
        """Insert or merge rows. Non-null incoming values overwrite; nulls
        never erase data another source already supplied."""
        if df.empty:
            return 0
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        if "match_id" not in df:
            df["match_id"] = [make_match_id(d, h, a)
                              for d, h, a in zip(df["date"], df["home"], df["away"])]
        df["source"] = source
        cols = [c for c in MATCH_COLUMNS if c in df.columns]
        updates = ", ".join(f"{c}=COALESCE(excluded.{c}, matches.{c})"
                            for c in cols if c != "match_id")
        sql = (f"INSERT INTO matches ({', '.join(cols)}) VALUES "
               f"({', '.join('?' * len(cols))}) "
               f"ON CONFLICT(match_id) DO UPDATE SET {updates}")
        rows = df[cols].astype(object).where(df[cols].notna(), None).values.tolist()
        with self.connect() as con:
            con.executemany(sql, rows)
        log.debug("upserted %d rows from %s", len(rows), source)
        return len(rows)

    def load_matches(self, played_only: bool = True) -> pd.DataFrame:
        q = "SELECT * FROM matches"
        if played_only:
            q += " WHERE fthg IS NOT NULL AND ftag IS NOT NULL"
        with self.connect() as con:
            df = pd.read_sql_query(q + " ORDER BY date, match_id", con)
        df["date"] = pd.to_datetime(df["date"])
        return df

    def count_matches(self) -> int:
        with self.connect() as con:
            return con.execute("SELECT COUNT(*) FROM matches").fetchone()[0]

    # ----------------------------------------------------------- team info
    def upsert_team_info(self, df: pd.DataFrame) -> int:
        """df columns: team, date, key, value."""
        if df.empty:
            return 0
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        with self.connect() as con:
            con.executemany(
                "INSERT OR REPLACE INTO team_info (team, date, key, value) VALUES (?,?,?,?)",
                df[["team", "date", "key", "value"]].values.tolist())
        return len(df)

    def load_team_info(self) -> pd.DataFrame:
        with self.connect() as con:
            df = pd.read_sql_query("SELECT * FROM team_info ORDER BY date", con)
        df["date"] = pd.to_datetime(df["date"])
        return df

    # -------------------------------------------------------------- weather
    def upsert_weather(self, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        with self.connect() as con:
            con.executemany(
                "INSERT OR REPLACE INTO weather VALUES (?,?,?,?)",
                df[["match_id", "temp_c", "precip_mm", "wind_kmh"]].values.tolist())
        return len(df)

    def load_weather(self) -> pd.DataFrame:
        with self.connect() as con:
            return pd.read_sql_query("SELECT * FROM weather", con)

    # -------------------------------------------------------- aliases/meta
    def add_aliases(self, mapping: dict[str, str]) -> None:
        with self.connect() as con:
            con.executemany("INSERT OR REPLACE INTO aliases VALUES (?,?)",
                            list(mapping.items()))

    def load_aliases(self) -> dict[str, str]:
        with self.connect() as con:
            return dict(con.execute("SELECT alias, team FROM aliases").fetchall())

    def set_meta(self, key: str, value: str) -> None:
        with self.connect() as con:
            con.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, value))

    def get_meta(self, key: str, default: str | None = None) -> str | None:
        with self.connect() as con:
            row = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def teams(self) -> list[str]:
        with self.connect() as con:
            rows = con.execute(
                "SELECT home FROM matches UNION SELECT away FROM matches").fetchall()
        return sorted(r[0] for r in rows)

    def team_league(self) -> dict[str, str]:
        """Most recent league per team."""
        df = self.load_matches(played_only=False)
        if df.empty:
            return {}
        long = pd.concat([df[["date", "home", "league"]].rename(columns={"home": "team"}),
                          df[["date", "away", "league"]].rename(columns={"away": "team"})])
        return long.sort_values("date").groupby("team")["league"].last().to_dict()
