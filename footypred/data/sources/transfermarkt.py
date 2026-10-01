"""Transfermarkt: squad market values per club (league table pages)."""

from __future__ import annotations

import re

import pandas as pd
from bs4 import BeautifulSoup

from footypred.data.http import HttpClient
from footypred.data.names import canonical
from footypred.logging_utils import get_logger

log = get_logger("sources.transfermarkt")

LEAGUE_IDS = {"E0": "GB1", "SP1": "ES1", "I1": "IT1", "D1": "L1", "F1": "FR1",
              "N1": "NL1", "P1": "PO1"}
URL = "https://www.transfermarkt.com/x/startseite/wettbewerb/{tm}/saison_id/{season}"


def _parse_value(text: str) -> float | None:
    """'€1.21bn' / '€845.50m' / '€900k' -> EUR millions."""
    m = re.search(r"([\d.,]+)\s*(bn|m|k)", text.replace(",", "."))
    if not m:
        return None
    v = float(m.group(1))
    return v * {"bn": 1000, "m": 1, "k": 0.001}[m.group(2)]


def parse(html: str, season: int) -> pd.DataFrame:
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for tr in soup.select("table.items tbody tr"):
        name = tr.select_one("td.hauptlink a")
        cells = tr.select("td.rechts")
        if not name or not cells:
            continue
        val = _parse_value(cells[-1].get_text(" ", strip=True))
        if val is not None:
            rows.append({"team": canonical(name.get_text(strip=True)),
                         "date": f"{season}-08-01", "key": "market_value_m", "value": val})
    return pd.DataFrame(rows)


def fetch(client: HttpClient, leagues: list[str], seasons: list[int]) -> pd.DataFrame:
    frames = []
    for code in leagues:
        tm = LEAGUE_IDS.get(code)
        if not tm:
            continue
        for season in seasons:
            try:
                frames.append(parse(client.get_text(URL.format(tm=tm, season=season)), season))
            except Exception as exc:
                log.warning("transfermarkt %s %s failed: %s", code, season, exc)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
