"""Command line interface: `footy <command>`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from footypred.config import load_config
from footypred.logging_utils import get_logger, setup_logging

log = get_logger("cli")


def _db(cfg, sync: bool = True):
    """The system database; your local match file is (re)imported first
    whenever it changed."""
    from footypred.data.db import Database
    from footypred.data.localfile import sync_db
    db = Database(cfg.paths.db_file)
    if sync:
        n = sync_db(cfg, db)
        if n:
            print(f"Imported {n} matches from your match file")
    return db


def _fetcher(cfg, args, progress=print):
    from footypred.data.localfile import make_fetcher
    return make_fetcher(cfg, progress, fallback=False if getattr(args, "no_fallback", False)
                        else None)


def _specs(cfg, only: str | None):
    from footypred.data.localfile import specs_from_config
    specs = specs_from_config(cfg)
    if only:
        want = {x.strip().upper() for x in only.split(",")}
        specs = [s for s in specs if s.key.upper() in want]
        if not specs:
            sys.exit(f"no configured competitions match {only}")
    return specs


def cmd_data(cfg, args):
    import pandas as pd
    from footypred.data import localfile as lf
    path = Path(args.file) if getattr(args, "file", None) else lf.csv_path(cfg)
    first = int(getattr(args, "first_season", None) or lf.first_season(cfg))
    to = pd.Timestamp(args.to).normalize() if getattr(args, "to", None) else pd.Timestamp.today().normalize()
    if args.data_cmd == "download":
        if path.exists() and not args.force:
            sys.exit(f"{path} already exists. Use `footy data update` to add new matches, "
                     "or --force to rebuild it from scratch.")
        specs = _specs(cfg, args.only)
        print(f"Downloading {len(specs)} competitions, seasons {first}/{str(first + 1)[2:]} "
              f"to {to.date()} → {path}")
        df = lf.download(_fetcher(cfg, args), specs, first, to)
        lf.write_csv(df, path)
        print(f"\nSaved {len(df)} matches to {path}")
        if len(df):
            print(lf.summarize(df))
        db = _db(cfg)
    elif args.data_cmd == "update":
        if not path.exists():
            sys.exit(f"{path} not found — run `footy data download` first")
        specs = _specs(cfg, args.only)
        print(f"Updating {path} up to {to.date()}")
        r = lf.update(_fetcher(cfg, args), specs, path, first, to)
        print(f"\nAdded {r['added']} new matches" +
              (f", corrected {r['corrected']} (backup: {path.name}.bak)" if r["corrected"] else "")
              + f" · file now has {r['rows']} matches")
        for k, v in r["by_competition"].items():
            if v:
                print(f"  {k:<5} +{v}")
        _db(cfg)
    elif args.data_cmd == "import":
        from footypred.data.db import Database
        db = Database(cfg.paths.db_file)
        if args.file:
            n = lf.to_db(lf.read_csv(path), db, aliases=lf.load_aliases(cfg))
        else:
            n = lf.sync_db(cfg, db, force=True)
        if not n:
            sys.exit(f"nothing imported (is {path} there?)")
        print(f"Imported {n} matches from {path} into {cfg.paths.db_file}. "
              "Run `footy train` to retrain on it.")
    elif args.data_cmd == "info":
        df = lf.read_csv(path)
        print(f"{path}: {len(df)} matches" + (f", {df['date'].min()} → {df['date'].max()}"
                                              if len(df) else ""))
        if len(df):
            print(lf.summarize(df))
    elif args.data_cmd == "check":
        df = lf.read_csv(path)
        pairs = lf.name_check(df)
        if not pairs:
            print("No suspicious team-name pairs found.")
        for comp, a, b, r in pairs:
            print(f"  {comp:<5} '{a}'  ~  '{b}'  ({r:.0f}%)")
        if pairs:
            print(f"\nIf two names are the same club, add a line '{pairs[0][1]},{pairs[0][2]}' "
                  f"to {lf.aliases_path(cfg)} (columns from,to).")


def cmd_bootstrap(cfg, args):
    from footypred.data.pipeline import bootstrap
    db = _db(cfg, sync=False)
    from footypred.data.localfile import csv_path
    if csv_path(cfg).exists():
        print(f"⚠ your match file {csv_path(cfg)} stays untouched; the demo data is used until "
              "you run `footy data import` (or edit the file)")
    n = bootstrap(cfg, db, cutoff=args.cutoff, seed=args.seed)
    db.set_meta("csv_signature", "")
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
    res.report["data_source"] = db.get_meta("data_source")
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
    import pandas as pd
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
    rep = res.report
    before = (allm["date"] < pd.Timestamp(rep["eval_from"]) if rep.get("eval_from")
              else allm["season"] < min(rep["eval_seasons"]))
    typical = base_rates(allm[before])
    base = {**(cfg.raw.get("picks") or {}), **_pick_opts(args)}
    periods = rep.get("eval_periods") or rep["eval_seasons"]
    print(f"Best-pick backtest on {len(em)} out-of-sample matches "
          f"({', '.join(map(str, periods))}); form from games "
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


def cmd_backtest(cfg, args):
    from footypred.predict.charts import plot_walkforward
    from footypred.predict.walkforward import QUICK_MODELS, render, walk_forward
    db = _db(cfg)
    comps = [c.strip() for c in args.competitions.split(",")] if args.competitions else None
    models = QUICK_MODELS if args.quick else None
    last = [0.0]

    def progress(frac, msg):
        if frac == 0 or frac >= 1 or frac - last[0] >= 0.1 or "retrain" in msg:
            print(f"  {100 * frac:3.0f}%  {msg}")
            last[0] = frac

    print(f"Walk-forward backtest from {args.date_from} to {args.date_to or 'the last result'}"
          f" — trains on matches before the start, then predicts each day before seeing it")
    r = walk_forward(cfg, db, args.date_from, args.date_to, competitions=comps,
                     retrain_every=args.retrain_every, models=models, pick_opts=_pick_opts(args),
                     tune=not args.no_tune, value_edge=args.value_edge, progress=progress)
    if args.json:
        print(json.dumps(r.summary(), indent=2, default=float))
    else:
        print("\n" + render(r))
    out = Path(args.out) if args.out else cfg.paths.data_dir / "backtests"
    out.mkdir(parents=True, exist_ok=True)
    stem = f"backtest_{r.start}_{r.end}" + (f"_{'-'.join(comps)}" if comps else "")
    r.rows.to_csv(out / f"{stem}.csv", index=False)
    print(f"\nPer-match predictions: {out / (stem + '.csv')}")
    print(f"Chart: {plot_walkforward(r, out / (stem + '.png'))}")


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
                                  pick_opts=_pick_opts(args), competition=args.competition)
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

    d = sub.add_parser("data", help="your local match file: download / update / import / info / check")
    dsub = d.add_subparsers(dest="data_cmd", required=True)
    dd = dsub.add_parser("download", help="build the match CSV from football-data.org")
    du = dsub.add_parser("update", help="append matches played since the last run")
    for p_ in (dd, du):
        p_.add_argument("--to", help="last date to include, YYYY-MM-DD (default: today)")
        p_.add_argument("--only", help="comma-separated competition codes, e.g. E0,CL")
        p_.add_argument("--first-season", type=int, help="first season (default from config: 2022)")
        p_.add_argument("--file", help="CSV path (default: local_data.csv in the config)")
        p_.add_argument("--no-fallback", action="store_true",
                        help="don't fill gaps from football-data.co.uk")
    dd.add_argument("--force", action="store_true", help="overwrite an existing file")
    di = dsub.add_parser("import", help="load the CSV into the system (also automatic)")
    di.add_argument("--file", help="import this CSV instead of the configured one")
    for name, hlp in (("info", "matches per competition and season"),
                      ("check", "spot team names that may be the same club")):
        x = dsub.add_parser(name, help=hlp)
        x.add_argument("--file")
    sub.add_parser("train", help="tune, cross-validate, select and save models")

    pr = sub.add_parser("predict", help="predict a fixture")
    pr.add_argument("home"); pr.add_argument("away")
    pr.add_argument("--date", help="match date YYYY-MM-DD (default: today)")
    pr.add_argument("--neutral", action="store_true", help="neutral venue")
    pr.add_argument("--competition", help="competition code, e.g. CL or E0 (default: automatic; "
                                          "teams from different leagues = Champions League)")
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

    wf = sub.add_parser("backtest", help="walk-forward backtest over a date range: train on "
                        "matches before --from, predict each day up to --to before seeing it")
    wf.add_argument("--from", dest="date_from", required=True, help="first match day, YYYY-MM-DD")
    wf.add_argument("--to", dest="date_to", help="last match day (default: last result on file)")
    wf.add_argument("--competitions", help="score only these codes, e.g. E0,CL (all matches "
                                           "still feed the ratings)")
    wf.add_argument("--retrain-every", type=int, metavar="DAYS",
                    help="also retrain the models every N days (default: train once)")
    wf.add_argument("--quick", action="store_true",
                    help="train only Poisson, Dixon-Coles and LightGBM (much faster)")
    wf.add_argument("--no-tune", action="store_true", help="skip rating tuning (faster)")
    wf.add_argument("--value-edge", type=float, default=0.05,
                    help="value bets: model edge needed over the bookmaker's price (default 0.05)")
    wf.add_argument("--out", help="folder for the CSV and chart (default: data/backtests)")
    wf.add_argument("--json", action="store_true")
    _add_pick_args(wf)

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
     "app": cmd_app, "pick": cmd_pick, "data": cmd_data, "backtest-picks": cmd_backtest_picks,
     "backtest": cmd_backtest, "image": cmd_image}[args.cmd](cfg, args)


if __name__ == "__main__":
    main()
