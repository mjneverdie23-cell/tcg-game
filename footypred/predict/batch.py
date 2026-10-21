"""Predict a list of fixtures (e.g. read from an image) and summarise them."""

from __future__ import annotations

from footypred.logging_utils import get_logger

log = get_logger("predict.batch")


def predict_many(predictor, fixtures: list[dict], default_date=None, neutral: bool = False,
                 pick_opts: dict | None = None) -> list[dict]:
    """fixtures: [{home, away, date?}] -> [{fixture, prediction | error}]"""
    out = []
    for fx in fixtures:
        try:
            pred = predictor.predict(fx["home"], fx["away"], date=fx.get("date") or default_date,
                                     neutral=neutral, pick_opts=pick_opts)
            out.append({"fixture": fx, "prediction": pred})
        except Exception as exc:                     # one bad row never stops the batch
            log.warning("prediction failed for %s vs %s: %s", fx.get("home"), fx.get("away"), exc)
            out.append({"fixture": fx, "error": str(exc)})
    return out


def summary_row(pred) -> dict:
    m, f = pred.markets, pred.form or {}
    b = f.get("best_pick")
    return {
        "home": pred.home, "away": pred.away, "date": pred.date,
        "best_pick": b["label"] if b else None,
        "best_model": b["model_prob"] if b else None,
        "best_form": b["form_rate"] if b else None,
        "best_odds": b["fair_odds"] if b else None,
        "follow_ups": [{"label": c["label"], "model": c["model_prob"], "odds": c["fair_odds"],
                        "form": c["form_rate"]} for c in (f.get("follow_ups") or [])],
        "by_style": {k: (v["label"] if v else None) for k, v in (f.get("by_style") or {}).items()},
        "home_win": m["1x2"]["home"], "draw": m["1x2"]["draw"], "away_win": m["1x2"]["away"],
        "over_2.5": m["over_under_2.5"]["over"], "btts": m["btts"]["yes"],
        "home_over_0.5": m["team_totals"]["home"]["over_0.5"],
        "away_over_0.5": m["team_totals"]["away"]["over_0.5"],
        "confidence": pred.confidence["overall"],
    }


def render_batch(results: list[dict]) -> str:
    pct = lambda x: f"{100 * x:.0f}%"
    head = (f"{'#':>2}  {'Fixture':<38}{'Date':<12}{'Best pick (last-5 form + model)':<34}"
            f"{'model':>6}{'odds':>6}{'form':>6}   {'1X2 H-D-A':<13}{'O2.5':>5}{'BTTS':>6}")
    L = [head, "─" * len(head)]
    for i, r in enumerate(results, 1):
        fx = r["fixture"]
        if "error" in r:
            L.append(f"{i:>2}  {fx['home'] + ' vs ' + fx['away']:<38}  ✗ {r['error']}")
            continue
        s = summary_row(r["prediction"])
        name = f"{s['home']} vs {s['away']}"
        best = s["best_pick"] or "no clear pick"
        nxt = [c["label"] for c in s["follow_ups"][:2]]
        L.append(f"{i:>2}  {name[:37]:<38}{s['date']:<12}{best[:33]:<34}"
                 f"{(pct(s['best_model']) if s['best_model'] is not None else '-'):>6}"
                 f"{(format(s['best_odds'], '.2f') if s['best_odds'] is not None else '-'):>6}"
                 f"{(pct(s['best_form']) if s['best_form'] is not None else '-'):>6}   "
                 f"{pct(s['home_win']) + '-' + pct(s['draw']) + '-' + pct(s['away_win']):<13}"
                 f"{pct(s['over_2.5']):>5}{pct(s['btts']):>6}")
        if nxt:
            L.append(f"{'':>4}{'':<38}{'':<12}then: {' · '.join(nxt)}")
    return "\n".join(L)


def pick_summary(pred) -> dict:
    """Compact prediction for lists (schedule, image batch): best pick,
    follow-up picks, best pick per style and the headline markets."""
    m, f = pred.markets, pred.form or {}
    slim = lambda c: None if not c else {k: c.get(k) for k in (
        "label", "market", "model_prob", "form_rate", "fair_odds", "agreement", "lean", "why")}
    return {"home": pred.home, "away": pred.away, "date": pred.date, "league": pred.league,
            "best": slim(f.get("best_pick")),
            "follow_ups": [slim(c) for c in f.get("follow_ups") or []],
            "by_style": {k: slim(v) for k, v in (f.get("by_style") or {}).items()},
            "style": (f.get("settings") or {}).get("style"),
            "1x2": m["1x2"], "over_2.5": m["over_under_2.5"]["over"], "btts": m["btts"]["yes"],
            "xg": pred.expected_goals, "confidence": pred.confidence["overall"],
            "warnings": pred.warnings[:2]}
