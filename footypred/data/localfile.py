"""The local match file: one CSV on your PC that the whole system reads.

    footy data download   build it from football-data.org (+ fallback)
    footy data update     append only the matches played since the last run
    footy data import     load it into the system (also automatic whenever
                          the file changes; see `local_data` in the config)

Goals are 90-minute scores. Rows come from football-data.org; when a
competition or season isn't in your API plan, domestic leagues are filled
from football-data.co.uk (which also adds shots, corners and odds).
"""

from __future__ import annotations

import io
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from footypred.data.names import canonical
from footypred.data.sources.football_data_org import (CompetitionSpec, FDOrgClient, FDOrgError,
                                                      NotAvailable, PlanRestricted, parse_matches,
                                                      resolve_competition, season_of)
from footypred.logging_utils import get_logger

log = get_logger("data.localfile")

COLUMNS = ["match_id", "source", "competition", "competition_name", "season", "date",
           "kickoff", "kickoff_tz", "matchday", "stage", "status", "home", "away", "home_raw",
           "away_raw", "fthg", "ftag", "hthg", "htag", "duration", "home_aet", "away_aet",
           "neutral", "hs", "as_", "hst", "ast", "hc", "ac", "hy", "ay", "hr", "ar",
           "odds_h", "odds_d", "odds_a", "odds_o25", "odds_u25", "fd_id", "updated_at"]
COUK_MAIN = "https://www.football-data.co.uk/mmz4281/{code}/{league}.csv"
COUK_EXTRA = "https://www.football-data.co.uk/new/{league}.csv"
# football-data.co.uk "extra leagues": one file per country, all seasons
COUK_EXTRA_CODES = {"ARG", "AUT", "BRA", "CHN", "DNK", "FIN", "IRL", "JPN", "MEX", "NOR", "POL",
                    "ROU", "RUS", "SWE", "SWZ", "USA"}


# ------------------------------------------------------------------ config
def specs_from_config(cfg) -> list[CompetitionSpec]:
    comps = (cfg.raw.get("football_data_org") or {}).get("competitions") or {}
    return [CompetitionSpec.from_config(k, v or {}) for k, v in comps.items()]


def csv_path(cfg) -> Path:
    p = Path((cfg.raw.get("local_data") or {}).get("csv") or "data/matches.csv")
    return p if p.is_absolute() else cfg.paths.root / p


def aliases_path(cfg) -> Path:
    p = Path((cfg.raw.get("local_data") or {}).get("aliases") or "data/aliases.csv")
    return p if p.is_absolute() else cfg.paths.root / p


def load_aliases(cfg) -> dict[str, str]:
    """Your own name merges: a CSV with columns from,to."""
    p = aliases_path(cfg)
    if not p.exists():
        return {}
    df = pd.read_csv(p, dtype=str).dropna()
    return dict(zip(df.iloc[:, 0].str.strip(), df.iloc[:, 1].str.strip()))


def apply_aliases(df: pd.DataFrame, aliases: dict[str, str]) -> pd.DataFrame:
    if aliases and len(df):
        df = df.copy()
        df["home"] = df["home"].map(lambda n: aliases.get(n, n))
        df["away"] = df["away"].map(lambda n: aliases.get(n, n))
    return df


def cup_codes(cfg) -> set[str]:
    cups = {s.key for s in specs_from_config(cfg) if s.cup}
    cups |= {k for k, v in (cfg.leagues or {}).items() if (v or {}).get("cup")}
    return cups or {"CL"}


# ------------------------------------------------------------------ csv io
INT_COLUMNS = ["season", "matchday", "fthg", "ftag", "hthg", "htag", "home_aet", "away_aet",
               "neutral", "hs", "as_", "hst", "ast", "hc", "ac", "hy", "ay", "hr", "ar", "fd_id"]


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in COLUMNS:
        if c not in df:
            df[c] = np.nan
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    for c in INT_COLUMNS:                     # whole numbers stay "3", not "3.0"
        df[c] = pd.to_numeric(df[c], errors="coerce").round().astype("Int64")
    return df[COLUMNS]


