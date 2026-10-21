"""Build the Süper Lig and Eliteserien files for footypred from
football-data.co.uk downloads, and optionally add them to your match file.

football-data.org's free plan doesn't cover these two leagues, so they come
from football-data.co.uk instead:

    Süper Lig     one file per season   mmz4281/2526/T1.csv  (saved as 2025.csv ...)
    Eliteserien   one file, all seasons new/NOR.csv  (CSV or saved as NOR.xlsx)

What it does:
* Süper Lig: combines every season file into one.
* Eliteserien: keeps 2022 onward (your config's first_season).
* Both: drops unplayed fixtures and awarded 3-0 results (no game was
  played), and gives team names the same spelling as the rest of your data.

Writes data/extra/super_lig.csv and data/extra/eliteserien.csv, in the same
columns as your match file.

Usage (from the project folder):

    python scripts/extra_leagues.py                    # read footballdata/ in this folder
    python scripts/extra_leagues.py --download         # fetch the latest files first
    python scripts/extra_leagues.py --download --merge # ... and add new matches to your file
    python scripts/extra_leagues.py --super-lig "D:/footballdata/super lig" \\
        --eliteserien D:/footballdata/eliteserien/NOR.xlsx --merge

--merge adds only the matches your match file doesn't have yet (the same as
`footy data merge`). Run `footy train` afterwards so the model learns the
new matches.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))           # works without `pip install -e .` too

from footypred.config import load_config                      # noqa: E402
from footypred.data import localfile as lf                    # noqa: E402
from footypred.data.sources.football_data import season_code  # noqa: E402
from footypred.data.sources.football_data_org import season_of  # noqa: E402

COUK = "https://www.football-data.co.uk/"
LEAGUES = {
    #  key     output file          default input       code  calendar-year seasons
    "T1": ("super_lig.csv", "footballdata/super lig", "T1", False),
    "NOR": ("eliteserien.csv", "footballdata/eliteserien", "NOR", True),
}


def download(key: str, folder: Path, first_season: int) -> list[Path]:
    """Fetch the latest football-data.co.uk files into `folder`."""
    import requests
    folder.mkdir(parents=True, exist_ok=True)
    _, _, code, calendar = LEAGUES[key]
    headers = {"User-Agent": "footypred (personal use)"}
    if calendar:                                       # one file, every season
        jobs = [(f"{COUK}new/{code}.csv", folder / f"{code}.csv")]
    else:                                              # one file per season
        import pandas as pd
        last = season_of(str(pd.Timestamp.today().date()), False)
        jobs = [(f"{COUK}mmz4281/{season_code(s)}/{code}.csv", folder / f"{s}.csv")
                for s in range(first_season, last + 1)]
    got = []
    for url, dest in jobs:
        r = requests.get(url, headers=headers, timeout=60)
        if r.status_code == 404:
            print(f"  – {url}: not published yet")
            continue
        r.raise_for_status()
        dest.write_bytes(r.content)
        got.append(dest)
        print(f"  ↓ {url} → {dest}")
    return got


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--super-lig", help="folder of Süper Lig season files, or file(s) "
                                        "(default: footballdata/super lig)", nargs="+")
    ap.add_argument("--eliteserien", help="NOR.csv / NOR.xlsx, or its folder "
                                          "(default: footballdata/eliteserien)", nargs="+")
    ap.add_argument("--out", help="output folder (default: data/extra)")
    ap.add_argument("--first-season", type=int, help="skip seasons before this (default: "
                                                     "first_season in the config, 2022)")
    ap.add_argument("--download", action="store_true",
                    help="download the latest files from football-data.co.uk into the input "
                         "folders first")
    ap.add_argument("--merge", action="store_true",
                    help="also add the new matches to your match file (local_data.csv)")
    ap.add_argument("--only", choices=list(LEAGUES), help="build just one of the two")
    ap.add_argument("--config", help="footypred config (default: config/default.yaml)")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    first = args.first_season or lf.first_season(cfg)
    specs = lf.specs_from_config(cfg)
    aliases = lf.load_aliases(cfg)
    out_dir = Path(args.out) if args.out else cfg.paths.data_dir / "extra"
    out_dir.mkdir(parents=True, exist_ok=True)
    given = {"T1": args.super_lig, "NOR": args.eliteserien}
    written = []
    for key, (out_name, default_in, _, _) in LEAGUES.items():
        if args.only and key != args.only:
            continue
        sources = [Path(p) for p in (given[key] or [default_in])]
        if args.download:
            folder = sources[0] if sources[0].is_dir() or not sources[0].suffix else sources[0].parent
            print(f"Downloading {key} into {folder}")
            download(key, folder, first)
            sources = [folder]          # read what's there now (fresh files first by name)
        missing = [p for p in sources if not p.exists()]
        if missing:
            flag = "--super-lig" if key == "T1" else "--eliteserien"
            print(f"✗ {key}: {', '.join(map(str, missing))} not found — pass {flag} PATH, "
                  "or use --download")
            continue
        rows, rep = lf.build_league_file(sources, specs, competition=key, first_season=first,
                                         aliases=aliases)
        name = next((s.name for s in specs if s.key == key), key)
        print(lf.render_build(rep, f"\n{name} ({key})"))
        if rows.empty:
            print(f"  ✗ no matches from {first} on")
            continue
        path = lf.write_csv(rows, out_dir / out_name)
        print(f"  → {path}  ({len(rows)} matches)")
        written.append(path)

    if args.merge and written:
        target = lf.csv_path(cfg)
        print(f"\nAdding new matches to {target}")
        r = lf.merge(target, written, specs, first, aliases=aliases)
        print(lf.render_merge(r, target))
        if r["added"]:
            print("\nNext: run `footy train` so the model learns the new matches.")
    elif written:
        print("\nTo add them to your match file: "
              f"footy data merge {' '.join(str(p) for p in written)}   (or rerun with --merge)")
    return 0 if written else 1


if __name__ == "__main__":
    sys.exit(main())
