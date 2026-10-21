"""Local web app: choose league and teams from dropdowns, get the
four-market prediction, past-match evidence and analysis charts.

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
                        chart=q.get("chart", "1") != "0"))
                elif url.path == "/api/team-index":
                    self._json(service.team_index())
                elif url.path == "/api/evaluation":
                    self._json(service.evaluation_payload())
                else:
                    self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            except (TeamNameError, ValueError) as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:                      # keep the app alive
                log.exception("request failed: %s", self.path)
                self._json({"error": f"internal error: {exc}"},
                           HTTPStatus.INTERNAL_SERVER_ERROR)

        def do_POST(self):
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            if url.path != "/api/image":
                return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
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
    httpd = make_server(service, host, port)
    url = f"http://{host}:{httpd.server_address[1]}/"
    print(f"footypred is running at {url}  (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
