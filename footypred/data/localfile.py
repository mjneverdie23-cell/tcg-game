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
def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in COLUMNS:
        if c not in df:
            df[c] = np.nan
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
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
def _couk_rows(raw: bytes, spec: CompetitionSpec, season: int, extra: bool) -> pd.DataFrame:
    if not extra:
        from footypred.data.sources.football_data import parse_csv
        df = parse_csv(raw, spec.key, season)
        kick = None
    else:
        src = pd.read_csv(io.BytesIO(raw), encoding="latin-1", on_bad_lines="skip")
        src = src[src["Season"].astype(str).str[:4] == str(season)]
        df = pd.DataFrame({
            "date": pd.to_datetime(src["Date"], dayfirst=True, errors="coerce"),
            "home": src["Home"].map(canonical), "away": src["Away"].map(canonical),
            "fthg": src["HG"], "ftag": src["AG"], "season": season, "league": spec.key})
        for target, cands in (("odds_h", ["PSCH", "AvgCH", "B365CH", "PH", "AvgH"]),
                              ("odds_d", ["PSCD", "AvgCD", "B365CD", "PD", "AvgD"]),
                              ("odds_a", ["PSCA", "AvgCA", "B365CA", "PA", "AvgA"])):
            col = next((c for c in cands if c in src.columns), None)
            df[target] = pd.to_numeric(src[col], errors="coerce").values if col else np.nan
        kick = src["Time"].values if "Time" in src else None
        df = df.dropna(subset=["date", "fthg", "ftag"])
    if df.empty:
        return pd.DataFrame(columns=COLUMNS)
    from footypred.data.db import make_match_id
    out = df.rename(columns={"league": "competition"}).copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    out["match_id"] = ["cuk-" + make_match_id(d, h, a)
                       for d, h, a in zip(out["date"], out["home"], out["away"])]
    out["home_raw"], out["away_raw"] = out["home"], out["away"]
    out["source"] = "football-data.co.uk"
    out["competition"] = spec.key
    out["competition_name"] = spec.name
    out["status"] = "FINISHED"
    out["stage"] = "REGULAR_SEASON"
    out["duration"] = "REGULAR"
    out["neutral"] = 0
    out["kickoff_tz"] = "Europe/London"
    if kick is not None:
        out["kickoff"] = kick[:len(out)] if len(kick) == len(out) else None
    return _normalise(out)


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
    known_keys = set(zip(have["competition"], have["date"], have["home"], have["away"]))
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
            key = (row["competition"], row["date"], row["home"], row["away"])
            if mid in known_ids:
                old = have.loc[have["match_id"] == mid].iloc[0]
                if any(_differs(old[c], row[c]) for c in ("fthg", "ftag", "hthg", "htag")):
                    corrections.append(row)
                continue
            if key in known_keys:
                continue
            new_rows.append(row)
            known_ids.add(mid)
            known_keys.add(key)
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