def read_csv(path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_csv(path, dtype={"match_id": str, "kickoff": str})
    return _normalise(df) if len(df) else pd.DataFrame(columns=COLUMNS)


def _sorted(df: pd.DataFrame) -> pd.DataFrame:
    return df.sort_values(["date", "kickoff", "competition", "home"], na_position="last")


def write_csv(df: pd.DataFrame, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _sorted(_normalise(df)).to_csv(path, index=False)
    return path


def append_csv(df: pd.DataFrame, path) -> int:
    """Append rows to the end of an existing file (no rewrite)."""
    if df.empty:
        return 0
    path = Path(path)
    header = not path.exists() or path.stat().st_size == 0
    _sorted(_normalise(df)).to_csv(path, mode="a", header=header, index=False)
    return len(df)


# -------------------------------------------------------- football-data.co.uk
# country of a co.uk "extra leagues" file -> its code
COUK_COUNTRIES = {"Argentina": "ARG", "Austria": "AUT", "Brazil": "BRA", "China": "CHN",
                  "Denmark": "DNK", "Finland": "FIN", "Ireland": "IRL", "Japan": "JPN",
                  "Mexico": "MEX", "Norway": "NOR", "Poland": "POL", "Romania": "ROU",
                  "Russia": "RUS", "Sweden": "SWE", "Switzerland": "SWZ", "USA": "USA"}
EXTRA_ODDS = (("odds_h", ["PSCH", "AvgCH", "B365CH", "PH", "AvgH"]),
              ("odds_d", ["PSCD", "AvgCD", "B365CD", "PD", "AvgD"]),
              ("odds_a", ["PSCA", "AvgCA", "B365CA", "PA", "AvgA"]))


def couk_team(name) -> str:
    """co.uk spelling -> the same short name the API rows get."""
    from footypred.data.names import clean_team_name
    return clean_team_name(canonical(str(name)))


def _couk_main(raw: bytes) -> pd.DataFrame:
    """A main-league file (one season, columns Div/HomeTeam/FTHG...)."""
    from footypred.data.sources.football_data import parse_csv
    df = parse_csv(raw, "", 0)
    src = pd.read_csv(io.BytesIO(raw), encoding="latin-1", on_bad_lines="skip")
    df["div"] = src.loc[df.index, "Div"].astype(str).str.strip().values if "Div" in src else None
    df["home"], df["away"] = df["home"].map(couk_team), df["away"].map(couk_team)
    return df.drop(columns=["league", "season"])


def _couk_extra(raw: bytes) -> pd.DataFrame:
    """An "extra leagues" file (one country, all seasons: Country/Home/HG...)."""
    src = pd.read_csv(io.BytesIO(raw), encoding="latin-1", on_bad_lines="skip")
    src = src.dropna(subset=["Date", "Home", "Away"])
    df = pd.DataFrame({
        "date": pd.to_datetime(src["Date"], dayfirst=True, errors="coerce"),
        "home": src["Home"].map(couk_team), "away": src["Away"].map(couk_team),
        "fthg": pd.to_numeric(src["HG"], errors="coerce"),
        "ftag": pd.to_numeric(src["AG"], errors="coerce"),
        "season": pd.to_numeric(src["Season"].astype(str).str[:4], errors="coerce"),
        "country": src["Country"].astype(str).str.strip() if "Country" in src else None,
        "kickoff": src["Time"].astype(str).where(src["Time"].notna(), None) if "Time" in src else None,
        "neutral": 0}, index=src.index)
    for target, cands in EXTRA_ODDS:
        col = next((c for c in cands if c in src.columns), None)
        df[target] = pd.to_numeric(src[col], errors="coerce") if col else np.nan
    return df.dropna(subset=["date"])


def _file_rows(df: pd.DataFrame, source: str, id_prefix: str) -> pd.DataFrame:
    """Parsed rows (with competition, competition_name, season) -> the file
    schema; only played matches."""
    from footypred.data.db import make_match_id
    df = df[df["fthg"].notna() & df["ftag"].notna()].copy()
    if df.empty:
        return pd.DataFrame(columns=COLUMNS)
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df["match_id"] = [id_prefix + make_match_id(d, h, a)
                      for d, h, a in zip(df["date"], df["home"], df["away"])]
    if "home_raw" not in df:
        df["home_raw"], df["away_raw"] = df["home"], df["away"]
    defaults = {"source": source, "status": "FINISHED", "stage": "REGULAR_SEASON",
                "duration": "REGULAR", "neutral": 0}
    for k, v in defaults.items():
        if k not in df:
            df[k] = v
    if source == "football-data.co.uk":
        df["kickoff_tz"] = "Europe/London"
    return _normalise(df)


def _couk_rows(raw: bytes, spec: CompetitionSpec, season: int, extra: bool) -> pd.DataFrame:
    df = _couk_extra(raw) if extra else _couk_main(raw)
    if extra:
        df = df[df["season"] == season]
    df = df.assign(competition=spec.key, competition_name=spec.name, season=season)
    return _file_rows(df.drop(columns=[c for c in ("div", "country") if c in df]),
                      "football-data.co.uk", "cuk-")


def fetch_couk(http, spec: CompetitionSpec, season: int) -> pd.DataFrame:
    """Fallback for a domestic league-season from football-data.co.uk."""
    from footypred.data.sources.football_data import season_code
    if not spec.couk:
        return pd.DataFrame(columns=COLUMNS)
    extra = spec.couk in COUK_EXTRA_CODES
    url = (COUK_EXTRA.format(league=spec.couk) if extra
           else COUK_MAIN.format(code=season_code(season), league=spec.couk))
    return _couk_rows(http.get_bytes(url), spec, season, extra)


# ------------------------------------------------------------------ fetching
def make_fetcher(cfg, progress=print, fallback: bool | None = None) -> "Fetcher":
    """Fetcher from the config: football-data.org with the API key from the
    environment (FOOTBALL_DATA_API_KEY) or the config, co.uk as fallback."""
    from footypred.data.http import HttpClient
    from footypred.data.sources.football_data_org import api_key_from
    fd = cfg.raw.get("football_data_org") or {}
    key = api_key_from(fd)
    client = None
    if key:
        client = FDOrgClient(key, base_url=fd.get("base_url") or "https://api.football-data.org/v4",
                             min_interval=float(fd.get("min_interval_seconds", 6.5)))
    elif progress:
        progress("⚠ no football-data.org API key (set FOOTBALL_DATA_API_KEY); "
                 "only football-data.co.uk will be used")
    if fallback is None:
        fallback = bool(fd.get("fallback_football_data_co_uk", True))
    return Fetcher(client, HttpClient.from_config(cfg) if fallback else None, fallback=fallback,
                   progress=progress, aliases=load_aliases(cfg))


def first_season(cfg) -> int:
    return int((cfg.raw.get("football_data_org") or {}).get("first_season", 2022))


class Fetcher:
    """One competition-season at a time, API first, co.uk as fallback."""

    def __init__(self, client: FDOrgClient | None, http=None, fallback: bool = True,
                 progress=print, aliases: dict | None = None):
        self.client, self.http, self.fallback = client, http, fallback
        self.aliases = aliases or {}
        self.progress = progress or (lambda *_: None)
        self._catalogue = None
        self.report: list[dict] = []

    def _api_id(self, spec):
        if spec.code or self.client is None:
            return spec.code
        if self._catalogue is None:
            try:
                self._catalogue = self.client.competitions()
            except FDOrgError as exc:
                log.warning("competition list unavailable: %s", exc)
                self._catalogue = []
        return resolve_competition(spec, self._catalogue)

    def season(self, spec: CompetitionSpec, season: int) -> pd.DataFrame:
        return apply_aliases(self._season(spec, season), self.aliases)

    def _season(self, spec: CompetitionSpec, season: int) -> pd.DataFrame:
        api_id = self._api_id(spec)
        reason = "competition not offered by football-data.org for this key"
        if api_id is not None and self.client is not None:
            try:
                raw = self.client.matches(api_id, season=season)
                df = _normalise(parse_matches(raw, spec)) if raw else pd.DataFrame(columns=COLUMNS)
                self._log(spec, season, "football-data.org", len(df))
                return df
            except PlanRestricted:
                reason = "not in your football-data.org plan"
            except NotAvailable:
                reason = "not found on football-data.org"
            except FDOrgError as exc:
                reason = f"football-data.org error ({exc})"
        if self.fallback and spec.couk and self.http is not None:
            try:
                df = fetch_couk(self.http, spec, season)
                self._log(spec, season, "football-data.co.uk", len(df), reason)
                return df
            except Exception as exc:
                reason += f"; football-data.co.uk fallback failed ({exc})"
        self._log(spec, season, None, 0, reason)
        return pd.DataFrame(columns=COLUMNS)

    def _log(self, spec, season, source, n, note=""):
        self.report.append({"competition": spec.key, "season": season, "source": source,
                            "rows": n, "note": note})
        label = f"{spec.name} {season}/{str(season + 1)[2:]}" if not spec.calendar_year \
            else f"{spec.name} {season}"
        if source:
            self.progress(f"  {label:<32} {n:>4} matches  ({source})"
                          + (f"  ← {note}" if note and source != "football-data.org" else ""))
        else:
            self.progress(f"  {label:<32}    0 matches  ✗ {note}")


def _dedupe(df: pd.DataFrame) -> pd.DataFrame:
    """Same game from two sources: keep football-data.org."""
    if df.empty:
        return df
    df = df.assign(_pref=(df["source"] != "football-data.org").astype(int))
    df = df.sort_values("_pref").drop_duplicates(["competition", "date", "home", "away"])
    return df.drop(columns="_pref").drop_duplicates("match_id")


def seasons_between(first: int, end_date: pd.Timestamp, calendar_year: bool) -> list[int]:
    last = season_of(str(end_date.date()), calendar_year)
    return list(range(first, last + 1))


def download(fetcher: Fetcher, specs: list[CompetitionSpec], first_season: int,
             end_date) -> pd.DataFrame:
    end_date = pd.Timestamp(end_date).normalize()
    frames = []
    for spec in specs:
        for season in seasons_between(first_season, end_date, spec.calendar_year):
            frames.append(fetcher.season(spec, season))
    df = pd.concat([f for f in frames if len(f)], ignore_index=True) if any(len(f) for f in frames) \
        else pd.DataFrame(columns=COLUMNS)
    if len(df):
        df = df[pd.to_datetime(df["date"]) <= end_date]
    return _dedupe(df)


def update(fetcher: Fetcher, specs: list[CompetitionSpec], path, first_season: int,
           end_date=None, margin_days: int = 3) -> dict:
    """Add matches played since the file's last date (per competition).
    New rows are appended; the file is only rewritten (after a .bak copy)
    when a stored result was corrected at the source."""
    path = Path(path)
    end_date = pd.Timestamp(end_date or pd.Timestamp.today()).normalize()
    have = read_csv(path)
    known_ids = set(have["match_id"].astype(str))
    known = KnownMatches(have)
    new_rows, corrections = [], []
    summary = {}
    for spec in specs:
        mine = have[have["competition"] == spec.key]
        if len(mine):
            since = pd.Timestamp(mine["date"].max()) - pd.Timedelta(days=margin_days)
            seasons = sorted({season_of(str(since.date()), spec.calendar_year),
                              season_of(str(end_date.date()), spec.calendar_year)})
        else:
            since = None
            seasons = seasons_between(first_season, end_date, spec.calendar_year)
        got = [fetcher.season(spec, s) for s in seasons]
        got = [g for g in got if len(g)]
        if not got:
            summary[spec.key] = 0
            continue
        df = pd.concat(got, ignore_index=True)
        d = pd.to_datetime(df["date"])
        df = df[(d <= end_date) & ((d >= since) if since is not None else True)]
        added = 0
        for row in df.to_dict("records"):
            mid = str(row["match_id"])
            key = (row["competition"], row["home"], row["away"], row["date"])
            if mid in known_ids:
                old = have.loc[have["match_id"] == mid].iloc[0]
                if any(_differs(old[c], row[c]) for c in ("fthg", "ftag", "hthg", "htag")):
                    corrections.append(row)
                continue
            if known.find(*key) is not None:     # same game from another source
                continue
            new_rows.append(row)
            known_ids.add(mid)
            known.add(*key)
            added += 1
        summary[spec.key] = added
    new_df = pd.DataFrame(new_rows, columns=COLUMNS)
    if corrections:
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        fixed = pd.DataFrame(corrections).set_index("match_id")
        have = have.set_index("match_id")
        have.update(fixed)
        all_rows = pd.concat([have.reset_index(), new_df], ignore_index=True)
        write_csv(all_rows, path)
    else:
        append_csv(new_df, path)
    return {"added": len(new_df), "corrected": len(corrections), "by_competition": summary,
            "rows": len(have) + len(new_df)}


def _differs(a, b) -> bool:
    if pd.isna(a) and pd.isna(b):
        return False
    try:
        return float(a) != float(b)
    except (TypeError, ValueError):
        return str(a) != str(b)


# ------------------------------------------------------------ merging files
class KnownMatches:
    """Matches already in the file, keyed by competition and teams; the
    same fixture within a day either side counts as the same match (a
    UTC date from the API vs a local date from another source)."""

    def __init__(self, df: pd.DataFrame | None = None):
        self.by_pair: dict[tuple, list[tuple[int, int]]] = {}
        if df is not None:
            for i, r in enumerate(zip(df["competition"], df["home"], df["away"], df["date"])):
                self.add(*r, i)

    def add(self, comp, home, away, date, i: int = -1) -> None:
        self.by_pair.setdefault((comp, home, away), []).append(
            (pd.Timestamp(date).toordinal(), i))

    def find(self, comp, home, away, date) -> int | None:
        d = pd.Timestamp(date).toordinal()
        for day, i in self.by_pair.get((comp, home, away), []):
            if abs(day - d) <= 1:
                return i
        return None


# generic CSVs: our column -> accepted header names (case-insensitive)
GENERIC_COLS = {"date": ["date", "match_date", "utc_date", "day"],
                "home": ["home", "hometeam", "home_team", "home team"],
                "away": ["away", "awayteam", "away_team", "away team"],
                "fthg": ["fthg", "hg", "home_goals", "home_score", "homegoals"],
                "ftag": ["ftag", "ag", "away_goals", "away_score", "awaygoals"],
                "hthg": ["hthg", "ht_home_goals"], "htag": ["htag", "ht_away_goals"],
                "season": ["season"], "competition": ["competition", "league", "div"]}
FILLABLE = ["hthg", "htag", "hs", "as_", "hst", "ast", "hc", "ac", "hy", "ay", "hr", "ar",
            "odds_h", "odds_d", "odds_a", "odds_o25", "odds_u25"]


def _plain_csv(raw: bytes) -> bytes:
    """Comma-separated ASCII, whatever was saved: UTF-8 (with or without a
    BOM) or Windows-1252, and ';' with decimal commas as European Excel
    writes it. Accents are folded (team names are folded anyway)."""
    from footypred.data.names import _ascii
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    first = text.split("\n", 1)[0]
    if first.count(";") > first.count(","):
        df = pd.read_csv(io.StringIO(text), sep=";", dtype=str, keep_default_na=False)
        df = df.apply(lambda c: c.str.replace(r"^(-?\d+),(\d+)$", r"\1.\2", regex=True))
        text = df.to_csv(index=False)
    return _ascii(text).encode("ascii", "ignore")


def _spec_for(code, specs: list[CompetitionSpec]) -> CompetitionSpec | None:
    code = str(code or "").strip()
    return next((s for s in specs if code and code.upper() in (s.key.upper(), (s.couk or "").upper())),
                None)


def read_other(path, specs: list[CompetitionSpec], competition: str | None = None):
    """Any supported CSV -> (rows in the file schema, format name, notes).

    Formats: a footypred match file; a football-data.co.uk league file
    (e.g. mmz4281/2425/T1.csv); a football-data.co.uk "extra leagues" file
    (e.g. new/NOR.csv, all seasons of one country); or any CSV with date,
    home, away and goal columns (give --competition if it has none)."""
    path = Path(path)
    raw = _plain_csv(path.read_bytes())
    cols = {c.strip() for c in pd.read_csv(io.BytesIO(raw), nrows=0, encoding="latin-1").columns}
    notes: list[str] = []
    forced = _spec_for(competition, specs) if competition else None
    if competition and forced is None:
        forced = CompetitionSpec(key=competition, name=competition)
        notes.append(f"'{competition}' isn't in your config's competitions; stored as is")

    def assign(df, codes, seasons=None):
        """Per-row competition from `codes` (or --competition) and season."""
        out_codes, out_names, cal = [], [], []
        unknown = set()
        for c in (codes if codes is not None else [None] * len(df)):
            sp = forced or _spec_for(c, specs)
            if sp is None:
                unknown.add(str(c))
                sp = CompetitionSpec(key=str(c), name=str(c))
            out_codes.append(sp.key); out_names.append(sp.name); cal.append(sp.calendar_year)
        if unknown:
            notes.append(f"competition code(s) {', '.join(sorted(unknown))} not in your config; "
                         "stored as is (use --competition to rename)")
        df = df.assign(competition=out_codes, competition_name=out_names)
        if seasons is None or pd.isna(seasons).all():
            df["season"] = [season_of(str(pd.Timestamp(d).date()), c)
                            for d, c in zip(df["date"], cal)]
        else:
            df["season"] = seasons
        return df

    if {"competition", "date", "home", "away", "fthg", "ftag"} <= cols:
        df = _normalise(pd.read_csv(io.BytesIO(raw), dtype={"match_id": str, "kickoff": str}))
        if forced:
            df = df.assign(competition=forced.key, competition_name=forced.name)
        return df[df["fthg"].notna() & df["ftag"].notna()], "footypred match file", notes
    if {"HomeTeam", "AwayTeam", "FTHG", "FTAG", "Date"} <= cols:
        df = _couk_main(raw)
        if forced is None and df["div"].isna().all():
            raise ValueError(f"{path.name}: no Div column — say which competition with --competition")
        df = assign(df, None if forced else df["div"].tolist()).drop(columns="div")
        return _file_rows(df, "football-data.co.uk", "cuk-"), "football-data.co.uk league file", notes
    if {"Home", "Away", "HG", "AG", "Date", "Season"} <= cols:
        df = _couk_extra(raw)
        codes = [COUK_COUNTRIES.get(c, c) for c in df["country"]] if "country" in df else None
        df = assign(df, None if forced else codes, df["season"]).drop(columns="country")
        return (_file_rows(df, "football-data.co.uk", "cuk-"),
                "football-data.co.uk extra-leagues file", notes)
    # generic
    src = pd.read_csv(io.BytesIO(raw), encoding="latin-1")
    lower = {c.strip().lower(): c for c in src.columns}
    pick = {k: next((lower[n] for n in names if n in lower), None) for k, names in GENERIC_COLS.items()}
    missing = [k for k in ("date", "home", "away", "fthg", "ftag") if pick[k] is None]
    if missing:
        raise ValueError(f"{path.name}: can't find column(s) for {', '.join(missing)}; "
                         f"columns are: {', '.join(map(str, src.columns))}")
    if forced is None and pick["competition"] is None:
        raise ValueError(f"{path.name}: no competition column — say which one with --competition")
    df = pd.DataFrame({k: src[c] for k, c in pick.items() if c is not None and k != "competition"})
    df["date"] = pd.to_datetime(df["date"], dayfirst=not df["date"].astype(str).str.match(
        r"^\d{4}-").all(), errors="coerce")
    df = df.dropna(subset=["date"])
    for k in ("fthg", "ftag", "hthg", "htag"):
        if k in df:
            df[k] = pd.to_numeric(df[k], errors="coerce")
    df["home"], df["away"] = df["home"].map(couk_team), df["away"].map(couk_team)
    codes = None if forced else src.loc[df.index, pick["competition"]].tolist()
    seasons = df.pop("season") if "season" in df else None
    if seasons is not None:
        seasons = pd.to_numeric(seasons.astype(str).str[:4], errors="coerce")
    df = assign(df, codes, seasons)
    return _file_rows(df, f"file:{path.name}", "csv-"), "generic CSV", notes


def match_names(incoming: set[str], existing: set[str]) -> tuple[dict, dict]:
    """Map names in an incoming file onto the spelling already in your
    file: identical after normalising (accents, punctuation, case) or
    nearly identical (one typo). Returns (mapping, suggestions) where
    suggestions are looser look-alikes for you to check."""
    from rapidfuzz import fuzz, process
    from footypred.data.names import _norm
    mapping, suggest = {}, {}
    pool = sorted(existing - incoming)              # a name in both files is the same team
    norm_pool = {_norm(n): n for n in pool}
    taken = set()
    for n in sorted(incoming - existing):
        hit = norm_pool.get(_norm(n))
        if hit is None and pool:
            best = process.extractOne(_norm(n), list(norm_pool), scorer=fuzz.ratio)
            if best and best[1] >= 92:
                hit = norm_pool[best[0]]
            elif pool:
                loose = process.extractOne(n, pool, scorer=fuzz.WRatio)
                if loose and loose[1] >= 80:
                    suggest[n] = (loose[0], round(float(loose[1])))
        if hit and hit not in taken:
            mapping[n] = hit
            taken.add(hit)
    return mapping, suggest


def csv_sources(paths, exclude=()) -> list[Path]:
    """Files and folders (every *.csv inside) -> CSV files to merge."""
    out, skip = [], {Path(x).resolve() for x in exclude}
    for p in map(Path, paths):
        p = p.expanduser()
        if not p.exists():
            raise ValueError(f"{p} not found")
        files = sorted(p.glob("*.csv")) if p.is_dir() else [p]
        out += [f for f in files if f.resolve() not in skip and f.suffix.lower() == ".csv"]
    if not out:
        raise ValueError("no CSV files to merge")
    return out


def merge(path, sources, specs: list[CompetitionSpec], first_season: int | None = None,
          end_date=None, competition: str | None = None, aliases: dict | None = None,
          fill: bool = False, dry_run: bool = False) -> dict:
    """Add the matches in `sources` that aren't in your file yet.

    New matches are appended to the end of the file. With fill=True,
    matches that are already there get their empty columns (odds, shots,
    half-time score ...) filled from the other file; that rewrites the file
    (old one kept as .bak). dry_run reports without writing anything."""
    path = Path(path)
    end_date = pd.Timestamp(end_date or pd.Timestamp.today()).normalize()
    have = read_csv(path)
    known = KnownMatches(have)
    names = {c: set(g["home"]) | set(g["away"]) for c, g in have.groupby("competition")}
    rep = {"files": [], "added": 0, "already": 0, "filled": 0, "skipped": 0,
           "by_competition": {}, "renamed": {}, "new_names": {}, "suggestions": {}}
    new_rows, fills = [], {}
    rep["errors"] = []
    for src in csv_sources(sources, exclude=[path, path.with_suffix(path.suffix + ".bak")]):
        try:
            df, fmt, notes = read_other(src, specs, competition)
        except Exception as exc:              # one bad file never stops the others
            msg = str(exc) if isinstance(exc, ValueError) else f"{src.name}: could not read ({exc})"
            rep["errors"].append(msg if msg.startswith(src.name) else f"{src.name}: {msg}")
            continue
        df = apply_aliases(df, aliases or {})
        n_read = len(df)
        keep = pd.to_datetime(df["date"]) <= end_date
        if first_season is not None:
            keep &= pd.to_numeric(df["season"], errors="coerce") >= first_season
        df = df[keep]
        f = {"file": str(src), "format": fmt, "matches": n_read, "skipped": n_read - len(df),
             "notes": notes, "added": 0, "already": 0}
        for comp, g in df.groupby("competition"):
            mine = names.get(comp, set())
            if mine:
                mapping, suggest = match_names(set(g["home"]) | set(g["away"]), mine)
                if mapping:
                    rep["renamed"].update(mapping)
                    df.loc[g.index, "home"] = g["home"].map(lambda n: mapping.get(n, n))
                    df.loc[g.index, "away"] = g["away"].map(lambda n: mapping.get(n, n))
                    g = df.loc[g.index]
                fresh = sorted((set(g["home"]) | set(g["away"])) - mine)
                if fresh:
                    rep["new_names"].setdefault(comp, set()).update(fresh)
                    rep["suggestions"].update({k: v for k, v in suggest.items() if k in fresh})
            names.setdefault(comp, set()).update(set(g["home"]) | set(g["away"]))
        for row in df.to_dict("records"):
            key = (row["competition"], row["home"], row["away"], row["date"])
            i = known.find(*key)
            by = rep["by_competition"].setdefault(row["competition"], {"added": 0, "already": 0})
            if i is not None:
                f["already"] += 1; by["already"] += 1
                if fill and i >= 0:
                    upd = {c: row[c] for c in FILLABLE
                           if pd.isna(have.iloc[i][c]) and not pd.isna(row.get(c))}
                    if upd:
                        fills.setdefault(i, {}).update(upd)
                continue
            new_rows.append(row)
            known.add(*key)
            f["added"] += 1; by["added"] += 1
        rep["files"].append(f)
    rep["added"] = len(new_rows)
    rep["already"] = sum(f["already"] for f in rep["files"])
    rep["skipped"] = sum(f["skipped"] for f in rep["files"])
    rep["filled"] = len(fills)
    rep["new_names"] = {k: sorted(v) for k, v in rep["new_names"].items()}
    new_df = pd.DataFrame(new_rows, columns=COLUMNS)
    if not dry_run:
        if fills:
            shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
            for i, upd in fills.items():
                for c, v in upd.items():
                    have.iat[i, have.columns.get_loc(c)] = v
            write_csv(pd.concat([have, new_df], ignore_index=True), path)
        elif not path.exists():
            write_csv(new_df, path)
        else:
            append_csv(new_df, path)
    rep["rows"] = len(have) + len(new_df)
    rep["dry_run"] = dry_run
    return rep


def render_merge(rep: dict, path) -> str:
    L = [f"  ✗ {e}" for e in rep.get("errors", [])]
    for f in rep["files"]:
        L.append(f"  {Path(f['file']).name}  ({f['format']}): {f['matches']} played matches"
                 + (f", {f['skipped']} outside the season/date range" if f["skipped"] else "")
                 + f" → +{f['added']} new, {f['already']} already in the file")
        L += [f"      ⚠ {n}" for n in f["notes"]]
    for comp, b in rep["by_competition"].items():
        if b["added"]:
            L.append(f"  {comp:<5} +{b['added']}")
    if rep["renamed"]:
        L.append("  names matched to your file: " + ", ".join(
            f"'{a}' → '{b}'" for a, b in sorted(rep["renamed"].items())))
    for comp, ns in rep["new_names"].items():
        L.append(f"  new team names in {comp} (promoted clubs, or a different spelling?): "
                 + ", ".join(n + (f" (~ {rep['suggestions'][n][0]}?)" if n in rep["suggestions"]
                                  else "") for n in ns))
    if rep["suggestions"]:
        L.append("  if a '~' pair is the same club, add 'name,existing name' to aliases.csv "
                 "and merge again")
    verb = "Would add" if rep["dry_run"] else "Added"
    L.append(f"\n{verb} {rep['added']} matches" +
             (f", fill {rep['filled']}" if rep["dry_run"] and rep["filled"] else
              f", filled empty columns on {rep['filled']}" if rep["filled"] else "")
             + f" · {rep['already']} were already in the file · {path} "
             + ("would have" if rep["dry_run"] else "now has") + f" {rep['rows']} matches")
    return "\n".join(L)


# ------------------------------------------------------------------ import
def to_db(df: pd.DataFrame, db, replace_synthetic: bool = True,
          aliases: dict | None = None) -> int:
    """Load file rows into the system database (90-minute results)."""
    if df.empty:
        return 0
    df = apply_aliases(df, aliases or {})
    if replace_synthetic and db.get_meta("data_source") == "synthetic":
        log.info("replacing the synthetic demo data with your match file")
        db.clear_matches()
    from footypred.data.db import make_match_id
    rows = df.rename(columns={"competition": "league"}).drop(columns=["match_id"])
    rows = rows[rows["fthg"].notna() & rows["ftag"].notna()].copy()
    rows["match_id"] = [make_match_id(d, h, a) for d, h, a in zip(
        pd.to_datetime(rows["date"]).dt.strftime("%Y-%m-%d"), rows["home"], rows["away"])]
    pruned = db.prune_source("local_csv", set(rows["match_id"]))
    if pruned:
        log.info("removed %d matches no longer in the file (or renamed)", pruned)
    n = db.upsert_matches(rows, source="local_csv")
    db.set_meta("data_source", "local_csv")
    return n


def sync_db(cfg, db, force: bool = False) -> int | None:
    """Re-import the local file when it (or the aliases file) changed since
    the last import. Returns the number of rows imported, or None."""
    path = csv_path(cfg)
    if not path.exists():
        return None
    if not force and not (cfg.raw.get("local_data") or {}).get("auto_import", True):
        return None
    st = path.stat()
    ap = aliases_path(cfg)
    sig = f"{path}:{st.st_mtime_ns}:{st.st_size}"
    if ap.exists():
        sig += f":{ap.stat().st_mtime_ns}"
    if not force and db.get_meta("csv_signature") == sig:
        return None
    n = to_db(read_csv(path), db, aliases=load_aliases(cfg))
    db.set_meta("csv_signature", sig)
    db.set_meta("csv_path", str(path))
    db.set_meta("last_update", pd.Timestamp.now().isoformat(timespec="seconds"))
    log.info("imported %d matches from %s", n, path)
    return n


def summarize(df: pd.DataFrame) -> str:
    if df.empty:
        return "no matches"
    g = df.groupby(["competition", "season"]).agg(matches=("match_id", "size"),
                                                  first=("date", "min"), last=("date", "max"),
                                                  source=("source", lambda s: ", ".join(sorted(set(s)))))
    return g.to_string()


def name_check(df: pd.DataFrame, threshold: float = 86) -> list[tuple[str, str, str, float]]:
    """Pairs of different names that look like the same team (possible
    duplicates to merge in the aliases file)."""
    from rapidfuzz import fuzz
    out = []
    for comp, g in df.groupby("competition"):
        names = sorted(set(g["home"]) | set(g["away"]))
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                r = fuzz.token_set_ratio(a, b)
                if r >= threshold:
                    out.append((comp, a, b, float(r)))
    # the same club spelled differently across competitions (e.g. CL vs league)
    by_comp = {c: set(g["home"]) | set(g["away"]) for c, g in df.groupby("competition")}
    cups = [c for c in by_comp if c == "CL"]
    for cup in cups:
        league_names = set().union(*(v for k, v in by_comp.items() if k != cup)) if len(by_comp) > 1 else set()
        for n in by_comp[cup] - league_names:
            from rapidfuzz import process
            best = process.extractOne(n, list(league_names), scorer=fuzz.token_set_ratio) if league_names else None
            if best and best[1] >= threshold:
                out.append((cup, n, best[0], float(best[1])))
    return out
