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


def cmd_predict(cfg, args):
    from footypred.predict.predictor import Predictor
    from footypred.predict.report import render
    pred = Predictor(cfg).predict(args.home, args.away, date=args.date, neutral=args.neutral)
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
     "app": cmd_app, "pick": cmd_pick}[args.cmd](cfg, args)


if __name__ == "__main__":
    main()
