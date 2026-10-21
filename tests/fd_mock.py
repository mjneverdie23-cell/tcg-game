"""A small stand-in for api.football-data.org (v4) used by the tests.

Serves /v4/competitions and /v4/competitions/{code}/matches?season=YYYY
from an in-memory list of matches in the real response format, checks the
X-Auth-Token header, answers 403 for competitions outside the "plan", and
can return one 429 to exercise the rate-limit path.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

OFFICIAL = {"Arsenal": "Arsenal FC", "Chelsea": "Chelsea FC", "Liverpool": "Liverpool FC",
            "Manchester City": "Manchester City FC", "Bayern Munich": "FC Bayern München",
            "Borussia Dortmund": "Borussia Dortmund", "Real Madrid": "Real Madrid CF",
            "Barcelona": "FC Barcelona", "Atletico Madrid": "Club Atlético de Madrid",
            "Paris Saint-Germain": "Paris Saint-Germain FC", "Inter Milan": "FC Internazionale Milano"}

COMPETITIONS = [
    {"id": 2021, "code": "PL", "name": "Premier League", "area": {"name": "England"}},
    {"id": 2002, "code": "BL1", "name": "Bundesliga", "area": {"name": "Germany"}},
    {"id": 2014, "code": "PD", "name": "Primera Division", "area": {"name": "Spain"}},
    {"id": 2001, "code": "CL", "name": "UEFA Champions League", "area": {"name": "Europe"}},
    {"id": 2003, "code": "TSL", "name": "Süper Lig", "area": {"name": "Turkey"}},
]


def match(mid, comp, utc, home, away, ft, ht, stage="REGULAR_SEASON", status="FINISHED",
          duration="REGULAR", regular=None, extra=None, season_start=None):
    score = {"winner": None, "duration": duration,
             "fullTime": {"home": ft[0], "away": ft[1]} if ft else {"home": None, "away": None},
             "halfTime": {"home": ht[0], "away": ht[1]} if ht else {"home": None, "away": None}}
    if regular:
        score["regularTime"] = {"home": regular[0], "away": regular[1]}
    if extra:
        score["extraTime"] = {"home": extra[0], "away": extra[1]}
    y = int(utc[:4]) if int(utc[5:7]) >= 7 else int(utc[:4]) - 1
    return {"id": mid, "utcDate": utc, "status": status, "matchday": 1, "stage": stage,
            "season": {"startDate": season_start or f"{y}-08-01"},
            "homeTeam": {"name": OFFICIAL.get(home, home), "crest": f"https://crests.test/{mid}h.png"},
            "awayTeam": {"name": OFFICIAL.get(away, away), "crest": f"https://crests.test/{mid}a.png"},
            "score": score, "lastUpdated": utc, "competition": {"code": comp}}


def pd_days(lo: str, hi: str) -> int:
    from datetime import date
    a, b = date.fromisoformat(lo), date.fromisoformat(hi)
    return (b - a).days + 1


class MockFDOrg:
    def __init__(self, matches: dict[str, list[dict]], key="test-key", restricted=("TSL",),
                 throttle_once=False):
        self.matches, self.key, self.restricted = matches, key, set(restricted)
        self.throttle_once = throttle_once
        self.calls: list[str] = []
        self.window_calls = 0
        mock = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, code, obj, headers=None):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                u = urlparse(self.path)
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                mock.calls.append(self.path)
                if self.headers.get("X-Auth-Token") != mock.key:
                    return self._json(400, {"message": "Your API token is invalid."})
                if mock.throttle_once:
                    mock.throttle_once = False
                    return self._json(429, {"message": "too many requests"},
                                      {"X-RequestCounter-Reset": "0"})
                parts = u.path.strip("/").split("/")
                if parts == ["v4", "competitions"]:
                    return self._json(200, {"competitions": COMPETITIONS})
                if parts == ["v4", "matches"]:          # date window across competitions
                    codes = q.get("competitions", "").split(",") if q.get("competitions") else list(mock.matches)
                    if set(codes) & mock.restricted:
                        return self._json(403, {"message": "The resource you are looking for is "
                                                           "restricted."})
                    lo, hi = q.get("dateFrom", "0000"), q.get("dateTo", "9999")
                    if (pd_days(lo, hi)) > 10:
                        return self._json(400, {"message": "dateFrom and dateTo more than 10 days apart"})
                    mock.window_calls += 1
                    ms = [m for c in codes for m in mock.matches.get(c, [])
                          if lo <= m["utcDate"][:10] <= hi]
                    return self._json(200, {"matches": ms})
                if len(parts) == 4 and parts[:2] == ["v4", "competitions"] and parts[3] == "matches":
                    code = parts[2]
                    if code in mock.restricted:
                        return self._json(403, {"message": "The resource you are looking for is "
                                                           "restricted. Please pass a valid API token "
                                                           "and check your subscription for permission."})
                    if code not in mock.matches:
                        return self._json(404, {"message": "Resource not found"})
                    ms = mock.matches[code]
                    if "season" in q:
                        ms = [m for m in ms if m["season"]["startDate"][:4] == q["season"]]
                    return self._json(200, {"matches": ms})
                return self._json(404, {"message": "Resource not found"})

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/v4"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()


class FakeCoUk:
    """Stands in for the football-data.co.uk HTTP client (get_bytes)."""

    def __init__(self, files: dict[str, bytes]):
        self.files = files
        self.requested: list[str] = []

    def get_bytes(self, url, **_):
        self.requested.append(url)
        for suffix, body in self.files.items():
            if url.endswith(suffix):
                return body
        raise RuntimeError(f"404 {url}")
