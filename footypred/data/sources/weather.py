"""Open-Meteo historical weather at the home team's city on match day."""

from __future__ import annotations

import json

import pandas as pd

from footypred.data.http import HttpClient
from footypred.logging_utils import get_logger

log = get_logger("sources.weather")

URL = "https://archive-api.open-meteo.com/v1/archive"

# approximate stadium coordinates for clubs we care about; extend freely
CITY = {
    "Arsenal": (51.555, -0.108), "Chelsea": (51.482, -0.191),
    "Liverpool": (53.431, -2.961), "Manchester City": (53.483, -2.200),
    "Manchester United": (53.463, -2.291), "Tottenham": (51.604, -0.066),
    "Real Madrid": (40.453, -3.688), "Barcelona": (41.381, 2.123),
    "Bayern Munich": (48.219, 11.625), "Paris Saint-Germain": (48.841, 2.253),
    "Inter Milan": (45.478, 9.124), "AC Milan": (45.478, 9.124),
    "Juventus": (45.110, 7.641), "Borussia Dortmund": (51.493, 7.452),
}


def fetch(client: HttpClient, matches: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, m in matches.iterrows():
        loc = CITY.get(m["home"])
        if not loc:
            continue
        day = pd.Timestamp(m["date"]).strftime("%Y-%m-%d")
        try:
            data = json.loads(client.get_text(
                URL, latitude=loc[0], longitude=loc[1], start_date=day, end_date=day,
                daily="temperature_2m_mean,precipitation_sum,wind_speed_10m_max"))["daily"]
            rows.append({"match_id": m["match_id"], "temp_c": data["temperature_2m_mean"][0],
                         "precip_mm": data["precipitation_sum"][0],
                         "wind_kmh": data["wind_speed_10m_max"][0]})
        except Exception as exc:
            log.debug("weather %s failed: %s", m["match_id"], exc)
    return pd.DataFrame(rows)
