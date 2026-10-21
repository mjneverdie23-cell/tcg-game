"""Your local match file: download from football-data.org (mocked), the
incremental update, import into the system, and cup-aware league lookup."""

import pandas as pd
import pytest

from fd_mock import FakeCoUk, MockFDOrg, match
from footypred.config import load_config
from footypred.data import localfile as lf
from footypred.data.db import Database
from footypred.data.sources.football_data_org import CompetitionSpec, FDOrgClient

SPECS = [CompetitionSpec.from_config("E0", {"code": "PL", "name": "Premier League"}),
         CompetitionSpec.from_config("D1", {"code": "BL1", "name": "Bundesliga"}),
         CompetitionSpec.from_config("CL", {"code": "CL", "name": "Champions League", "cup": True}),
         CompetitionSpec.from_config("T1", {"area": "Turkey", "name": "Süper Lig", "couk": "T1"})]

COUK_T1 = (b"Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,HTHG,HTAG,B365H,B365D,B365A\n"
           b"T1,10/08/2025,19:00,Galatasaray,Fenerbahce,2,1,1,0,2.1,3.4,3.3\n"
           b"T1,17/08/2025,19:00,Besiktas,Galatasaray,0,0,0,0,2.8,3.3,2.4\n")


def _matches():
    return {
        "PL": [match(1, "PL", "2025-08-16T14:00:00Z", "Arsenal", "Chelsea", (2, 0), (1, 0)),
               match(2, "PL", "2025-08-23T14:00:00Z", "Liverpool", "Manchester City", (1, 1), (0, 1)),
               match(3, "PL", "2025-12-26T15:00:00Z", "Chelsea", "Arsenal", None, None,
                     status="TIMED")],
        "BL1": [match(10, "BL1", "2025-08-22T18:30:00Z", "Bayern Munich", "Borussia Dortmund",
                      (3, 1), (2, 0))],
        "CL": [match(20, "CL", "2025-09-17T19:00:00Z", "Arsenal", "Bayern Munich", (1, 2), (0, 1),
                     stage="LEAGUE_STAGE"),
               # final decided on penalties: the file keeps the 90-minute score
               match(21, "CL", "2026-05-30T19:00:00Z", "Bayern Munich", "Arsenal", (1, 1), (0, 0),
                     stage="FINAL", duration="PENALTY_SHOOTOUT", regular=(1, 1), extra=(1, 1))],
    }


@pytest.fixture()
def api():
    m = MockFDOrg(_matches(), throttle_once=True)
    yield m
    m.close()


def _fetcher(api, http=None):
    client = FDOrgClient("test-key", base_url=api.url, min_interval=0, sleep=lambda s: None)
    return lf.Fetcher(client, http or FakeCoUk({"2526/T1.csv": COUK_T1}), progress=None)


def test_download_cleans_names_scores_and_falls_back(api):
    f = _fetcher(api)
    df = lf.download(f, SPECS, 2025, "2026-10-20")
    assert set(df["competition"]) == {"E0", "D1", "CL", "T1"}
    assert len(df) == 2 + 1 + 2 + 2                       # unplayed fixture left out
    e0 = df[df["competition"] == "E0"]
    assert {"Arsenal", "Chelsea", "Liverpool", "Manchester City"} == set(e0["home"]) | set(e0["away"])
    final = df[df["match_id"] == "fd-21"].iloc[0]
    assert (final["home"], final["fthg"], final["ftag"], final["neutral"]) == ("Bayern Munich", 1, 1, 1)
    assert final["duration"] == "PENALTY_SHOOTOUT"
    t1 = df[df["competition"] == "T1"]
    assert (t1["source"] == "football-data.co.uk").all() and t1["odds_h"].notna().all()
    rep = {(r["competition"], r["season"]): r for r in f.report}
    assert "plan" in rep[("T1", 2025)]["note"]             # 403 on the API -> fallback
    assert any("season=2025" in c for c in api.calls)


