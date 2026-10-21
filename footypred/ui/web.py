"""Local web app: choose league and teams from dropdowns, get the
four-market prediction, past-match evidence and analysis charts; build and
update your match file, train, and backtest, all from the browser.

Standard library only (http.server); binds to localhost.

    footy app [--port 8765] [--no-browser]
"""

from __future__ import annotations

import json
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from urllib.parse import parse_qs, urlparse

from footypred.data.names import TeamNameError
from footypred.logging_utils import get_logger
from footypred.ui.service import NotReady

log = get_logger("ui.web")


def _page() -> bytes:
    return resources.files("footypred.ui").joinpath("static/index.html").read_bytes()


def pick_opts(q: dict) -> dict:
    """Best-pick settings from query parameters (invalid values are ignored)."""
    o = {}
    if q.get("markets"):
        allowed = {"1x2", "totals", "ou25", "btts", "team_totals"}
        o["markets"] = [m for m in q["markets"].split(",") if m in allowed]
    if q.get("style") in ("safe", "balanced", "bold"):
        o["style"] = q["style"]
    for key, lo, hi in (("min_odds", 1.0, 10.0), ("max_odds", 1.0, 50.0), ("form_weight", 0.0, 1.0),
                        ("min_lift", 0.0, 0.5)):
        try:
            if q.get(key) not in (None, ""):
                o[key] = min(max(float(q[key]), lo), hi)
        except ValueError:
            pass
    return o


def backtest_params(body: dict) -> dict:
    """Validate the backtest form (dates, competitions, options)."""
    import pandas as pd
    out = {}
    for key in ("from", "to"):
        v = (body.get(key) or "").strip()
        if v:
            try:
                out[key] = str(pd.Timestamp(v).date())
            except ValueError as exc:
                raise ValueError(f"bad {key} date '{v}'") from exc
    if "from" not in out:
        raise ValueError("choose a start date")
    comps = body.get("competitions") or []
    if isinstance(comps, str):
        comps = comps.split(",")
    out["competitions"] = [c.strip() for c in comps if str(c).strip()]
    try:
        n = int(body.get("retrain_every") or 0)
    except (TypeError, ValueError):
        n = 0
    out["retrain_every"] = n if n >= 7 else None
    out["quick"] = bool(body.get("quick"))
    out["no_tune"] = bool(body.get("no_tune"))
    out["pick_opts"] = pick_opts({k: str(v) for k, v in (body.get("pick_opts") or {}).items()})
    return out


