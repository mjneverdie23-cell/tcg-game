"""Command line interface: `footy <command>`."""

from __future__ import annotations

import argparse
import json
import sys

from footypred.config import load_config
from footypred.logging_utils import get_logger, setup_logging

log = get_logger("cli")


def _db(cfg):
    from footypred.data.db import Database
    return Database(cfg.paths.db_file)


def cmd_bootstrap(cfg, args):
    from footypred.data.pipeline import bootstrap
    db = _db(cfg)
    n = bootstrap(cfg, db, cutoff=args.cutoff, seed=args.seed)
    print(f"Loaded {n} synthetic matches into {cfg.paths.db_file}")


def cmd_update(cfg, args):
    from footypred.data.pipeline import update
    rep = update(cfg, _db(cfg))
    for k, v in rep.items():
        print(f"  {k:<15} {v}")


def cmd_train(cfg, args):
    from footypred.features.engineering import FeatureBuilder, feature_columns
    from footypred.features.tuning import tune_ratings
    from footypred.models.registry import ModelRegistry
    from footypred.models.summary import render_training_report
    from footypred.models.trainer import Trainer
    db = _db(cfg)
    matches = db.load_matches()
    if matches.empty:
        sys.exit("no matches in the database - run `footy bootstrap` or `footy update` first")
    params = {}
    if cfg.features.get("auto_tune_ratings", True):
        params = tune_ratings(matches)
    fb = FeatureBuilder(cfg, db, params)
    frame = fb.build_training_frame(matches)
    res = Trainer(cfg).train(frame, feature_columns(frame))
    res.feature_params = fb.params
    version = ModelRegistry(cfg.paths.models_dir).save(res, fb.state)
    print(render_training_report(res.report))
    print(f"\nSaved model {version}")


def _pick_opts(args) -> dict:
    o = {}
    if getattr(args, "markets", None):
        o["markets"] = [m.strip() for m in args.markets.split(",") if m.strip()]
    if getattr(args, "min_odds", None) is not None:
        o["min_odds"] = args.min_odds
    if getattr(args, "form_weight", None) is not None:
        o["form_weight"] = args.form_weight
    if getattr(args, "min_lift", None) is not None:
        o["min_lift"] = args.min_lift
    if getattr(args, "max_odds", None) is not None:
        o["max_odds"] = args.max_odds
    if getattr(args, "style", None):
        o["style"] = args.style
    return o


def _add_pick_args(p):
    p.add_argument("--style", choices=["safe", "balanced", "bold"],
                   help="pick style = fair-odds range: safe 1.15-1.60, balanced 1.25-2.20 "
                        "(default), bold 1.60-3.50")
    p.add_argument("--markets", help="markets the best pick may come from, comma separated: "
                   "1x2,totals,btts,team_totals (default: all)")
    p.add_argument("--max-odds", type=float, help="skip selections with fair odds above this")
    p.add_argument("--min-odds", type=float, help="skip selections with fair odds below this "
                   "(default: set by --style)")
    p.add_argument("--form-weight", type=float, help="0..1, how much last-5 form decides the "
                   "best pick vs the model (default 0.6)")
    p.add_argument("--min-lift", type=float, help="how far above a typical game a pick must be "
                   "(default 0.05; 0 allows ordinary safe picks)")


def cmd_backtest_picks(cfg, args):
    from footypred.data.db import Database
    from footypred.models.registry import ModelRegistry
    from footypred.predict.picks import FormIndex, backtest, eval_matches, form_reliability
    db = Database(cfg.paths.db_file)
    res = ModelRegistry(cfg.paths.models_dir).load().result
    allm = db.load_matches()
    idx = FormIndex(allm)
    em = eval_matches(allm, res.eval_preds, res.report["eval_seasons"])
    probs = res.eval_preds["final"]
    from footypred.predict.picks import base_rates
    typical = base_rates(allm[allm["season"] < min(res.report["eval_seasons"])])
    base = {**(cfg.raw.get("picks") or {}), **_pick_opts(args)}
    print(f"Best-pick backtest on {len(em)} out-of-sample matches "
          f"(seasons {', '.join(map(str, res.report['eval_seasons']))}); form from games "
          "before each match, model = out-of-fold probabilities.\n")
    print(f"{'strategy':<26}{'picks':>7}{'landed':>9}{'model said':>12}{'form said':>11}"
          "   most common picks")
    for name, o in (("model only", {"form_weight": 0.0, "min_form": 0.0}),
                    ("form only", {"form_weight": 1.0, "min_model": 0.0}),
                    (f"your settings (fw={base.get('form_weight', 0.6)})", {})):
        r = backtest(idx, em, probs, {**base, **o}, base=typical)
        if not r["picks"]:
            print(f"{name:<26}{0:>7}")
            continue
        common = ", ".join(f"{k} {v}" for k, v in list(r["by_pick"].items())[:3])
        print(f"{name:<26}{r['picks']:>7}{100 * r['hit_rate']:8.1f}%{100 * r['mean_model']:11.1f}%"
              f"{100 * r['mean_form']:10.1f}%   {common}")
    print("\nHow often selections landed by their raw last-5 form rate:")
    for row in form_reliability(idx, em, limit=args.limit):
        print(f"  form {100 * row['form_from']:3.0f}-{100 * row['form_to']:3.0f}%  "
              f"(avg {100 * row['mean_form']:4.1f}%)  landed {100 * row['hit_rate']:4.1f}%  "
              f"n={row['n']}")


