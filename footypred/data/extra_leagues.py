"""Süper Lig and Eliteserien from football-data.co.uk (football-data.org's
free plan doesn't cover them).

    Süper Lig     one file per season   mmz4281/2526/T1.csv  (saved as 2025.csv ...)
    Eliteserien   one file, all seasons new/NOR.csv  (CSV, or saved as NOR.xlsx)

`build` combines every Süper Lig season into one file and keeps Eliteserien
from `first_season` on. It also drops unplayed fixtures and awarded 3-0
results, and gives team names the same spelling as the rest of your data.
The output is data/extra/super_lig.csv and eliteserien.csv. With merge=True,
only the matches your match file doesn't have yet are added to it.

Used by the web app (Data tab) and scripts/extra_leagues.py.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from footypred.data import localfile as lf
from footypred.data.sources.football_data import season_code
from footypred.data.sources.football_data_org import season_of

COUK = "https://www.football-data.co.uk/"
#        key: (output file, default input (relative to the project), co.uk code, calendar-year)
LEAGUES = {"T1": ("super_lig.csv", "footballdata/super lig", "T1", False),
           "NOR": ("eliteserien.csv", "footballdata/eliteserien", "NOR", True)}


def download(key: str, folder: Path, first_season: int, say=print) -> list[Path]:
    """Fetch the latest football-data.co.uk files for one league into `folder`."""
    import requests
    folder.mkdir(parents=True, exist_ok=True)
    _, _, code, calendar = LEAGUES[key]
    headers = {"User-Agent": "footypred (personal use)"}
    if calendar:                                       # one file, every season
        jobs = [(f"{COUK}new/{code}.csv", folder / f"{code}.csv")]
    else:                                              # one file per season
        last = season_of(str(pd.Timestamp.today().date()), False)
        jobs = [(f"{COUK}mmz4281/{season_code(s)}/{code}.csv", folder / f"{s}.csv")
                for s in range(first_season, last + 1)]
    got = []
    for url, dest in jobs:
        r = requests.get(url, headers=headers, timeout=60)
        if r.status_code == 404:
            say(f"  – {url}: not published yet")
            continue
        r.raise_for_status()
        dest.write_bytes(r.content)
        got.append(dest)
        say(f"  ↓ {url} → {dest}")
    return got


def build(cfg, sources: dict | None = None, out_dir=None, first_season: int | None = None,
          fetch: bool = False, merge: bool = False, only: str | None = None, say=print,
          base: Path | None = None) -> dict:
    """sources: {"T1": [paths], "NOR": [paths]} (folders or files); missing
    keys use the default folders under the project. Relative paths are read
    from `base` (default: the project folder). Returns what was written and
    the merge report."""
    base = Path(base or cfg.paths.root)
    first = first_season or lf.first_season(cfg)
    specs = lf.specs_from_config(cfg)
    aliases = lf.load_aliases(cfg)
    out_dir = Path(out_dir) if out_dir else cfg.paths.data_dir / "extra"
    out_dir.mkdir(parents=True, exist_ok=True)
    res = {"written": [], "reports": {}, "errors": [], "merge": None, "text": []}

    def log(msg):
        res["text"].append(msg)
        say(msg)

    for key, (out_name, default_in, _, _) in LEAGUES.items():
        if only and key != only:
            continue
        given = [p for p in ((sources or {}).get(key) or []) if str(p).strip()]
        paths = [Path(str(p).strip().strip('"').strip("'")).expanduser() for p in (given or [default_in])]
        paths = [p if p.is_absolute() else base / p for p in paths]
        name = next((s.name for s in specs if s.key == key), key)
        if fetch:
            folder = paths[0] if paths[0].is_dir() or not paths[0].suffix else paths[0].parent
            log(f"Downloading {name} into {folder}")
            try:
                download(key, folder, first, say=log)
            except Exception as exc:                 # keep going with what's on disk
                log(f"  ✗ download failed: {exc}")
            paths = [folder]                         # read what's there now
        missing = [p for p in paths if not p.exists()]
        if missing:
            res["errors"].append(f"{name}: {', '.join(map(str, missing))} not found")
            log(f"✗ {name}: {', '.join(map(str, missing))} not found")
            continue
        try:
            rows, rep = lf.build_league_file(paths, specs, competition=key, first_season=first,
                                             aliases=aliases)
        except ValueError as exc:
            res["errors"].append(f"{name}: {exc}")
            log(f"✗ {name}: {exc}")
            continue
        log(lf.render_build(rep, f"\n{name} ({key})"))
        res["reports"][key] = rep
        if rows.empty:
            log(f"  ✗ no matches from {first} on")
            continue
        path = lf.write_csv(rows, out_dir / out_name)
        log(f"  → {path}  ({len(rows)} matches)")
        res["written"].append(str(path))

    if merge and res["written"]:
        target = lf.csv_path(cfg)
        log(f"\nAdding new matches to {target}")
        r = lf.merge(target, res["written"], specs, first, aliases=aliases)
        log(lf.render_merge(r, target))
        res["merge"] = r
    res["text"] = "\n".join(res["text"])
    return res