def test_update_appends_in_place_and_handles_corrections(api, tmp_path):
    path = tmp_path / "matches.csv"
    lf.write_csv(lf.download(_fetcher(api), SPECS[:3], 2025, "2025-12-31"), path)
    before = path.read_text()
    # a new round is played
    api.matches["PL"].append(match(4, "PL", "2025-08-30T14:00:00Z", "Chelsea", "Liverpool",
                                   (0, 2), (0, 1)))
    r = lf.update(_fetcher(api), SPECS[:3], path, 2025, end_date="2025-12-31")
    assert r["added"] == 1 and r["corrected"] == 0 and r["by_competition"]["E0"] == 1
    after = path.read_text()
    assert after.startswith(before) and not (tmp_path / "matches.csv.bak").exists()
    assert lf.update(_fetcher(api), SPECS[:3], path, 2025, end_date="2025-12-31")["added"] == 0
    # the source corrects a recent score: the file is rewritten, with a backup
    api.matches["PL"][-1] = match(4, "PL", "2025-08-30T14:00:00Z", "Chelsea", "Liverpool",
                                  (1, 2), (0, 1))
    r = lf.update(_fetcher(api), SPECS[:3], path, 2025, end_date="2025-12-31")
    assert r["corrected"] == 1 and (tmp_path / "matches.csv.bak").exists()
    got = lf.read_csv(path).set_index("match_id").loc["fd-4"]
    assert (got["fthg"], got["ftag"]) == (1, 2)


def test_file_replaces_demo_data_and_follows_edits(tmp_path, matches):
    cfg = load_config(root=tmp_path)
    cfg.paths.ensure()
    db = Database(cfg.paths.db_file)
    db.upsert_matches(matches.head(50), source="synthetic")
    db.set_meta("data_source", "synthetic")
    rows = pd.DataFrame({
        "match_id": ["a", "b", "c"], "source": "football-data.org",
        "competition": ["E0", "E0", "CL"], "season": 2025,
        "date": ["2025-08-16", "2025-08-23", "2025-09-17"],
        "home": ["Arsenal", "Man Utd", "Arsenal"], "away": ["Chelsea", "Arsenal", "Bayern Munich"],
        "fthg": [2, 1, 1], "ftag": [0, 1, 2]})
    lf.write_csv(rows, lf.csv_path(cfg))
    assert lf.sync_db(cfg, db) == 3
    assert db.get_meta("data_source") == "local_csv" and db.count_matches() == 3
    assert lf.sync_db(cfg, db) is None                      # unchanged file: no re-import
    # cup games never move a team out of its league
    tl = db.team_league({"CL"})
    assert tl["Arsenal"] == "E0" and tl["Bayern Munich"] == "CL"
    # merging a name in the aliases file renames it everywhere (old rows go)
    lf.aliases_path(cfg).write_text("from,to\nMan Utd,Manchester United\n")
    assert lf.sync_db(cfg, db) == 3
    assert "Man Utd" not in db.teams() and "Manchester United" in db.teams()
    assert db.count_matches() == 3


def test_name_cleaning():
    from footypred.data.names import clean_team_name
    assert clean_team_name("FC Bayern München") == "Bayern Munich"
    assert clean_team_name("FK Bodø/Glimt") == "Bodo/Glimt"
    assert clean_team_name("1. FSV Mainz 05") == "Mainz 05"
    assert clean_team_name("Paris FC") == "Paris FC"


T1_FILE = ("Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,HTHG,HTAG,HS,AS,B365H,B365D,B365A\n"
           "T1,08/08/2025,19:00,Galatasaray,Goztep,3,0,1,0,15,6,1.30,5.50,9.00\n"
           "T1,16/08/2025,19:00,Buyuksehyr,Fenerbahce,1,1,0,1,10,12,4.20,3.80,1.80\n"
           "T1,23/08/2025,19:00,Fenerbahce,Galatasaray,2,2,1,1,13,11,2.40,3.50,2.80\n"
           "T1,13/04/2021,16:00,Kasimpasa,Galatasaray,0,2,0,1,8,14,3.10,3.40,2.30\n")