def cmd_image(cfg, args):
    from pathlib import Path
    from footypred.predict.batch import predict_many, render_batch, summary_row
    from footypred.predict.predictor import Predictor
    from footypred.predict.report import render
    from footypred.vision.reader import read_image
    predictor = Predictor(cfg)
    db = predictor.db
    img_cfg = cfg.raw.get("image") or {}
    all_rows, payload = [], []
    for path in args.images:
        res = read_image(Path(path).read_bytes(), db.teams(), db.load_aliases(),
                         engine=args.engine or img_cfg.get("engine", "auto"),
                         claude_model=img_cfg.get("claude_model"))
        print(f"\n{path}: {len(res['fixtures'])} fixture(s) found via {res['engine']}")
        for w in res["warnings"]:
            print(f"  ⚠ {w}")
        for u in res.get("unmatched", []):
            print(f"  ✗ not in database: {u}")
        for f in res["fixtures"]:
            when = " ".join(x for x in (f["date"], f["time"]) if x)
            print(f"  • {f['home']} vs {f['away']}  {when}  (read: \"{f['source']}\", "
                  f"confidence {100 * f['confidence']:.0f}%)")
        rows = predict_many(predictor, res["fixtures"], args.date, args.neutral, _pick_opts(args))
        all_rows += rows
        payload.append({"image": str(path), **res,
                        "predictions": [summary_row(r["prediction"]) if "prediction" in r
                                        else {"error": r["error"], **r["fixture"]} for r in rows]})
    if args.json:
        print(json.dumps(payload, indent=2, default=float))
        return
    if all_rows:
        print("\n" + render_batch(all_rows))
    if args.full:
        for r in all_rows:
            if "prediction" in r:
                print("\n" + render(r["prediction"]))
    if args.chart_dir:
        from footypred.predict.charts import plot_prediction
        for r in all_rows:
            if "prediction" in r:
                p = r["prediction"]
                safe = lambda s: "".join(c if c.isalnum() else "_" for c in s)
                out = Path(args.chart_dir) / f"{safe(p.home)}_vs_{safe(p.away)}_{p.date}.png"
                print(f"chart: {plot_prediction(p, out)}")


def cmd_predict(cfg, args):
    from footypred.predict.predictor import Predictor
    from footypred.predict.report import render
    pred = Predictor(cfg).predict(args.home, args.away, date=args.date, neutral=args.neutral,
                                  pick_opts=_pick_opts(args))
    if args.json:
        print(json.dumps(pred.to_dict(), indent=2, default=float))
    else:
        print(render(pred))
    if args.chart:
        from footypred.predict.charts import plot_prediction
        path = args.chart
        if path == "auto":
            safe = lambda s: "".join(c if c.isalnum() else "_" for c in s)
            path = cfg.paths.data_dir / "charts" / f"{safe(pred.home)}_vs_{safe(pred.away)}_{pred.date}.png"
        print(f"\nChart saved: {plot_prediction(pred, path)}")


