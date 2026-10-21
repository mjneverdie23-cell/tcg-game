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
