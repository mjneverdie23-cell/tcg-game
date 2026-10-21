"""Fixtures and results for the Schedule page: three days back, today and
five days ahead.

Sources, best first:
* football-data.org: every match of your competitions in the window,
  played or not, with kick-off time, live status, score and crests
  (one or two requests).
* football-data.co.uk's weekly fixture lists, for leagues the API doesn't
  give you (Süper Lig, Eliteserien; or every league when there's no API key).
* your match file, for results it already has.

The window is saved next to your match file as fixtures.csv and refreshed by
Update (Data tab) or the Schedule page's refresh button.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pandas as pd

from footypred.data import localfile as lf
from footypred.data.sources.football_data import first_available, parse_dates
from footypred.data.sources.football_data_org import FDOrgError, parse_matches
from footypred.logging_utils import get_logger

log = get_logger("data.schedule")

BACK, AHEAD = 3, 5
LIVE = {"IN_PLAY", "PAUSED", "LIVE"}
COUK_FIXTURES = "https://www.football-data.co.uk/fixtures.csv"
COUK_EXTRA_FIXTURES = "https://www.football-data.co.uk/new_league_fixtures.csv"
FIXTURE_COLUMNS = ["match_id", "source", "competition", "competition_name", "season", "date", "utc",
                   "status", "matchday", "stage", "home", "away", "home_raw", "away_raw", "fthg",
                   "ftag", "home_crest", "away_crest", "odds_h", "odds_d", "odds_a", "neutral",
                   "updated_at"]


def fixtures_path(cfg) -> Path:
    return lf.csv_path(cfg).with_name("fixtures.csv")


def _bounds(today=None) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp]:
    """UTC dates to cover so every local day from -3 to +5 is complete in
    any time zone (one day of margin each side)."""
    today = pd.Timestamp(today or pd.Timestamp.now(tz="UTC").tz_localize(None)).normalize()
    return today, today - pd.Timedelta(days=BACK + 1), today + pd.Timedelta(days=AHEAD + 1)


def _utc_from_uk(dates: pd.Series, times: pd.Series) -> pd.Series:
    """football-data.co.uk dates + UK kick-off times -> ISO UTC (None when
    the time is unknown)."""
    d = pd.to_datetime(dates, errors="coerce")
    t = times.astype("string").str.strip().str[:5]
    ts = pd.to_datetime(d.dt.strftime("%Y-%m-%d") + " " + t, errors="coerce", format="%Y-%m-%d %H:%M")
    local = ts.dt.tz_localize("Europe/London", ambiguous="NaT", nonexistent="shift_forward")
    out = local.dt.tz_convert("UTC").dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return out.where(out.notna(), None)


def _frame(rows) -> pd.DataFrame:
    df = pd.DataFrame(rows) if not isinstance(rows, pd.DataFrame) else rows.copy()
    for c in FIXTURE_COLUMNS:
        if c not in df:
            df[c] = np.nan
    return df[FIXTURE_COLUMNS]


# ------------------------------------------------------------------ sources
def fetch_api(client, specs, date_from, date_to, aliases=None) -> tuple[pd.DataFrame, list[str]]:
    """football-data.org: one call for all competitions with a code (per
    competition if that call is refused)."""
    by_code = {s.code: s for s in specs if s.code}
    notes, raw = [], []
    if not by_code:
        return _frame([]), notes
    try:
        raw = client.matches_between(str(date_from.date()), str(date_to.date()), list(by_code))
    except FDOrgError as exc:
        notes.append(f"football-data.org: {exc} — trying one competition at a time")
        for code in by_code:
            try:
                raw += client.matches(code, date_from=str(date_from.date()), date_to=str(date_to.date()))
            except FDOrgError as e:
                notes.append(f"  {by_code[code].name}: {e}")
    groups: dict[str, list] = {}
    for m in raw:
        code = (m.get("competition") or {}).get("code")
        if code in by_code:
            groups.setdefault(code, []).append(m)
    frames = [parse_matches(ms, by_code[c], include_unplayed=True) for c, ms in groups.items()]
    df = pd.concat([f for f in frames if len(f)], ignore_index=True) if any(len(f) for f in frames) \
        else pd.DataFrame()
    return _frame(lf.apply_aliases(df, aliases or {}) if len(df) else df), notes


def _couk_fixture_rows(raw: bytes, specs, extra: bool) -> pd.DataFrame:
    src = pd.read_csv(io.BytesIO(lf._plain_csv(raw)), encoding="latin-1", on_bad_lines="skip")
    if extra:
        if not {"Country", "Home", "Away", "Date"} <= set(src.columns):
            return _frame([])
        codes = src["Country"].astype(str).str.strip().map(lambda c: lf.COUK_COUNTRIES.get(c, c))
        home, away = src["Home"], src["Away"]
        odds = (["PSH", "PH", "AvgH", "B365H", "MaxH"], ["PSD", "PD", "AvgD", "B365D", "MaxD"],
                ["PSA", "PA", "AvgA", "B365A", "MaxA"])
    else:
        if not {"Div", "HomeTeam", "AwayTeam", "Date"} <= set(src.columns):
            return _frame([])
        codes = src["Div"].astype(str).str.strip()
        home, away = src["HomeTeam"], src["AwayTeam"]
        odds = (["PSH", "AvgH", "B365H"], ["PSD", "AvgD", "B365D"], ["PSA", "AvgA", "B365A"])
    spec = [lf._spec_for(c, specs) for c in codes]
    keep = np.array([s is not None for s in spec])
    if not keep.any():
        return _frame([])
    date = parse_dates(src["Date"])
    times = src["Time"] if "Time" in src else pd.Series([None] * len(src), index=src.index)
    df = pd.DataFrame({
        "source": "football-data.co.uk", "status": "SCHEDULED",
        "competition": [s.key if s else None for s in spec],
        "competition_name": [s.name if s else None for s in spec],
        "date": date.dt.strftime("%Y-%m-%d").values, "utc": _utc_from_uk(date, times).values,
        "home": home.map(lf.couk_team).values, "away": away.map(lf.couk_team).values,
        "home_raw": home.astype(str).values, "away_raw": away.astype(str).values,
        "odds_h": first_available(src, odds[0]).values, "odds_d": first_available(src, odds[1]).values,
        "odds_a": first_available(src, odds[2]).values}, index=src.index)
    df = df[keep & date.notna().values]
    df["match_id"] = ["cukfx-" + f"{d}_{h}_{a}".replace(" ", "") for d, h, a in
                      zip(df["date"], df["home"], df["away"])]
    return _frame(df)


def fetch_couk(http, specs, skip: set[str]) -> tuple[pd.DataFrame, list[str]]:
    """The week's fixtures from football-data.co.uk for competitions the API
    didn't cover (skip = covered competition codes)."""
    want = [s for s in specs if s.couk and s.key not in skip]
    if not want or http is None:
        return _frame([]), []
    notes, frames = [], []
    for url, extra in ((COUK_FIXTURES, False), (COUK_EXTRA_FIXTURES, True)):
        if not any((s.couk in lf.COUK_EXTRA_CODES) == extra for s in want):
            continue
        try:
            df = _couk_fixture_rows(http.get_bytes(url, use_cache=False), want, extra)
            frames.append(df)
        except Exception as exc:                   # optional source: never fatal
            notes.append(f"football-data.co.uk fixtures ({url.rsplit('/', 1)[-1]}): {exc}")
    df = pd.concat(frames, ignore_index=True) if frames else _frame([])
    return _frame(df[df["competition"].isin({s.key for s in want})]), notes