def cmd_evaluate(cfg, args):
    from footypred.models.registry import ModelRegistry
    from footypred.models.summary import render_training_report
    b = ModelRegistry(cfg.paths.models_dir).load(args.version)
    if args.json:
        from footypred.models.registry import _jsonable
        print(json.dumps(_jsonable(b.result.report), indent=2))
    else:
        print(f"Model {b.version} (created {b.created})\n")
        print(render_training_report(b.result.report))
    if args.chart:
        from footypred.predict.charts import plot_evaluation
        path = args.chart if args.chart != "auto" else cfg.paths.data_dir / "charts" / f"evaluation_{b.version}.png"
        print(f"\nChart saved: {plot_evaluation(b.result, path)}")


def cmd_teams(cfg, args):
    db = _db(cfg)
    by_league: dict[str, list[str]] = {}
    for team, lg in sorted(db.team_league().items()):
        by_league.setdefault(lg, []).append(team)
    for lg, teams in sorted(by_league.items()):
        if args.league and lg != args.league:
            continue
        print(f"{lg} ({len(teams)}): {', '.join(teams)}")


def cmd_app(cfg, args):
    from footypred.ui.web import serve
    serve(cfg, host=args.host, port=args.port, open_browser=not args.no_browser)


def cmd_pick(cfg, args):
    from footypred.ui.menu import Menu
    from footypred.ui.service import PredictionService
    print("Loading model and match history ...")
    Menu(PredictionService(cfg)).run()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="footy", description="Football prediction for 1X2, "
                                "O/U 2.5, team goals O/U 0.5-2.5 and BTTS")
    p.add_argument("--config", help="path to a YAML config (default: config/default.yaml)")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("bootstrap", help="load the offline synthetic dataset")
    b.add_argument("--cutoff", help="last match date (default: today)")
    b.add_argument("--seed", type=int, default=7)
    sub.add_parser("update", help="scrape/refresh all enabled data sources")
    sub.add_parser("train", help="tune, cross-validate, select and save models")

    pr = sub.add_parser("predict", help="predict a fixture")
    pr.add_argument("home"); pr.add_argument("away")
    pr.add_argument("--date", help="match date YYYY-MM-DD (default: today)")
    pr.add_argument("--neutral", action="store_true", help="neutral venue")
    pr.add_argument("--json", action="store_true", help="JSON output")
    pr.add_argument("--chart", nargs="?", const="auto", metavar="PATH",
                    help="save a dashboard PNG (optional path)")
    _add_pick_args(pr)

    im = sub.add_parser("image", help="read fixtures from screenshot(s) and predict them all")
    im.add_argument("images", nargs="+", help="image file(s): PNG, JPEG, WebP ...")
    im.add_argument("--engine", choices=["auto", "ocr", "claude"],
                    help="auto (default): offline OCR, Claude vision only if OCR finds nothing "
                         "and the anthropic package is installed")
    im.add_argument("--date", help="date for fixtures whose date isn't shown (default: today)")
    im.add_argument("--neutral", action="store_true")
    im.add_argument("--full", action="store_true", help="print the full report for each fixture")
    im.add_argument("--chart-dir", help="save a dashboard PNG per fixture into this folder")
    im.add_argument("--json", action="store_true")
    _add_pick_args(im)

    bt = sub.add_parser("backtest-picks", help="how often best picks landed out of sample")
    _add_pick_args(bt)
    bt.add_argument("--limit", type=int, default=1500,
                    help="matches used for the form-reliability table (default 1500)")

    ev = sub.add_parser("evaluate", help="show the out-of-sample evaluation of a model")
    ev.add_argument("--version")
    ev.add_argument("--json", action="store_true")
    ev.add_argument("--chart", nargs="?", const="auto", metavar="PATH",
                    help="save reliability diagrams for the four markets")

    t = sub.add_parser("teams", help="list known teams by league")
    t.add_argument("--league")

    a = sub.add_parser("app", help="open the web app: pick league and teams from dropdowns")
    a.add_argument("--port", type=int, default=8765)
    a.add_argument("--host", default="127.0.0.1")
    a.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    sub.add_parser("pick", help="terminal menu: pick league and teams from numbered lists")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)
    cfg.paths.ensure()
    setup_logging(cfg.paths.log_dir, "DEBUG" if args.verbose else "INFO")
    {"bootstrap": cmd_bootstrap, "update": cmd_update, "train": cmd_train,
     "predict": cmd_predict, "evaluate": cmd_evaluate, "teams": cmd_teams,
     "app": cmd_app, "pick": cmd_pick, "backtest-picks": cmd_backtest_picks, "image": cmd_image}[args.cmd](cfg, args)


if __name__ == "__main__":
    main()
