"""ClubElo: external club Elo snapshots (one CSV per date)."""

from __future__ import annotations

import io

import pandas as pd

from footypred.data.http import HttpClient
from footypred.data.names import canonical
from footypred.logging_utils import get_logger

log = get_logger("sources.clubelo")

URL = "http://api.clubelo.com/{date}"


def fetch(client: HttpClient, dates: list[pd.Timestamp]) -> pd.DataFrame:
    """Returns team_info rows (team, date, key='clubelo', value)."""
    frames = []
    for d in dates:
        ds = pd.Timestamp(d).strftime("%Y-%m-%d")
        try:
            df = pd.read_csv(io.BytesIO(client.get_bytes(URL.format(date=ds))))
            frames.append(pd.DataFrame({"team": df["Club"].map(canonical), "date": ds,
                                        "key": "clubelo", "value": df["Elo"]}))
        except Exception as exc:
            log.warning("clubelo %s failed: %s", ds, exc)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