NOR_FILE = ("Country,League,Season,Date,Time,Home,Away,HG,AG,Res,PSCH,PSCD,PSCA\n"
            "Norway,Eliteserien,2021,15/05/2021,18:00,Bodo/Glimt,Molde,2,1,H,2.1,3.6,3.2\n"
            "Norway,Eliteserien,2024,06/04/2024,18:00,Bodo/Glimt,Molde,3,1,H,1.9,3.8,3.6\n"
            "Norway,Eliteserien,2024,07/04/2024,18:00,Lillestrom,Ham-Kam,1,0,H,2.4,3.4,2.9\n"
            "Norway,Eliteserien,2026,20/12/2026,18:00,Viking,Molde,,,,3.4,3.8,2.0\n")
MERGE_SPECS = SPECS + [CompetitionSpec.from_config(
    "NOR", {"area": "Norway", "name": "Eliteserien", "couk": "NOR", "calendar_year": True})]


def _have(path):
    """Your file: two Süper Lig games already came from the API (UTC dates)."""
    lf.write_csv(pd.DataFrame({
        "match_id": ["fd-1", "fd-2"], "source": "football-data.org", "competition": "T1",
        "season": 2025, "date": ["2025-08-09", "2025-08-16"], "kickoff": "16:00", "kickoff_tz": "UTC",
        "home": ["Galatasaray", "Basaksehir"], "away": ["Goztepe", "Fenerbahce"],
        "fthg": [3, 1], "ftag": [0, 1]}), path)


def test_merge_adds_only_missing_matches(tmp_path):
    path = tmp_path / "matches.csv"
    _have(path)
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "T1.csv").write_bytes(T1_FILE.encode("cp1252"))
    (tmp_path / "in" / "NOR.csv").write_text(NOR_FILE, encoding="utf-8")
    before = path.read_text()
    dry = lf.merge(path, [tmp_path / "in"], MERGE_SPECS, 2022, "2026-10-20", dry_run=True)
    assert dry["added"] == 3 and path.read_text() == before          # dry run writes nothing
    r = lf.merge(path, [tmp_path / "in"], MERGE_SPECS, 2022, "2026-10-20")
    # T1: the 08/08 game is the API's 09/08 (a day apart), 16/08 is the same game;
    # 2021 is before the first season. NOR: 2021 too old, the December game unplayed
    assert r["by_competition"]["T1"] == {"added": 1, "already": 2}
    assert r["by_competition"]["NOR"] == {"added": 2, "already": 0}
    assert path.read_text().startswith(before)                       # appended, not rewritten
    df = lf.read_csv(path)
    nor = df[df["competition"] == "NOR"]
    assert set(nor["season"]) == {2024} and "HamKam" in set(nor["away"])
    assert set(df[df["competition"] == "T1"]["home"]) == {"Galatasaray", "Basaksehir", "Fenerbahce"}
    assert ",3,0," in path.read_text()                               # goals stay whole numbers
    again = lf.merge(path, [tmp_path / "in"], MERGE_SPECS, 2022, "2026-10-20")
    assert again["added"] == 0 and again["already"] == 5


