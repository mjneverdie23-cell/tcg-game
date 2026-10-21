"""Shared back end for the interactive pickers (web app and terminal menu):
leagues, teams per league, predictions with charts, the model report."""

from __future__ import annotations

import base64
import io
import threading
import time
import uuid

import pandas as pd

from footypred.data.db import Database
from footypred.logging_utils import get_logger

log = get_logger("ui.service")

INTERNATIONAL = "INT"


class NotReady(Exception):
    """The app needs data or a trained model first (shown as a setup step)."""


class PredictionService:
    def __init__(self, cfg, db: Database | None = None):
        from footypred.data.localfile import sync_db
        self.cfg = cfg
        if db is None:
            db = Database(cfg.paths.db_file)
            sync_db(cfg, db)
        self.db = db
        self._lock = threading.Lock()          # models + matplotlib aren't thread-safe
        self._schedule_lock = threading.Lock()
        self.jobs = JobRunner()
        self._load()

    def _load(self) -> None:
        """(Re)build the predictor and the league/team lists from the DB.
        Without a trained model (or data) the app still runs, in setup mode."""
        from footypred.data.localfile import cup_codes
        from footypred.predict.predictor import Predictor
        self.predictor, self.model_error = None, None
        try:
            if self.db.count_matches():
                self.predictor = Predictor(self.cfg, self.db)
            else:
                self.model_error = "no matches loaded yet"
        except FileNotFoundError:
            self.model_error = "no trained model yet"
        except Exception as exc:                  # e.g. a model from an incompatible version
            log.exception("could not load the model")
            self.model_error = f"could not load the model: {exc}"
        tl = self.db.team_league(cup_codes(self.cfg))
        teams: dict[str, list[str]] = {}
        for team, lg in tl.items():
            teams.setdefault(lg, []).append(team)
        for lg in teams:
            teams[lg].sort()
        self._teams = teams

    # ---------------------------------------------------------------- lists
    def league_name(self, code: str) -> str:
        if code == INTERNATIONAL:
            return "International"
        return (self.cfg.leagues.get(code) or {}).get("name", code)

    def leagues(self) -> list[dict]:
        """Leagues with known teams, configured order first, internationals last."""
        order = list(self.cfg.leagues)
        codes = sorted(self._teams, key=lambda c: (c == INTERNATIONAL,
                                                   order.index(c) if c in order else 99, c))
        return [{"code": c, "name": self.league_name(c),
                 "country": (self.cfg.leagues.get(c) or {}).get("country", ""),
                 "teams": len(self._teams[c])} for c in codes]

    def teams(self, league: str | None = None) -> list[str]:
        if league:
            return list(self._teams.get(league, []))
        return sorted(t for ts in self._teams.values() for t in ts)

    def _model(self):
        if self.predictor is None:
            raise NotReady((self.model_error or "no trained model yet") +
                           " — open the Data tab: add your matches, then click Train model")
        return self.predictor

    # ----------------------------------------------------------- prediction
    def predict(self, home: str, away: str, date: str | None = None,
                neutral: bool = False, chart: bool = True, pick_opts: dict | None = None,
                competition: str | None = None):
        from footypred.predict.charts import plot_prediction
        predictor = self._model()
        with self._lock:
            pred = predictor.predict(home, away, date=date or None, neutral=neutral,
                                          pick_opts=pick_opts, competition=competition or None)
            png = None
            if chart:
                buf = io.BytesIO()
                plot_prediction(pred, buf)
                png = buf.getvalue()
        return pred, png

    def predict_payload(self, home, away, date=None, neutral=False, pick_opts=None,
                        chart: bool = True, competition: str | None = None) -> dict:
        pred, png = self.predict(home, away, date, neutral, chart=chart, pick_opts=pick_opts,
                                 competition=competition)
        d = pred.to_dict()
        d["chart_png"] = base64.b64encode(png).decode() if png else None
        return d

    def team_index(self) -> dict[str, str]:
        return {t: lg for lg, ts in self._teams.items() for t in ts}

    def read_image(self, data: bytes, engine: str = "auto") -> dict:
        from footypred.vision.reader import read_image
        img_cfg = self.cfg.raw.get("image") or {}
        with self._lock:
            return read_image(data, self.db.teams(), self.db.load_aliases(),
                              engine=engine or img_cfg.get("engine", "auto"),
                              claude_model=img_cfg.get("claude_model"))

    # --------------------------------------------------------------- report
    def evaluation_payload(self) -> dict:
        from footypred.models.summary import render_training_report
        from footypred.predict.charts import plot_evaluation
        b = self._model().bundle
        with self._lock:
            buf = io.BytesIO()
            plot_evaluation(b.result, buf)
        return {"version": b.version, "created": b.created,
                "report_text": render_training_report(b.result.report),
                "chart_png": base64.b64encode(buf.getvalue()).decode()}

    def competitions(self) -> list[dict]:
        """Competitions a fixture can be played in (for the override select)."""
        from footypred.data.localfile import cup_codes
        cups = cup_codes(self.cfg)
        comps = (self.predictor.competitions if self.predictor else
                 set(self.db.load_matches()["league"].dropna().unique()))
        return [{"code": c, "name": self.league_name(c)}
                for c in sorted(comps, key=lambda c: (c == INTERNATIONAL, c in cups, c))]

    # ------------------------------------------------------------ your data
    def data_info(self) -> dict:
        from footypred.data import localfile as lf
        from footypred.data.sources.football_data_org import api_key_from
        path = lf.csv_path(self.cfg)
        info = {"path": str(path), "exists": path.exists(),
                "aliases_path": str(lf.aliases_path(self.cfg)),
                "auto_import": bool((self.cfg.raw.get("local_data") or {}).get("auto_import", True)),
                "api_key": bool(api_key_from(self.cfg.raw.get("football_data_org") or {})),
                "data_source": self.db.get_meta("data_source", "unknown"),
                "last_update": self.db.get_meta("last_update", ""),
                "db_matches": self.db.count_matches(),
                **self._model_info(),
                "competitions": [],
                "config_competitions": [{"code": sp.key, "name": sp.name}
                                        for sp in lf.specs_from_config(self.cfg)],
                "first_season": lf.first_season(self.cfg)}
        if path.exists():
            df = lf.read_csv(path)
            info.update({"rows": len(df), "size_kb": round(path.stat().st_size / 1024, 1),
                         "modified": pd.Timestamp(path.stat().st_mtime, unit="s")
                         .tz_localize("UTC").tz_convert(None).isoformat(timespec="seconds")})
            if len(df):
                info["first"], info["last"] = df["date"].min(), df["date"].max()
                g = df.groupby("competition").agg(matches=("date", "size"), first=("date", "min"),
                                                  last=("date", "max"),
                                                  sources=("source", lambda x: ", ".join(sorted(set(x)))))
                info["competitions"] = [{"code": c, "name": self.league_name(c), **r}
                                        for c, r in g.to_dict("index").items()]
        m = self.db.load_matches()
        if len(m):
            info["db_first"] = str(m["date"].min().date())
            info["db_last"] = str(m["date"].max().date())
        return info

    def _model_info(self) -> dict:
        p = self.predictor
        if p is None:
            return {"model": None, "model_data_source": None, "model_trained_until": None,
                    "model_matches": None, "model_error": self.model_error, "retrain": None}
        rep = p.res.report or {}
        hint, now = None, self.db.get_meta("data_source")
        trained_n = rep.get("n_matches")
        n = self.db.count_matches()
        if rep.get("data_source") and now and rep["data_source"] != now:
            hint = f"the model was trained on {rep['data_source']} data but {now} data is loaded"
        elif trained_n and n > trained_n * 1.05 + 20:
            hint = f"{n - trained_n:,} matches were added since the model was trained"
        return {"model": p.bundle.version, "model_created": p.bundle.created,
                "model_selected": p.res.selected,
                "model_data_source": rep.get("data_source"), "model_matches": trained_n,
                "model_trained_until": rep.get("trained_until") or (
                    str(p.state.last_date.date()) if p.state.last_date is not None else None),
                "model_error": None, "retrain": hint}

    def reload_data(self) -> dict:
        """Re-import the match file now and refresh teams and feature state."""
        from footypred.data.localfile import csv_path, sync_db
        if not csv_path(self.cfg).exists():
            raise ValueError(f"{csv_path(self.cfg)} not found — download it first (Data tab)")
        with self._lock:
            n = sync_db(self.cfg, self.db, force=True)
            self._load()
        return {"imported": n or 0, **self.data_info()}

    def merge_files(self, params: dict) -> dict:
        """Add matches from other CSV files on this PC (paths, not uploads)
        that aren't in your match file yet; same as `footy data merge`."""
        from footypred.data import localfile as lf
        raw = params.get("paths") or []
        if isinstance(raw, str):
            raw = raw.splitlines()
        paths = [p.strip().strip('"').strip("'") for p in raw if p and p.strip()]
        if not paths:
            raise ValueError("enter the path of a CSV file or a folder of CSV files")
        path = lf.csv_path(self.cfg)
        with self._lock:
            r = lf.merge(path, paths, lf.specs_from_config(self.cfg),
                         None if params.get("all_seasons") else lf.first_season(self.cfg),
                         competition=(params.get("competition") or "").strip() or None,
                         aliases=lf.load_aliases(self.cfg), fill=bool(params.get("fill")),
                         dry_run=bool(params.get("dry_run")))
            if not r["dry_run"] and (r["added"] or r["filled"]):
                lf.sync_db(self.cfg, self.db)
                self._load()
        return {**r, "text": lf.render_merge(r, path), "info": self.data_info()}

    def start_update(self) -> dict:
        """Background job: append new matches from football-data.org to the
        file (same as `footy data update`), then re-import it."""
        from footypred.data import localfile as lf
        path = lf.csv_path(self.cfg)
        if not path.exists():
            raise ValueError(f"{path} not found — download it first (Data tab)")

        def work(job):
            fetcher = lf.make_fetcher(self.cfg, progress=job.say)
            job.say(f"Updating {path}")
            r = lf.update(fetcher, lf.specs_from_config(self.cfg), path, lf.first_season(self.cfg))
            job.say(f"Added {r['added']} new matches"
                    + (f", corrected {r['corrected']}" if r["corrected"] else "")
                    + f" · file now has {r['rows']} matches")
            with self._lock:
                lf.sync_db(self.cfg, self.db)
                self._load()
            self._refresh_schedule_quietly(job.say)
            return {**r, "info": self.data_info()}
        return self.jobs.start("update", work)

    def start_backtest(self, params: dict) -> dict:
        from footypred.predict.walkforward import QUICK_MODELS, walk_forward

        def work(job):
            r = walk_forward(self.cfg, self.db, params["from"], params.get("to") or None,
                             competitions=params.get("competitions") or None,
                             retrain_every=params.get("retrain_every") or None,
                             models=QUICK_MODELS if params.get("quick") else None,
                             pick_opts=params.get("pick_opts") or None,
                             tune=not params.get("no_tune"),
                             progress=lambda f, m: job.say(m, f), should_stop=job.cancelled)
            return self._backtest_payload(r, job)
        return self.jobs.start("backtest", work)

    def _backtest_payload(self, r, job) -> dict:
        from footypred.predict.charts import plot_walkforward
        from footypred.predict.walkforward import render
        with self._lock:
            buf = io.BytesIO()
            plot_walkforward(r, buf)
        job.files["csv"] = r.rows.to_csv(index=False).encode()
        job.files["name"] = f"backtest_{r.start}_{r.end}.csv"
        cols = ["date", "league", "home", "away", "fthg", "ftag", "p_home", "p_draw", "p_away",
                "p_o25", "p_btts", "xg_home", "xg_away", "pick_balanced", "pick_balanced_hit",
                "pick_safe", "pick_safe_hit", "pick_bold", "pick_bold_hit"]
        table = r.rows[[c for c in cols if c in r.rows]].tail(1500)
        table = table.astype(object).where(table.notna(), None)
        return {**r.summary(), "matches": len(r.rows), "text": render(r),
                "chart_png": base64.b64encode(buf.getvalue()).decode(),
                "table": table.to_dict("records")}

    def date_range(self) -> dict:
        m = self.db.load_matches()
        if m.empty:
            return {}
        d = m["date"]
        return {"first": str(d.min().date()), "last": str(d.max().date()),
                # earliest sensible start: about a year of history first
                "min_start": str((d.min() + pd.Timedelta(days=365)).date())}

    # ------------------------------------------------------------ schedule
    def schedule(self) -> dict:
        """Fixtures and results from 3 days back to 5 ahead (Schedule tab)."""
        from footypred.data import schedule as sch
        w = sch.window(self.cfg)
        teams = set(self.db.teams())
        for m in w["matches"]:
            m["home_known"], m["away_known"] = m["home"] in teams, m["away"] in teams
            m["known"] = m["home_known"] and m["away_known"]
            m["predictable"] = (m["known"] and self.predictor is not None
                                and m["status"] not in ("FINISHED", "AWARDED", "CANCELLED"))
        w["has_key"] = self.settings()["api_key_set"]
        w["ready"] = self.predictor is not None
        return w

    def refresh_schedule(self) -> dict:
        """Fetch the window again (football-data.org + co.uk fixture lists)."""
        from footypred.data import localfile as lf
        from footypred.data import schedule as sch
        if not self._schedule_lock.acquire(blocking=False):
            raise ValueError("the schedule is already being refreshed")
        try:
            from footypred.data.http import HttpClient
            from footypred.data.sources.football_data_org import FDOrgClient
            f = lf.make_fetcher(self.cfg, progress=None)
            # the page waits for this: fail fast instead of the downloader's long retries
            client = f.client and FDOrgClient(f.client.api_key, base_url=f.client.base_url,
                                              min_interval=f.client.min_interval, max_retries=2,
                                              timeout=20)
            http = f.http and HttpClient(self.cfg.paths.cache_dir, 1.0, 15, 1)
            r = sch.refresh(self.cfg, client, http)
        finally:
            self._schedule_lock.release()
        return {**self.schedule(), "notes": r["notes"]}

    def _refresh_schedule_quietly(self, say) -> None:
        try:
            r = self.refresh_schedule()
            say(f"Schedule refreshed: {len(r['matches'])} matches from "
                f"{(pd.Timestamp(r['today']) - pd.Timedelta(days=r['back'])).date()} to "
                f"{(pd.Timestamp(r['today']) + pd.Timedelta(days=r['ahead'])).date()}")
        except Exception as exc:                  # the schedule is a bonus here
            say(f"(schedule not refreshed: {exc})")

    def predict_batch(self, items: list[dict], pick_opts: dict | None = None) -> list[dict]:
        """Best pick + follow-ups for several fixtures at once."""
        from footypred.predict.batch import pick_summary
        predictor = self._model()
        out = []
        for it in (items or [])[:80]:
            comp = it.get("competition")
            comp = comp if comp in predictor.competitions else None
            try:
                pred, _ = self.predict(it.get("home", ""), it.get("away", ""), it.get("date") or None,
                                       bool(it.get("neutral")), chart=False, pick_opts=pick_opts,
                                       competition=comp)
                out.append({"ok": True, "id": it.get("id"), **pick_summary(pred)})
            except Exception as exc:              # one fixture never stops the rest
                out.append({"ok": False, "id": it.get("id"), "error": str(exc)})
        return out

    # --------------------------------------------------------- setup jobs
    def start_download(self, force: bool = False) -> dict:
        """Background job: build the match file from football-data.org (+ the
        co.uk fallback), like `footy data download`."""
        import shutil
        from footypred.data import localfile as lf
        path = lf.csv_path(self.cfg)
        if path.exists() and not force:
            raise ValueError("you already have a match file — use Update to add new matches, "
                             "or tick 'replace my file' to rebuild it from scratch")

        def work(job):
            specs, first = lf.specs_from_config(self.cfg), lf.first_season(self.cfg)
            end = pd.Timestamp.today().normalize()
            total = sum(len(lf.seasons_between(first, end, sp.calendar_year)) for sp in specs)
            done = [0]

            def say(msg):
                if msg.startswith("  "):          # one line per competition-season
                    done[0] += 1
                job.say(msg, done[0] / max(total, 1) * 0.95)
            job.say(f"Downloading {len(specs)} competitions, seasons {first}/{str(first + 1)[2:]} "
                    f"to {end.date()} (about {total * 7 // 60 + 1} min on the free plan)")
            df = lf.download(lf.make_fetcher(self.cfg, progress=say), specs, first, end)
            if df.empty:
                raise ValueError("nothing was downloaded — check your API key (Settings) and "
                                 "internet connection")
            if path.exists():
                shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
            lf.write_csv(df, path)
            job.say(f"Saved {len(df):,} matches to {path}")
            with self._lock:
                lf.sync_db(self.cfg, self.db)
                self._load()
            self._refresh_schedule_quietly(job.say)
            return {"rows": len(df), "info": self.data_info()}
        return self.jobs.start("download", work)

    def start_train(self, quick: bool = False) -> dict:
        """Background job: train on everything loaded and switch to the new
        model (same as `footy train`)."""
        from footypred.models.pipeline import QUICK_MODELS, train_and_save
        if not self.db.count_matches():
            raise ValueError("no matches loaded yet — add your match file (or the demo data) first")

        def work(job):
            r = train_and_save(self.cfg, self.db, models=QUICK_MODELS if quick else None,
                               say=job.say)
            with self._lock:
                self._load()
            return {**r, "status": self.status()}
        return self.jobs.start("training", work)

    def start_extra(self, params: dict) -> dict:
        """Background job: build Süper Lig + Eliteserien from football-data.co.uk
        files (optionally downloading them) and add them to the match file."""
        from footypred.data import localfile as lf
        from footypred.data.extra_leagues import build

        def lines(v):
            return [x for x in (v.splitlines() if isinstance(v, str) else (v or [])) if x.strip()]

        def work(job):
            res = build(self.cfg, {"T1": lines(params.get("super_lig")),
                                   "NOR": lines(params.get("eliteserien"))},
                        fetch=bool(params.get("download")), merge=bool(params.get("merge", True)),
                        say=job.say)
            if not res["written"]:
                raise ValueError("; ".join(res["errors"]) or "nothing was built")
            if res["merge"] and res["merge"]["added"]:
                with self._lock:
                    lf.sync_db(self.cfg, self.db)
                    self._load()
            return {**res, "info": self.data_info()}
        return self.jobs.start("Süper Lig + Eliteserien build", work)

    def start_demo(self) -> dict:
        """Background job: load the synthetic demo data (no internet needed)."""
        from footypred.data import localfile as lf
        from footypred.data.pipeline import bootstrap
        if lf.csv_path(self.cfg).exists():
            raise ValueError("you have your own match file — the demo data would be replaced "
                             "by it on the next start, so it isn't loaded")
        if self.db.count_matches() and self.db.get_meta("data_source") != "synthetic":
            raise ValueError("real matches are already loaded")

        def work(job):
            job.say("Generating the synthetic demo seasons …", 0.1)
            with self._lock:
                n = bootstrap(self.cfg, self.db)
                self.db.set_meta("csv_signature", "")
                self._load()
            job.say(f"Loaded {n:,} demo matches — now train a model", 1.0)
            return {"matches": n, "info": self.data_info()}
        return self.jobs.start("demo data", work)

    # ------------------------------------------------------- names & aliases
    def name_pairs(self) -> list[dict]:
        """Team names that look like the same club (merge them with an alias)."""
        from footypred.data import localfile as lf
        path = lf.csv_path(self.cfg)
        df = lf.read_csv(path) if path.exists() else \
            self.db.load_matches().rename(columns={"league": "competition"})
        df = lf.apply_aliases(df, lf.load_aliases(self.cfg))     # merges already made
        counts = pd.concat([df["home"], df["away"]]).value_counts()
        return [{"competition": c, "a": a, "b": b, "score": round(r),
                 "a_matches": int(counts.get(a, 0)), "b_matches": int(counts.get(b, 0))}
                for c, a, b, r in lf.name_check(df)]

    def add_alias(self, frm: str, to: str) -> dict:
        """Merge team name `frm` into `to` (written to your aliases file)."""
        from footypred.data import localfile as lf
        frm, to = (frm or "").strip(), (to or "").strip()
        if not frm or not to or frm == to:
            raise ValueError("give two different team names")
        if "," in frm or "," in to:
            raise ValueError("team names can't contain commas")
        p = lf.aliases_path(self.cfg)
        p.parent.mkdir(parents=True, exist_ok=True)
        new = not p.exists() or p.stat().st_size == 0
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(("from,to\n" if new else "") + f"{frm},{to}\n")
        with self._lock:
            lf.sync_db(self.cfg, self.db, force=True)
            self._load()
        return {"aliases_path": str(p), "pairs": self.name_pairs()}

    # ------------------------------------------------------------ settings
    def settings(self) -> dict:
        import os
        from footypred.config import settings_path
        from footypred.data import localfile as lf
        fd = self.cfg.raw.get("football_data_org") or {}
        env = os.environ.get("FOOTBALL_DATA_API_KEY")
        key = env or fd.get("api_key")
        return {"api_key_set": bool(key),
                "api_key_source": "environment variable" if env else ("settings" if key else None),
                "api_key_hint": ("…" + key[-4:]) if key and len(key) > 8 else None,
                "csv": str(lf.csv_path(self.cfg)), "first_season": lf.first_season(self.cfg),
                "settings_path": str(settings_path(self.cfg.paths.root))}

    def save_settings(self, params: dict) -> dict:
        from footypred.config import deep_update, save_local_settings
        from footypred.data import localfile as lf
        upd: dict = {}
        if "api_key" in params:
            key = (params.get("api_key") or "").strip()
            if key and (len(key) < 16 or not key.isalnum()):
                raise ValueError("that doesn't look like a football-data.org API key "
                                 "(32 letters and digits, from the email they sent you)")
            upd.setdefault("football_data_org", {})["api_key"] = key or None
        if params.get("first_season") not in (None, ""):
            try:
                fs = int(params["first_season"])
            except (TypeError, ValueError) as exc:
                raise ValueError("first season must be a year, e.g. 2022") from exc
            if not 1990 <= fs <= pd.Timestamp.today().year:
                raise ValueError("first season must be a year between 1990 and this year")
            upd.setdefault("football_data_org", {})["first_season"] = fs
        old_csv = lf.csv_path(self.cfg)
        if params.get("csv") not in (None, ""):
            csv = str(params["csv"]).strip().strip('"').strip("'")
            if not csv.lower().endswith(".csv"):
                raise ValueError("the match file must be a .csv file")
            upd.setdefault("local_data", {})["csv"] = csv
        if not upd:
            return self.settings()
        save_local_settings(upd, self.cfg.paths.root)
        deep_update(self.cfg.raw, upd)
        fd = self.cfg.raw.get("football_data_org") or {}
        if fd.get("api_key") is None:
            fd.pop("api_key", None)
        if lf.csv_path(self.cfg) != old_csv:
            with self._lock:
                lf.sync_db(self.cfg, self.db, force=True)
                self._load()
        return self.settings()

    def status(self) -> dict:
        p = self.predictor
        n = self.db.count_matches()
        return {"ready": p is not None, "has_data": n > 0, "matches": n,
                "version": p.bundle.version if p else None,
                "model": p.res.selected if p else None, "model_error": self.model_error,
                "data_source": self.db.get_meta("data_source", "none" if not n else "unknown"),
                "last_update": self.db.get_meta("last_update", ""),
                "today": str(pd.Timestamp.today().date())}


