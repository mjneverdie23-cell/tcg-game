"""Build the Süper Lig and Eliteserien files for footypred from
football-data.co.uk downloads, and optionally add them to your match file.

The web app does the same from the Data tab (Süper Lig + Eliteserien card);
this script is for doing it from a terminal or a scheduled task.

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
`footy data merge`). Train the model afterwards (Data tab > Train, or
`footy train`).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))           # works without `pip install -e .` too

from footypred.config import load_config            # noqa: E402
from footypred.data.extra_leagues import LEAGUES, build  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--super-lig", nargs="+", help="folder of Süper Lig season files, or "
                                                  "file(s) (default: footballdata/super lig)")
    ap.add_argument("--eliteserien", nargs="+", help="NOR.csv / NOR.xlsx, or its folder "
                                                    "(default: footballdata/eliteserien)")
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
    res = build(cfg, {"T1": args.super_lig, "NOR": args.eliteserien}, out_dir=args.out,
                first_season=args.first_season, fetch=args.download, merge=args.merge,
                only=args.only, base=Path.cwd())
    if res["merge"] and res["merge"]["added"]:
        print("\nNext: train the model (web app Data tab, or `footy train`).")
    elif res["written"] and not args.merge:
        print("\nTo add them to your match file: rerun with --merge, or "
              f"footy data merge {' '.join(res['written'])}")
    return 0 if res["written"] else 1


if __name__ == "__main__":
    sys.exit(main())