# ------------------------------------------------------------------ refresh
def refresh(cfg, client=None, http=None, today=None, say=None) -> dict:
    """Fetch the window and save fixtures.csv. client: FDOrgClient or None;
    http: an HttpClient for football-data.co.uk (None to skip it)."""
    say = say or (lambda *_: None)
    today, lo, hi = _bounds(today)
    specs, aliases = lf.specs_from_config(cfg), lf.load_aliases(cfg)
    notes, frames = [], []
    if client is not None:
        api, n = fetch_api(client, specs, lo, hi, aliases)
        frames.append(api)
        notes += n
        say(f"Schedule: {len(api)} matches from football-data.org")
    covered = set(frames[0]["competition"].dropna()) if frames and len(frames[0]) else set()
    couk, n = fetch_couk(http, specs, covered)
    notes += n
    if len(couk):
        frames.append(lf.apply_aliases(couk, aliases))
        say(f"Schedule: {len(couk)} fixtures from football-data.co.uk "
            f"({', '.join(sorted(set(couk['competition'])))})")
    df = pd.concat([f for f in frames if len(f)], ignore_index=True) if any(len(f) for f in frames) \
        else _frame([])
    df = _dedupe(df)
    path = fixtures_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.sort_values(["utc", "competition", "home"], na_position="last").to_csv(path, index=False)
    for n_ in notes:
        say("  " + n_)
    return {"matches": len(df), "notes": notes, "path": str(path)}