class Job:
    def __init__(self, kind: str):
        self.id = uuid.uuid4().hex[:12]
        self.kind, self.status, self.progress = kind, "running", 0.0
        self.log: list[str] = []
        self.result = self.error = None
        self.files: dict = {}
        self.started = time.time()
        self._stop = threading.Event()

    def say(self, msg: str, frac: float | None = None) -> None:
        if frac is not None:
            self.progress = max(0.0, min(1.0, float(frac)))
        if msg and (not self.log or self.log[-1] != msg):
            self.log.append(msg)
            del self.log[:-200]

    def cancelled(self) -> bool:
        return self._stop.is_set()

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "status": self.status,
                "progress": round(self.progress, 3), "log": self.log[-30:],
                "seconds": round(time.time() - self.started, 1), "error": self.error,
                "result": self.result if self.status == "done" else None}


class JobRunner:
    """One background job at a time (updates and backtests are heavy)."""

    def __init__(self):
        self.jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def start(self, kind: str, work) -> dict:
        with self._lock:
            busy = next((j for j in self.jobs.values() if j.status == "running"), None)
            if busy:
                raise ValueError(f"a {busy.kind} is already running — wait for it or cancel it")
            job = Job(kind)
            self.jobs[job.id] = job

        def run():
            try:
                job.result = work(job)
                job.status, job.progress = "done", 1.0
            except InterruptedError:
                job.status = "cancelled"
            except Exception as exc:            # reported to the page
                log.exception("%s job failed", kind)
                job.status, job.error = "error", str(exc)
        threading.Thread(target=run, daemon=True).start()
        return job.to_dict()

    def current(self) -> dict | None:
        """The running job, if any (so a reloaded page can follow it again)."""
        job = next((j for j in self.jobs.values() if j.status == "running"), None)
        return job.to_dict() if job else None

    def get(self, job_id: str) -> Job:
        if job_id not in self.jobs:
            raise ValueError("unknown job")
        return self.jobs[job_id]

    def cancel(self, job_id: str) -> dict:
        job = self.get(job_id)
        job._stop.set()
        return job.to_dict()
