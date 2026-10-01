"""Shared back end for the interactive pickers (web app and terminal menu):
leagues, teams per league, predictions with charts, the model report."""

from __future__ import annotations

import base64
import io
import threading

import pandas as pd

from footypred.data.db import Database
from footypred.logging_utils import get_logger

log = get_logger("ui.service")

INTERNATIONAL = "INT"


class PredictionService:
    def __init__(self, cfg, db: Database | None = None):
        from footypred.predict.predictor import Predictor
        self.cfg = cfg
        self.db = db or Database(cfg.paths.db_file)
        self.predictor = Predictor(cfg, self.db)
        self._lock = threading.Lock()          # models + matplotlib aren't thread-safe
        tl = self.db.team_league()
        self._teams: dict[str, list[str]] = {}
        for team, lg in tl.items():
            self._teams.setdefault(lg, []).append(team)
        for lg in self._teams:
            self._teams[lg].sort()

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
                neutral: bool = False, chart: bool = True):
        from footypred.predict.charts import plot_prediction
        with self._lock:
            pred = self.predictor.predict(home, away, date=date or None, neutral=neutral)
            png = None
            if chart:
                buf = io.BytesIO()
                plot_prediction(pred, buf)
                png = buf.getvalue()
        return pred, png

    def predict_payload(self, home, away, date=None, neutral=False) -> dict:
        pred, png = self.predict(home, away, date, neutral)
        d = pred.to_dict()
        d["chart_png"] = base64.b64encode(png).decode() if png else None
        return d

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

    def status(self) -> dict:
        b = self.predictor.bundle
        return {"version": b.version, "model": b.result.selected,
                "data_source": self.db.get_meta("data_source", "unknown"),
                "last_update": self.db.get_meta("last_update", ""),
                "matches": self.db.count_matches(),
                "today": str(pd.Timestamp.today().date())}
