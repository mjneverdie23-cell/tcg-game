import pandas as pd
import pytest

from footypred.data.db import Database
from footypred.data.names import NameResolver, TeamNameError, canonical
from footypred.data.sources import football_data, transfermarkt, understat


def test_db_merge_never_erases(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    db.upsert_matches(pd.DataFrame([{"date": "2025-01-04", "home": "Arsenal", "away": "Chelsea",
                                     "league": "E0", "season": 2024, "fthg": 2, "ftag": 1}]), "a")
    db.upsert_matches(pd.DataFrame([{"date": "2025-01-04", "home": "Arsenal", "away": "Chelsea",
                                     "home_xg": 1.8, "away_xg": 0.9, "fthg": None}]), "b")
    m = db.load_matches()
    assert len(m) == 1 and m.iloc[0]["fthg"] == 2 and m.iloc[0]["home_xg"] == 1.8


def test_football_data_parser():
    csv = (b"Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,HTHG,HTAG,HS,AS,HST,AST,PSCH,PSCD,PSCA,"
           b"PC>2.5,PC<2.5\nE0,16/08/2024,Man United,Fulham,1,0,0,0,14,10,5,2,1.6,4.2,5.5,1.9,1.95\n")
    df = football_data.parse_csv(csv, "E0", 2024)
    r = df.iloc[0]
    assert r["home"] == "Manchester United" and r["fthg"] == 1 and r["odds_o25"] == 1.9
    assert r["date"] == pd.Timestamp("2024-08-16")
    assert football_data.season_code(2024) == "2425"


def test_understat_parser():
    payload = [{"isResult": True, "datetime": "2024-08-17 15:00:00",
                "h": {"title": "Manchester City"}, "a": {"title": "Chelsea"},
                "goals": {"h": "2", "a": "0"}, "xG": {"h": "2.21", "a": "0.97"}}]
    df = understat.parse(payload, "E0", 2024)
    assert df.iloc[0]["home_xg"] == 2.21 and df.iloc[0]["away"] == "Chelsea"


def test_market_value_parser():
    assert transfermarkt._parse_value("€1.21bn") == pytest.approx(1210)
    assert transfermarkt._parse_value("€845.50m") == pytest.approx(845.5)


def test_name_resolution():
    r = NameResolver(["Manchester City", "Arsenal", "Real Madrid", "Paris Saint-Germain"])
    assert r.resolve("Man City") == "Manchester City"
    assert r.resolve("arsnal") == "Arsenal"
    assert r.resolve("PSG") == "Paris Saint-Germain"
    assert canonical("Nott'm Forest") == "Nottingham Forest"
    with pytest.raises(TeamNameError):
        r.resolve("Zzyzx United")
