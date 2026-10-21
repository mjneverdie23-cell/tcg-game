"""football-data.org API (v4): fixtures and results for leagues and the
Champions League.

    Free plan: an API key (register at football-data.org), 10 requests per
    minute, a fixed set of competitions. Competitions or seasons outside
    your plan answer HTTP 403; they are reported (and, for domestic
    leagues, can be filled from football-data.co.uk instead).

Set the key in the environment as FOOTBALL_DATA_API_KEY (preferred) or in
the config under football_data_org.api_key. It is sent only to
api.football-data.org in the X-Auth-Token header.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import pandas as pd
import requests

from footypred.data.names import clean_team_name
from footypred.logging_utils import get_logger

log = get_logger("sources.football_data_org")

BASE_URL = "https://api.football-data.org/v4"


class FDOrgError(RuntimeError):
    pass


class PlanRestricted(FDOrgError):
    """403: the competition or season isn't in your football-data.org plan."""


class NotAvailable(FDOrgError):
    pass


def api_key_from(cfg_section: dict | None) -> str | None:
    return os.environ.get("FOOTBALL_DATA_API_KEY") or (cfg_section or {}).get("api_key") or None


class FDOrgClient:
    def __init__(self, api_key: str, base_url: str = BASE_URL, min_interval: float = 6.5,
                 max_retries: int = 5, timeout: float = 30, session=None, sleep=time.sleep):
        if not api_key:
            raise FDOrgError("no football-data.org API key: set FOOTBALL_DATA_API_KEY "
                             "(free key at https://www.football-data.org/client/register)")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers["X-Auth-Token"] = api_key
        self._sleep = sleep
        self._last = 0.0
        self.requests_made = 0

    def get(self, path: str, **params) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        for attempt in range(self.max_retries):
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                self._sleep(wait)
            self._last = time.monotonic()
            try:
                r = self.session.get(url, params={k: v for k, v in params.items() if v is not None},
                                     timeout=self.timeout)
            except requests.RequestException as exc:
                log.warning("football-data.org %s failed (%s); retrying", path, exc)
                self._sleep(2 ** (attempt + 1))
                continue
            self.requests_made += 1
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:                 # per-minute quota used up
                reset = r.headers.get("X-RequestCounter-Reset") or r.headers.get("Retry-After")
                pause = float(reset) + 1 if reset and str(reset).isdigit() else 61.0
                log.info("rate limit reached; waiting %.0fs", pause)
                self._sleep(pause)
                continue
            msg = _error_message(r)
            if r.status_code == 403:
                raise PlanRestricted(msg)
            if r.status_code == 404:
                raise NotAvailable(msg)
            if r.status_code in (400, 401):
                raise FDOrgError(f"HTTP {r.status_code}: {msg}")
            log.warning("football-data.org %s: HTTP %s %s; retrying", path, r.status_code, msg)
            self._sleep(2 ** (attempt + 1))
        raise FDOrgError(f"giving up on {path} after {self.max_retries} attempts")

    # ----------------------------------------------------------- endpoints
    def competitions(self) -> list[dict]:
        return self.get("competitions").get("competitions", [])

    def matches(self, competition: str | int, season: int | None = None,
                date_from: str | None = None, date_to: str | None = None) -> list[dict]:
        data = self.get(f"competitions/{competition}/matches", season=season,
                        dateFrom=date_from, dateTo=date_to)
        return data.get("matches", [])

    def matches_between(self, date_from: str, date_to: str,
                        competitions: list[str] | None = None) -> list[dict]:
        """Every match (played or not) between two dates across competitions,
        in chunks of at most 10 days (the API's limit for this call)."""
        out, start, end = [], pd.Timestamp(date_from), pd.Timestamp(date_to)
        while start <= end:
            stop = min(start + pd.Timedelta(days=9), end)
            data = self.get("matches", dateFrom=str(start.date()), dateTo=str(stop.date()),
                            competitions=",".join(competitions) if competitions else None)
            out += data.get("matches", [])
            start = stop + pd.Timedelta(days=1)
        return out


def _error_message(r) -> str:
    try:
        return r.json().get("message", r.text[:200])
    except ValueError:
        return r.text[:200]


