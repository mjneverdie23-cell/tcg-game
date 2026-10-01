"""FIFA men's world ranking points for national teams."""

from __future__ import annotations

import json

import pandas as pd

from footypred.data.http import HttpClient
from footypred.data.names import canonical
from footypred.logging_utils import get_logger

log = get_logger("sources.fifa")

URL = "https://inside.fifa.com/api/ranking-overview?locale=en&dateId={date_id}"
DATES_URL = "https://inside.fifa.com/api/ranking-overview/dates?locale=en&gender=1"


def parse(payload: dict, date: str) -> pd.DataFrame:
    rows = [{"team": canonical(r["rankingItem"]["name"]), "date": date,
             "key": "fifa_points", "value": float(r["rankingItem"]["totalPoints"])}
            for r in payload.get("rankings", [])]
    return pd.DataFrame(rows)


def fetch(client: HttpClient, max_dates: int = 12) -> pd.DataFrame:
    frames = []
    try:
        dates = json.loads(client.get_text(DATES_URL))["dates"][-max_dates:]
    except Exception as exc:
        log.warning("fifa ranking dates failed: %s", exc)
        return pd.DataFrame()
    for d in dates:
        try:
            payload = json.loads(client.get_text(URL.format(date_id=d["id"])))
            frames.append(parse(payload, d["date"][:10]))
        except Exception as exc:
            log.warning("fifa ranking %s failed: %s", d.get("id"), exc)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
