"""A small stand-in for Polymarket's Gamma API used by the tests.

Serves GET /sports and GET /events?series_id=... with events in the shape
the client reads: one event per match with Yes/No win and draw markets
(outcomes / outcomePrices as JSON-encoded strings, bestBid / bestAsk for
the first outcome), plus an O/U 2.5 market.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

OFFICIAL = {"Arsenal": "Arsenal FC", "Chelsea": "Chelsea FC", "Liverpool": "Liverpool FC",
            "Manchester City": "Manchester City FC", "Tottenham": "Tottenham Hotspur FC",
            "Everton": "Everton FC", "Newcastle United": "Newcastle United FC"}


def _m(question, outcomes, mid, bid, ask, **kw):
    return {"question": question, "outcomes": json.dumps(outcomes),
            "outcomePrices": json.dumps([f"{mid:.3f}", f"{1 - mid:.3f}"]),
            "bestBid": bid, "bestAsk": ask, "active": True, "closed": False,
            "acceptingOrders": True, **kw}


def event(home, away, kickoff, p_home, p_draw, p_away, p_over=0.5, spread=0.01, eid=None):
    """Prices are the midpoints; bid / ask sit `spread` either side."""
    h, a = OFFICIAL.get(home, home), OFFICIAL.get(away, away)
    day = kickoff[:10]
    quote = lambda p: dict(bid=round(p - spread, 3), ask=round(p + spread, 3))  # noqa: E731
    return {"id": eid or f"{home}-{away}-{day}", "slug": f"epl-{home[:3]}-{away[:3]}-{day}".lower(),
            "title": f"{h} vs. {a}", "endDate": kickoff, "markets": [
                _m(f"Will {h} win on {day}?", ["Yes", "No"], p_home, **quote(p_home),
                   groupItemTitle=h, sportsMarketType="moneyline", gameStartTime=kickoff),
                _m(f"Will {h} vs. {a} end in a draw?", ["Yes", "No"], p_draw, **quote(p_draw),
                   groupItemTitle=f"Draw ({h} vs. {a})", sportsMarketType="moneyline"),
                _m(f"Will {a} win on {day}?", ["Yes", "No"], p_away, **quote(p_away),
                   groupItemTitle=a, sportsMarketType="moneyline"),
                _m(f"{h} vs. {a}: O/U 2.5", ["Over", "Under"], p_over, **quote(p_over), line=2.5,
                   sportsMarketType="totals")]}


class MockGamma:
    def __init__(self, events: list[dict], sport="epl", series="10188"):
        self.events, self.sport, self.series = events, sport, series
        self.calls: list[str] = []
        mock = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                u = urlparse(self.path)
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                mock.calls.append(u.path + ("?" + u.query if u.query else ""))
                if u.path == "/sports":
                    body = [{"sport": "nba", "series": "1", "tags": "1,745"},
                            {"sport": mock.sport, "series": mock.series, "tags": "1,82,306"}]
                elif u.path == "/events":
                    rows = mock.events if q.get("series_id") == mock.series else []
                    off, lim = int(q.get("offset", 0)), int(q.get("limit", 100))
                    body = rows[off:off + lim]
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                data = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def close(self):
        self.httpd.shutdown()
