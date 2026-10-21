"""Plain-text rendering of a Prediction, organised by the four markets."""

from __future__ import annotations

from footypred.predict.predictor import Prediction

W = 66


def _bar(p: float, width: int = 20) -> str:
    n = int(round(p * width))
    return "█" * n + "░" * (width - n)


def _pct(p: float) -> str:
    return f"{100 * p:5.1f}%"


def _frac(c: dict, key: str) -> str:
    return f"{c[key]}/{c['n']}" if c.get("n") else "-"


def _team_lines(name: str, ev: dict) -> list[str]:
    last, ven = ev["last"], ev["venue"]
    if not last.get("n"):
        return [f"  {name}: no match history on record"]
    xg = ""
    if last.get("xgf") is not None:
        xg = f" · xG {last['xgf']:.2f} / {last['xga']:.2f}"
    out = [
        f"  {name} — last {last['n']}: W{last['w']} D{last['d']} L{last['l']} · "
        f"{last['gf']:.2f} scored / {last['ga']:.2f} conceded per game{xg}",
        f"      scored in {_frac(last, 'scored')} · 2+ in {_frac(last, 'scored2')} · "
        f"3+ in {_frac(last, 'scored3')} · conceded in {_frac(last, 'conceded')} · "
        f"BTTS {_frac(last, 'btts')} · O2.5 {_frac(last, 'o25')}",
    ]
    if ven.get("n"):
        out.append(
            f"      {ev['venue_label']} games (last {ven['n']}): scored {_frac(ven, 'scored')} · "
            f"2+ {_frac(ven, 'scored2')} · conceded {_frac(ven, 'conceded')} · "
            f"BTTS {_frac(ven, 'btts')} · O2.5 {_frac(ven, 'o25')}")
    return out


def _best_pick_lines(pred: Prediction) -> list[str]:
    f = pred.form
    if not f:
        return []
    st = f.get("settings", {})
    rng = (f"{st.get('style', '')} style, fair odds {st.get('min_odds', 0):.2f}–"
           f"{st.get('max_odds', 0):.2f}" if st.get("max_odds") else "")
    L = ["", f" ★ BEST PICK (last-{f['window']} form + model{'; ' + rng if rng else ''})"]
    g = f.get("gap")
    if g and g["lopsided"]:
        L.append(f"    Big strength gap: {g['favourite']} win {100 * g['win_prob']:.0f}% "
                 f"(Elo gap {abs(g['elo_gap']):.0f}) — the favourite's safe lines are too short, "
                 "so bigger lines are considered")
    ts = f.get("too_short")
    if ts:
        L.append(f"    ↑ {ts['label']} is {100 * ts['model_prob']:.0f}% but only {ts['fair_odds']:.2f}"
                 " — too short, looked further up the ladder")
    b = f.get("best_pick")
    if b:
        L.append(f"    {b['label']}  —  {100 * b['model_prob']:.0f}% (fair odds {b['fair_odds']:.2f})"
                 f"  ·  form {100 * b['form_rate']:.0f}%  ·  {b['agreement']}")
        for e in sorted(b["evidence"], key=lambda e: -e["weight"])[:4]:
            L.append(f"      ✓ {e['event']}: {e['hits']}/{e['n']} ({e['window']})")
    else:
        L.append("    No clear pick — nothing in the odds range is backed by both recent form "
                 "and the model.")
    for side, team, venue in (("home", pred.home, "at home"), ("away", pred.away, "away")):
        tags = f["profiles"][side].get(venue) or f["profiles"][side].get("overall")
        if tags:
            L.append(f"    {team} {venue}: {', '.join(tags)}")
        sim = f["profiles"][side].get("vs similar")
        if sim:
            other = pred.away if side == "home" else pred.home
            L.append(f"    {team} vs teams rated like {other}: {', '.join(sim)}")
    L.append("    Best in each market:")
    for mk, r in f["best_by_market"].items():
        flag = "" if r["eligible"] else "  (no clear pick)"
        form = "-" if r["form_rate"] is None else f"{100 * r['form_rate']:.0f}%"
        L.append(f"      {r['market_name']:<20}{r['label'][:37]:<38}model {100 * r['model_prob']:3.0f}%"
                 f"  odds {r['fair_odds']:5.2f}  form {form:>4}{flag}")
    for c in f.get("conflicts", []):
        L.append(f"    ⚠ form disagrees: {c['label']} — model {100 * c['model_prob']:.0f}% but form "
                 f"only {100 * c['form_rate']:.0f}%")
    return L


def _form_table(pred: Prediction) -> list[str]:
    f = pred.form
    if not f:
        return []
    c = f["counts"]
    cols = [("home_last", f"{pred.home[:12]} L{f['window']}"), ("home_home", "home"),
            ("home_away", "away"), ("home_similar", "vs similar"),
            ("away_last", f"{pred.away[:12]} L{f['window']}"),
            ("away_home", "home"), ("away_away", "away"), ("away_similar", "vs similar"),
            ("h2h", "H2H")]
    L = ["", f" FORM CHECK — LAST {f['window']} (hits/games; H2H from {pred.home}'s side)"]
    L.append("    " + f"{'':<16}" + "".join(f"{lbl:>12}" for _, lbl in cols))
    rows = [("Results W-D-L", None), ("Scored 1+", "scored"), ("Scored 2+", "scored2"),
            ("Conceded 1+", "conceded"), ("Conceded 2+", "conceded2"),
            ("Clean sheet", "clean_sheets"), ("Failed to score", "failed_to_score"),
            ("BTTS", "btts"), ("Over 1.5", "o15"), ("Over 2.5", "o25"), ("Over 3.5", "o35")]
    for lbl, key in rows:
        cells = []
        for k, _ in cols:
            x = c[k]
            if not x["n"]:
                cells.append("-")
            elif key is None:
                cells.append(f"{x['w']}-{x['d']}-{x['l']}")
            else:
                cells.append(f"{x[key]}/{x['n']}")
        L.append("    " + f"{lbl:<16}" + "".join(f"{v:>12}" for v in cells))
    return L