def test_merge_fill_names_formats_and_errors(tmp_path):
    path = tmp_path / "matches.csv"
    _have(path)
    t1 = tmp_path / "T1.csv"
    t1.write_bytes(T1_FILE.replace("Goztep", "Goztepee").encode("cp1252"))   # a typo
    r = lf.merge(path, [t1], MERGE_SPECS, 2022, "2026-10-20", fill=True)
    assert r["renamed"] == {"Goztepee": "Goztepe"} and r["filled"] == 2
    assert (tmp_path / "matches.csv.bak").exists()
    got = lf.read_csv(path).set_index("match_id")
    assert got.loc["fd-1", "odds_h"] == 1.30 and got.loc["fd-1", "hs"] == 15
    assert got.loc["fd-1", "kickoff"] == "16:00"                    # API kickoff (UTC) kept
    # European-Excel CSV (';', decimal commas, UTF-8 BOM) without a competition column
    xl = tmp_path / "excel.csv"
    xl.write_text("Date;Home;Away;home_goals;away_goals;B365H\n"
                  "13.09.2025;Trabzonspor;Samsunspor;2;1;1,85\n", encoding="utf-8-sig")
    bad = lf.merge(path, [xl], MERGE_SPECS, 2022, "2026-10-20")
    assert bad["added"] == 0 and "--competition" in bad["errors"][0]
    ok = lf.merge(path, [xl], MERGE_SPECS, 2022, "2026-10-20", competition="T1")
    assert ok["added"] == 1
    row = lf.read_csv(path).query("home == 'Trabzonspor'").iloc[0]
    assert (row["date"], row["competition"], row["season"]) == ("2025-09-13", "T1", 2025)
    with pytest.raises(ValueError, match="not found"):
        lf.merge(path, [tmp_path / "nope.csv"], MERGE_SPECS)


def test_build_league_file_combines_seasons_and_drops_awarded(tmp_path):
    """Season files -> one file; awarded 3-0s (no HT score, no shots) out;
    per-row odds fallback; xG kept; BOM and ISO dates handled."""
    head = "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,HTHG,HTAG,HS,AS,PSCH,PSCD,PSCA,AvgCH,AvgCD,AvgCA,HxG,AxG\n"
    (tmp_path / "2024.csv").write_text(
        "﻿" + head +
        "T1,09/08/2024,19:00,Galatasaray,Buyuksehyr,2,1,1,0,14,8,1.5,4.0,6.0,1.45,4.1,6.2,,\n"
        "T1,09/02/2025,17:00,Galatasaray,Ad. Demirspor,3,0,,,,,1.07,9.0,21.0,1.07,9.5,20.0,,\n",
        encoding="utf-8")
    (tmp_path / "2025.csv").write_text(
        head + "T1,08/08/2025,19:00,Goztep,Fenerbahce,0,3,0,1,7,15,,,,4.8,3.9,1.70,0.6,2.1\n",
        encoding="utf-8")
    rows, rep = lf.build_league_file([tmp_path], MERGE_SPECS, competition="T1", first_season=2022)
    assert len(rows) == 2 and set(rows["season"]) == {2024, 2025}
    assert "awarded" in rep["files"][0]["notes"][0] and "Adana Demirspor" in rep["files"][0]["notes"][0]
    g = rows.set_index("home")
    assert g.loc["Galatasaray", "away"] == "Basaksehir"
    assert g.loc["Galatasaray", "odds_h"] == 1.5 and g.loc["Goztepe", "odds_h"] == 4.8  # Pinnacle, else avg
    assert g.loc["Goztepe", "home_xg"] == 0.6 and pd.isna(g.loc["Galatasaray", "home_xg"])
    assert [b["label"] for b in rep["by_season"]] == ["2024/25", "2025/26"]
    # a 0-3 with shots and a half-time score is a real result: kept
    assert g.loc["Goztepe", "ftag"] == 3