def _dedupe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.drop_duplicates("match_id")
    known, keep = lf.KnownMatches(), []
    for r in df.itertuples(index=False):           # API rows come first
        if known.find(r.competition, r.home, r.away, r.date) is None:
            known.add(r.competition, r.home, r.away, r.date)
            keep.append(True)
        else:
            keep.append(False)
    return df[keep]


# ------------------------------------------------------------------ window
def _result_rows(cfg, lo, hi) -> pd.DataFrame:
    """Results already in your match file, as schedule rows."""
    path = lf.csv_path(cfg)
    if not path.exists():
        return _frame([])
    m = lf.read_csv(path)
    d = pd.to_datetime(m["date"])
    m = m[(d >= lo) & (d <= hi)]
    if m.empty:
        return _frame([])
    utc = pd.Series([None] * len(m), index=m.index, dtype=object)
    k = m["kickoff"].astype("string")
    is_utc = m["kickoff_tz"].fillna("UTC").eq("UTC") & k.notna()
    utc[is_utc] = (m.loc[is_utc, "date"] + "T" + k[is_utc].str[:5] + ":00Z").values
    uk = ~m["kickoff_tz"].fillna("UTC").eq("UTC") & k.notna()
    if uk.any():
        utc[uk] = _utc_from_uk(m.loc[uk, "date"], k[uk]).values
    out = m.assign(utc=utc.values, status="FINISHED", home_crest=None, away_crest=None)
    return _frame(lf.apply_aliases(out, lf.load_aliases(cfg)))


def window(cfg, today=None) -> dict:
    """Everything the Schedule page shows: fixtures (with live status and
    scores where known) plus results from your match file, -3..+5 days."""
    today, lo, hi = _bounds(today)
    path = fixtures_path(cfg)
    fx = pd.read_csv(path, dtype={"match_id": str}) if path.exists() else _frame([])
    fx = _frame(fx)
    if len(fx):
        fx = fx[(pd.to_datetime(fx["date"]) >= lo) & (pd.to_datetime(fx["date"]) <= hi)]
    res = _result_rows(cfg, lo, hi)
    if len(fx) and len(res):                       # a stored result beats a stale fixture
        idx = lf.KnownMatches(res.reset_index(drop=True))
        r = res.reset_index(drop=True)
        for i in fx.index[~fx["status"].isin(["FINISHED"])]:
            j = idx.find(fx.at[i, "competition"], fx.at[i, "home"], fx.at[i, "away"], fx.at[i, "date"])
            if j is not None:
                fx.loc[i, ["status", "fthg", "ftag"]] = ["FINISHED", r.at[j, "fthg"], r.at[j, "ftag"]]
    both = _dedupe(pd.concat([fx, res], ignore_index=True)) if len(fx) or len(res) else _frame([])
    order = {s.key: i for i, s in enumerate(lf.specs_from_config(cfg))}
    rows = []
    for r in both.to_dict("records"):
        clean = {k: (None if v is None or (np.ndim(v) == 0 and pd.isna(v)) else v)
                 for k, v in r.items()}
        for g in ("fthg", "ftag"):
            if clean[g] is not None:
                clean[g] = int(clean[g])
        clean["order"] = order.get(clean["competition"], 99)
        clean["live"] = clean["status"] in LIVE
        rows.append(clean)
    rows.sort(key=lambda x: (x["utc"] or x["date"] + "T99", x["order"], x["home"]))
    fetched = (pd.Timestamp(path.stat().st_mtime, unit="s", tz="UTC").isoformat(timespec="seconds")
               if path.exists() else None)
    return {"today": str(today.date()), "back": BACK, "ahead": AHEAD, "fetched_at": fetched,
            "matches": rows}