def render(pred: Prediction) -> str:
    m, pk, cf = pred.markets, pred.picks, pred.confidence
    eg = pred.expected_goals
    L = ["═" * W,
         f" {pred.home} vs {pred.away}  ·  {pred.date}  ·  {pred.league_name}"
         f"{'  ·  neutral venue' if pred.neutral else ''}",
         f" model: {pred.model} ({pred.version})  ·  xG {eg['home']:.2f} – {eg['away']:.2f}"
         f"  (total {eg['total']:.2f})  ·  confidence {cf['overall']}/100",
         "═" * W]

    def head(title, key):
        L.append("")
        L.append(f" {title:<48}confidence {cf[key]:>3}/100")

    L += _best_pick_lines(pred)
    head("1) MATCH RESULT (1X2)", "1x2")
    for lbl, p in ((f"{pred.home} win", m["1x2"]["home"]), ("Draw", m["1x2"]["draw"]),
                   (f"{pred.away} win", m["1x2"]["away"])):
        L.append(f"    {lbl:<22}{_pct(p)}  {_bar(p)}  fair {1 / p:5.2f}")
    p1 = pk["1x2"]
    L.append(f"    → {p1['pick']} ({p1['strength']}, {100 * p1['prob']:.1f}%)")

    head("2) TOTAL GOALS OVER/UNDER 1.5 · 2.5 · 3.5", "over_under_2.5")
    for lbl, p in (("Over 2.5", m["over_under_2.5"]["over"]),
                   ("Under 2.5", m["over_under_2.5"]["under"])):
        L.append(f"    {lbl:<22}{_pct(p)}  {_bar(p)}  fair {1 / p:5.2f}")
    tot = m.get("totals", {})
    if tot:
        L.append("    " + "  ·  ".join(f"Over {l} {_pct(tot[f'over_{l}']).strip()} / Under "
                                      f"{_pct(1 - tot[f'over_{l}']).strip()}"
                                      for l in ("1.5", "3.5") if f"over_{l}" in tot))
    p2 = pk["over_under_2.5"]
    L.append(f"    → {p2['pick']} ({p2['strength']}, {100 * p2['prob']:.1f}%)")

    head("3) TEAM GOALS OVER/UNDER 0.5 · 1.5 · 2.5", "team_totals")
    L.append(f"    {'':<22}{'Over 0.5':>9}{'Over 1.5':>10}{'Over 2.5':>10}")
    for side, team in (("home", pred.home), ("away", pred.away)):
        t = m["team_totals"][side]
        L.append(f"    {team:<22}{_pct(t['over_0.5']):>9}{_pct(t['over_1.5']):>10}"
                 f"{_pct(t['over_2.5']):>10}")
    for team, lines in pk["team_totals"].items():
        txt = " · ".join(f"{l['pick']} {100 * l['prob']:.0f}% ({l['strength']})" for l in lines)
        L.append(f"    → {team}: {txt}")

    head("4) BOTH TEAMS TO SCORE", "btts")
    for lbl, p in (("Yes", m["btts"]["yes"]), ("No", m["btts"]["no"])):
        L.append(f"    {lbl:<22}{_pct(p)}  {_bar(p)}  fair {1 / p:5.2f}")
    p4 = pk["btts"]
    L.append(f"    → {p4['pick']} ({p4['strength']}, {100 * p4['prob']:.1f}%)")

    L += _form_table(pred)
    L += ["", " PAST-MATCH EVIDENCE"]
    L += _team_lines(pred.home, pred.evidence["home"])
    L += _team_lines(pred.away, pred.evidence["away"])
    h2h = pred.evidence.get("h2h")
    if h2h:
        L.append(f"  Head-to-head (last {h2h['n']}): {pred.home} {h2h['home_w']} · draws "
                 f"{h2h['d']} · {pred.away} {h2h['away_w']} · BTTS {h2h['btts']}/{h2h['n']} · "
                 f"O2.5 {h2h['o25']}/{h2h['n']} · {h2h['goals']:.1f} goals/game")
        L.append(f"      recent: {' | '.join(h2h['scores'])}")
    else:
        L.append("  Head-to-head: no previous meetings on record")

    if pred.drivers:
        L += ["", " WHAT MOVED EACH MARKET (direct-model contributions, log-odds)"]
        for d in pred.drivers.values():
            items = " · ".join(f"{'+' if v >= 0 else '−'}{abs(v):.2f} {name}"
                               for name, v, _ in d["items"][:3])
            L.append(f"  {d['label']:<14}{items}")

    L += ["", " Most likely scores: " + " · ".join(f"{s} {100 * p:.1f}%"
                                                 for s, p in pred.top_scores[:5])]
    agree = " · ".join(f"{n} {100 * mm['1x2']['home']:.0f}/{100 * mm['over_under_2.5']['over']:.0f}"
                       f"/{100 * mm['btts']['yes']:.0f}" for n, mm in pred.model_markets.items())
    L.append(f" Models (home win/O2.5/BTTS %): {agree}")
    for w in pred.warnings:
        L.append(f" ⚠ {w}")
    L.append("═" * W)
    return "\n".join(L)