def test_excel_country_file_and_iso_dates(tmp_path):
    pytest.importorskip("openpyxl")
    nor = pd.DataFrame({
        "Country": "Norway", "League": "Eliteserien", "Season": [2021, 2024, 2024],
        "Date": pd.to_datetime(["2021-05-15", "2024-04-06", "2024-11-03"]),
        "Time": [pd.Timestamp("2021-05-15 18:00").time(), pd.Timestamp("2024-04-06 18:00").time(),
                 pd.Timestamp("2024-11-03 16:00").time()],
        "Home": ["Bodo/Glimt", "Bodo/Glimt", "Ham-Kam"], "Away": ["Molde", "Molde", "Lillestrom"],
        "HG": [2, 3, 1], "AG": [1, 1, 0], "Res": ["H", "H", "H"],
        "PSCH": [2.1, None, 2.4], "PSCD": [3.6, None, 3.4], "PSCA": [3.2, None, 2.9],
        "AvgCH": [2.0, 1.85, 2.3], "AvgCD": [3.5, 3.7, 3.3], "AvgCA": [3.1, 3.5, 2.8]})
    nor.to_excel(tmp_path / "NOR.xlsx", index=False)
    rows, rep = lf.build_league_file([tmp_path / "NOR.xlsx"], MERGE_SPECS, competition="NOR",
                                     first_season=2022)
    assert list(rows["date"]) == ["2024-04-06", "2024-11-03"]     # not read as 4 June / 11 March
    assert list(rows["kickoff"]) == ["18:00", "16:00"] and list(rows["home"]) == ["Bodo/Glimt", "HamKam"]
    assert list(rows["odds_h"]) == [1.85, 2.4] and rep["by_season"][0]["label"] == "2024"
    assert rep["files"][0]["outside_range"] == 1


def test_old_file_layout_is_upgraded_once_on_append(tmp_path):
    path = tmp_path / "matches.csv"
    old_cols = [c for c in lf.COLUMNS if c not in ("home_xg", "away_xg")]
    pd.DataFrame([{"match_id": "fd-1", "competition": "E0", "season": 2025, "date": "2025-08-16",
                   "home": "Arsenal", "away": "Chelsea", "fthg": 2, "ftag": 0}],
                 columns=old_cols).to_csv(path, index=False)
    new = pd.DataFrame([{"match_id": "fd-2", "competition": "E0", "season": 2025, "date": "2025-08-23",
                         "home": "Chelsea", "away": "Arsenal", "fthg": 1, "ftag": 1, "home_xg": 1.2}])
    assert lf.append_csv(new, path) == 1
    assert path.read_text().splitlines()[0] == ",".join(lf.COLUMNS)
    df = lf.read_csv(path)
    assert list(df["match_id"]) == ["fd-1", "fd-2"] and df["home_xg"].iloc[1] == 1.2
    assert (tmp_path / "matches.csv.bak").exists()
    before = path.read_text()
    lf.append_csv(new.assign(match_id="fd-3", date="2025-08-30"), path)   # already current: plain append
    assert path.read_text().startswith(before)


def test_extra_leagues_script(tmp_path):
    """scripts/extra_leagues.py: raw downloads -> two files -> your match file."""
    import importlib.util
    import yaml
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("extra_leagues", root / "scripts" / "extra_leagues.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    c = yaml.safe_load((root / "config" / "default.yaml").read_text(encoding="utf-8"))
    c["paths"] = {k: str(tmp_path / v) for k, v in c["paths"].items()}
    c["local_data"]["csv"] = str(tmp_path / "matches.csv")
    (tmp_path / "cfg.yaml").write_text(yaml.safe_dump(c, allow_unicode=True), encoding="utf-8")
    (tmp_path / "sl").mkdir()
    (tmp_path / "sl" / "2025.csv").write_bytes(T1_FILE.encode("cp1252"))
    (tmp_path / "NOR.csv").write_text(NOR_FILE, encoding="utf-8")
    out = tmp_path / "extra"
    args = ["--config", str(tmp_path / "cfg.yaml"), "--super-lig", str(tmp_path / "sl"),
            "--eliteserien", str(tmp_path / "NOR.csv"), "--out", str(out), "--merge"]
    assert mod.main(args) == 0
    assert len(lf.read_csv(out / "super_lig.csv")) == 3 and len(lf.read_csv(out / "eliteserien.csv")) == 2
    assert len(lf.read_csv(tmp_path / "matches.csv")) == 5
    assert mod.main(args) == 0 and len(lf.read_csv(tmp_path / "matches.csv")) == 5   # nothing twice