def make_handler(service):
    class Handler(BaseHTTPRequestHandler):
        server_version = "footypred"

        def log_message(self, fmt, *args):          # route to our logger
            log.debug("%s - %s", self.address_string(), fmt % args)

        def _send(self, status, body: bytes, ctype: str):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, status=HTTPStatus.OK):
            self._send(status, json.dumps(obj, default=float).encode(),
                       "application/json; charset=utf-8")

        def do_GET(self):
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                if url.path in ("/", "/index.html"):
                    self._send(HTTPStatus.OK, _page(), "text/html; charset=utf-8")
                elif url.path == "/api/status":
                    self._json(service.status())
                elif url.path == "/api/leagues":
                    self._json(service.leagues())
                elif url.path == "/api/teams":
                    self._json(service.teams(q.get("league") or None))
                elif url.path == "/api/predict":
                    if not q.get("home") or not q.get("away"):
                        return self._json({"error": "choose both teams"}, HTTPStatus.BAD_REQUEST)
                    self._json(service.predict_payload(
                        q["home"], q["away"], q.get("date") or None,
                        q.get("neutral") in ("1", "true", "on"), pick_opts=pick_opts(q),
                        chart=q.get("chart", "1") != "0", competition=q.get("competition")))
                elif url.path == "/api/team-index":
                    self._json(service.team_index())
                elif url.path == "/api/evaluation":
                    self._json(service.evaluation_payload())
                elif url.path == "/api/competitions":
                    self._json(service.competitions())
                elif url.path == "/api/data":
                    self._json(service.data_info())
                elif url.path == "/api/date-range":
                    self._json(service.date_range())
                elif url.path == "/api/schedule":
                    self._json(service.schedule())
                elif url.path == "/api/data/names":
                    self._json(service.name_pairs())
                elif url.path == "/api/settings":
                    self._json(service.settings())
                elif url.path == "/api/job/current":
                    self._json({"job": service.jobs.current()})
                elif url.path == "/api/job":
                    self._json(service.jobs.get(q.get("id", "")).to_dict())
                elif url.path == "/api/backtest.csv":
                    job = service.jobs.get(q.get("id", ""))
                    if "csv" not in job.files:
                        return self._json({"error": "no results yet"}, HTTPStatus.NOT_FOUND)
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "text/csv; charset=utf-8")
                    self.send_header("Content-Disposition",
                                     f'attachment; filename="{job.files["name"]}"')
                    self.send_header("Content-Length", str(len(job.files["csv"])))
                    self.end_headers()
                    self.wfile.write(job.files["csv"])
                else:
                    self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            except NotReady as exc:
                self._json({"error": str(exc), "setup": True}, HTTPStatus.CONFLICT)
            except (TeamNameError, ValueError) as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:                      # keep the app alive
                log.exception("request failed: %s", self.path)
                self._json({"error": f"internal error: {exc}"},
                           HTTPStatus.INTERNAL_SERVER_ERROR)

        def do_POST(self):
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            if url.path == "/api/image":
                return self._image(q)
            try:
                if url.path == "/api/data/reload":
                    self._json(service.reload_data())
                elif url.path == "/api/schedule/refresh":
                    self._json(service.refresh_schedule())
                elif url.path == "/api/predict-batch":
                    b = self._body_json()
                    self._json(service.predict_batch(
                        b.get("fixtures") or [],
                        pick_opts({k: str(v) for k, v in (b.get("pick_opts") or {}).items()})))
                elif url.path == "/api/data/merge":
                    self._json(service.merge_files(self._body_json()))
                elif url.path == "/api/data/update":
                    self._json(service.start_update())
                elif url.path == "/api/data/download":
                    self._json(service.start_download(bool(self._body_json().get("force"))))
                elif url.path == "/api/data/extra":
                    self._json(service.start_extra(self._body_json()))
                elif url.path == "/api/data/demo":
                    self._json(service.start_demo())
                elif url.path == "/api/data/alias":
                    b = self._body_json()
                    self._json(service.add_alias(b.get("from"), b.get("to")))
                elif url.path == "/api/train":
                    self._json(service.start_train(bool(self._body_json().get("quick"))))
                elif url.path == "/api/settings":
                    self._json(service.save_settings(self._body_json()))
                elif url.path == "/api/backtest":
                    self._json(service.start_backtest(backtest_params(self._body_json())))
                elif url.path == "/api/job/cancel":
                    self._json(service.jobs.cancel(q.get("id", "")))
                else:
                    self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            except NotReady as exc:
                self._json({"error": str(exc), "setup": True}, HTTPStatus.CONFLICT)
            except ValueError as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                log.exception("request failed: %s", self.path)
                self._json({"error": f"internal error: {exc}"},
                           HTTPStatus.INTERNAL_SERVER_ERROR)

        def _body_json(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 100_000:
                raise ValueError("request too large")
            try:
                return json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError as exc:
                raise ValueError(f"bad JSON: {exc}") from exc

        def _image(self, q):
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0:
                    return self._json({"error": "no image received"}, HTTPStatus.BAD_REQUEST)
                if n > MAX_UPLOAD:
                    return self._json({"error": "image too large (max 15 MB)"},
                                      HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                data = self.rfile.read(n)
                self._json(service.read_image(data, q.get("engine") or ""))
            except Exception as exc:
                log.exception("image read failed")
                msg = str(exc) if "pip install" in str(exc) or "anthropic" in str(exc).lower() \
                    else f"could not read the image: {exc}"
                self._json({"error": msg}, HTTPStatus.BAD_REQUEST)

    return Handler


MAX_UPLOAD = 15 * 1024 * 1024


def make_server(service, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(service))


def serve(cfg, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    from footypred.ui.service import PredictionService
    print("Loading model and match history ...")
    service = PredictionService(cfg)
    try:
        httpd = make_server(service, host, port)
    except OSError:                       # port taken: probably already running
        url = f"http://{host}:{port}/"
        print(f"Port {port} is in use — footypred is probably already running: opening {url}")
        if open_browser:
            webbrowser.open(url)
        return
    url = f"http://{host}:{httpd.server_address[1]}/"
    if service.predictor is None:
        print(f"Setup needed ({service.model_error}): the Data tab walks you through it.")
    print(f"footypred is running at {url}  (keep this window open; Ctrl+C or close it to stop)")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
