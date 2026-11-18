"""League tables for the Schedule tab's match panel.

Built from your results (the match file, plus finished games the schedule
has fetched but the file doesn't have yet), so they work offline and
cover every league you follow, including the ones football-data.org
doesn't. Points 3 / 1 / 0, then each league's tie-break:

    goal difference, goals scored         Premier League, Bundesliga, Ligue 1,
                                          Eredivisie, Primeira Liga, Eliteserien,
                                          Champions League (league phase)
    head-to-head points, head-to-head     La Liga, Serie A, Süper Lig
    goal difference, then goal difference
    and goals scored

(set standings.tiebreak per league in config/local.yaml). Points
deductions aren't in the results: add them under standings.deductions,
e.g. {E0: {2026: {Everton: 10}}}.

Cup matches show the cup's league phase where it has one (Champions
League from 2024-25), otherwise each team's domestic table.
"""

from __future__ import annotations

import pandas as pd

H2H_LEAGUES = {"SP1", "I1", "T1"}
LEAGUE_PHASE = {"CL": 2024}           # cup -> first season played as one league table
LEAGUE_PHASE_ENDS = (2, 1)            # league phase games are before 1 February


def season_of(date, calendar_year: bool = False) -> int:
    d = pd.Timestamp(date)
    return d.year if (calendar_year or d.month >= 7) else d.year - 1


def season_label(season: int, calendar_year: bool = False) -> str:
    return str(season) if calendar_year else f"{season}-{str(season + 1)[2:]}"


def table(results: pd.DataFrame, tiebreak: str = "gd", deductions: dict | None = None) -> list[dict]:
    """Rows sorted into league order: pos, team, p, w, d, l, gf, ga, gd, pts."""
    st: dict[str, dict] = {}

    def row(team):
        return st.setdefault(team, {"team": team, "p": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0})
    for r in results.itertuples(index=False):
        h, a = row(r.home), row(r.away)
        gh, ga = int(r.fthg), int(r.ftag)
        for t, f, g in ((h, gh, ga), (a, ga, gh)):
            t["p"] += 1
            t["gf"] += f
            t["ga"] += g
            t["w"] += f > g
            t["d"] += f == g
            t["l"] += f < g
    for t in st.values():
        t["gd"] = t["gf"] - t["ga"]
        t["deducted"] = int((deductions or {}).get(t["team"], 0))
        t["pts"] = 3 * t["w"] + t["d"] - t["deducted"]

    def h2h(teams):                            # mini-table of the games between level teams
        mini = {t: [0, 0, 0] for t in teams}
        sub = results[results["home"].isin(teams) & results["away"].isin(teams)]
        for r in sub.itertuples(index=False):
            gh, ga = int(r.fthg), int(r.ftag)
            for t, f, g in ((r.home, gh, ga), (r.away, ga, gh)):
                m = mini[t]
                m[0] += 3 * (f > g) + (f == g)
                m[1] += f - g
                m[2] += f
        return mini

    rows = sorted(st.values(), key=lambda t: (-t["pts"], -t["gd"], -t["gf"], t["team"]))
    if tiebreak == "h2h":
        out, i = [], 0
        while i < len(rows):
            j = i
            while j < len(rows) and rows[j]["pts"] == rows[i]["pts"]:
                j += 1
            group = rows[i:j]
            if len(group) > 1:
                mini = h2h([t["team"] for t in group])
                group.sort(key=lambda t: (-mini[t["team"]][0], -mini[t["team"]][1],
                                          -mini[t["team"]][2], -t["gd"], -t["gf"], t["team"]))
            out += group
            i = j
        rows = out
    for pos, t in enumerate(rows, 1):
        t["pos"] = pos
    return rows


def _results(db_matches: pd.DataFrame, extra: list[dict] | None) -> pd.DataFrame:
    """Played matches + finished schedule games not in the file yet."""
    m = db_matches[["date", "league", "home", "away", "fthg", "ftag"]].dropna(subset=["fthg", "ftag"])
    m = m.assign(date=pd.to_datetime(m["date"]).dt.normalize())
    rows = []
    have = {(r.league, r.home, r.away): r.date for r in m.itertuples(index=False)}
    for x in extra or []:
        if x.get("fthg") is None or x.get("ftag") is None:
            continue
        d = pd.Timestamp(str(x.get("date") or x.get("utc", ""))[:10])
        seen = have.get((x["competition"], x["home"], x["away"]))
        if seen is not None and abs((seen - d).days) <= 1:
            continue
        rows.append({"date": d, "league": x["competition"], "home": x["home"], "away": x["away"],
                     "fthg": int(x["fthg"]), "ftag": int(x["ftag"])})
    return pd.concat([m, pd.DataFrame(rows)], ignore_index=True) if rows else m


def standings(cfg, db, competition: str, home: str, away: str, date=None,
              extra: list[dict] | None = None) -> dict:
    """The table(s) behind one schedule match, with both teams located."""
    from footypred.data.localfile import cup_codes, specs_from_config
    scfg = cfg.raw.get("standings") or {}
    cal = {s.key for s in specs_from_config(cfg) if s.calendar_year}
    cups = cup_codes(cfg)
    date = pd.Timestamp(date or pd.Timestamp.today()).normalize()
    results = _results(db.load_matches(), extra)
    names = {k: (v or {}).get("name", k) for k, v in (cfg.leagues or {}).items()}

    def build(code, phase=False):
        season = season_of(date, code in cal)
        sub = results[(results["league"] == code)]
        sub = sub[sub["date"].map(lambda d: season_of(d, code in cal)) == season]
        if phase:
            end = pd.Timestamp(year=season + 1, month=LEAGUE_PHASE_ENDS[0], day=LEAGUE_PHASE_ENDS[1])
            sub = sub[sub["date"] < end]
        tb = (scfg.get("tiebreak") or {}).get(code) or ("h2h" if code in H2H_LEAGUES else "gd")
        ded = ((scfg.get("deductions") or {}).get(code) or {}).get(season) \
            or ((scfg.get("deductions") or {}).get(code) or {}).get(str(season)) or {}
        rows = table(sub, tb, ded)
        find = lambda t: next(({"team": r["team"], "pos": r["pos"], "pts": r["pts"], "p": r["p"]}  # noqa: E731
                               for r in rows if r["team"] == t), None)
        return {"code": code, "name": names.get(code, code) + (" · league phase" if phase else ""),
                "season": season_label(season, code in cal), "tiebreak": tb,
                "as_of": None if sub.empty else str(sub["date"].max().date()),
                "matches": int(len(sub)), "rows": rows, "home": find(home), "away": find(away),
                "deductions": {k: int(v) for k, v in ded.items()}}

    if competition not in cups:
        return {"competition": competition, "tables": [build(competition)], "note": None}
    phases = scfg.get("league_phase")
    first = (LEAGUE_PHASE if phases is None else phases).get(competition)   # {} turns them off
    if first is not None and season_of(date) >= int(first):
        return {"competition": competition, "tables": [build(competition, phase=True)], "note": None}
    # a cup without a league table: each team's domestic league
    tl = db.team_league(cups)
    codes = [c for c in dict.fromkeys([tl.get(home), tl.get(away)]) if c and c not in cups]
    return {"competition": competition, "tables": [build(c) for c in codes],
            "note": "Cup match: the teams' league tables" if codes else "No league table for this match"}