# ----------------------------------------------------------------- mapping
@dataclass
class CompetitionSpec:
    key: str                    # our code, e.g. E0, CL, T1, NOR
    name: str
    code: str | None = None     # football-data.org code, e.g. PL
    area: str | None = None     # used to discover the code when it isn't given
    cup: bool = False
    couk: str | None = None     # football-data.co.uk fallback code
    calendar_year: bool = False  # season runs Jan-Dec (Eliteserien)

    @classmethod
    def from_config(cls, key: str, d: dict) -> "CompetitionSpec":
        return cls(key=key, name=d.get("name", key), code=d.get("code"), area=d.get("area"),
                   cup=bool(d.get("cup", False)), couk=d.get("couk", key if not d.get("cup") else None),
                   calendar_year=bool(d.get("calendar_year", False)))


def _fold(s: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


def resolve_competition(spec: CompetitionSpec, catalogue: list[dict] | None) -> str | int | None:
    """football-data.org code/id for a spec, discovering it by area + name
    from the competitions list when no code is configured."""
    if spec.code:
        return spec.code
    for c in catalogue or []:
        area = (c.get("area") or {}).get("name", "")
        if _fold(area) == _fold(spec.area or "") and _fold(spec.name) in _fold(c.get("name", "")):
            return c.get("code") or c.get("id")
    return None


def season_of(utc_date: str, calendar_year: bool, season_obj: dict | None = None) -> int:
    if season_obj and season_obj.get("startDate"):
        return int(season_obj["startDate"][:4])
    d = pd.Timestamp(utc_date)
    return d.year if (calendar_year or d.month >= 7) else d.year - 1


def parse_matches(raw: list[dict], spec: CompetitionSpec, include_unplayed: bool = False) -> pd.DataFrame:
    """API match objects -> rows in the footypred CSV schema.

    Goals are the 90-minute score: for knockout ties that went to extra
    time or penalties the API's regularTime is used (fullTime then includes
    extra time), and the extra-time score is kept separately."""
    rows = []
    for m in raw:
        status = m.get("status")
        if status != "FINISHED" and not include_unplayed:
            continue                       # AWARDED (forfeits), POSTPONED, SCHEDULED ...
        sc = m.get("score") or {}
        duration = sc.get("duration") or "REGULAR"
        ft = sc.get("fullTime") or {}
        reg = sc.get("regularTime") or (ft if duration == "REGULAR" else {})
        ht = sc.get("halfTime") or {}
        et = sc.get("extraTime") or {}
        home_raw = (m.get("homeTeam") or {}).get("name") or ""
        away_raw = (m.get("awayTeam") or {}).get("name") or ""
        if not home_raw or not away_raw:
            continue
        aet_h = aet_a = None
        if duration != "REGULAR" and reg.get("home") is not None:
            aet_h = reg["home"] + (et.get("home") or 0)
            aet_a = reg["away"] + (et.get("away") or 0)
        utc = m.get("utcDate") or ""
        rows.append({
            "match_id": f"fd-{m.get('id')}", "source": "football-data.org",
            "competition": spec.key, "competition_name": spec.name,
            "season": season_of(utc, spec.calendar_year, m.get("season")),
            "date": utc[:10], "kickoff": utc[11:16] or None, "kickoff_tz": "UTC",
            "matchday": m.get("matchday"), "stage": m.get("stage"), "status": status,
            "home": clean_team_name(home_raw), "away": clean_team_name(away_raw),
            "home_raw": home_raw, "away_raw": away_raw,
            "fthg": reg.get("home"), "ftag": reg.get("away"),
            "hthg": ht.get("home"), "htag": ht.get("away"),
            "duration": duration, "home_aet": aet_h, "away_aet": aet_a,
            "neutral": 1 if m.get("stage") == "FINAL" else 0,
            "fd_id": m.get("id"), "updated_at": m.get("lastUpdated"),
            # for the schedule (not part of the match file)
            "utc": utc or None, "home_crest": (m.get("homeTeam") or {}).get("crest"),
            "away_crest": (m.get("awayTeam") or {}).get("crest"),
        })
    return pd.DataFrame(rows)
