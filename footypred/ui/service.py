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


class PredictionService:
    def __init__(self, cfg, db: Database | None = None):
        from footypred.data.localfile import sync_db
        self.cfg = cfg
        if db is None:
            db = Database(cfg.paths.db_file)
            sync_db(cfg, db)
        self.db = db
        self._lock = threading.Lock()          # models + matplotlib aren't thread-safe
        self.jobs = JobRunner()
        self._load()

    def _load(self) -> None:
        """(Re)build the predictor and the league/team lists from the DB."""
        from footypred.data.localfile import cup_codes
        from footypred.predict.predictor import Predictor
        self.predictor = Predictor(self.cfg, self.db)
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

    # ----------------------------------------------------------- prediction
    def predict(self, home: str, away: str, date: str | None = None,
                neutral: bool = False, chart: bool = True, pick_opts: dict | None = None,
                competition: str | None = None):
        from footypred.predict.charts import plot_prediction
        with self._lock:
            pred = self.predictor.predict(home, away, date=date or None, neutral=neutral,
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
        b = self.predictor.bundle
        with self._lock:
            buf = io.BytesIO()
            plot_evaluation(b.result, buf)
        return {"version": b.version, "created": b.created,
                "report_text": render_training_report(b.result.report),
                "chart_png": base64.b64encode(buf.getvalue()).decode()}

    def competitions(self) -> list[dict]:
        """Competitions a fixture can be played in (for the override select)."""
        return [{"code": c, "name": self.league_name(c)}
                for c in sorted(self.predictor.competitions,
                                key=lambda c: (c == INTERNATIONAL, c in self.predictor.cups, c))]

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
                "model": self.predictor.bundle.version,
                "model_data_source": (self.predictor.res.report or {}).get("data_source"),
                "model_trained_until": str(self.predictor.state.last_date.date())
                if self.predictor.state.last_date is not None else None,
                "competitions": []}
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

    def reload_data(self) -> dict:
        """Re-import the match file now and refresh teams and feature state."""
        from footypred.data.localfile import csv_path, sync_db
        if not csv_path(self.cfg).exists():
            raise ValueError(f"{csv_path(self.cfg)} not found — run `footy data download` first")
        with self._lock:
            n = sync_db(self.cfg, self.db, force=True)
            self._load()
        return {"imported": n or 0, **self.data_info()}

    def start_update(self) -> dict:
        """Background job: append new matches from football-data.org to the
        file (same as `footy data update`), then re-import it."""
        from footypred.data import localfile as lf
        path = lf.csv_path(self.cfg)
        if not path.exists():
            raise ValueError(f"{path} not found — run `footy data download` first")

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

    def status(self) -> dict:
        b = self.predictor.bundle
        return {"version": b.version, "model": b.result.selected,
                "data_source": self.db.get_meta("data_source", "unknown"),
                "last_update": self.db.get_meta("last_update", ""),
                "matches": self.db.count_matches(),
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

    def get(self, job_id: str) -> Job:
        if job_id not in self.jobs:
            raise ValueError("unknown job")
        return self.jobs[job_id]

    def cancel(self, job_id: str) -> dict:
        job = self.get(job_id)
        job._stop.set()
        return job.to_dict()
