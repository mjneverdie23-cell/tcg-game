"""Polymarket prices for football matches, from the public Gamma API (no key).

Polymarket lists a match as an *event* holding separate markets, usually
Yes/No ones: "Will Arsenal FC win on 2026-11-22?", "Will Arsenal FC vs.
Chelsea FC end in a draw?", "Will Chelsea FC win on 2026-11-22?", and for
some matches totals, spreads and both-teams-to-score. A share pays $1 when
its outcome happens, so its price is a probability and the decimal odds
are 1 / price. How each pick engine selection is bought:

    selection              bought as                       price paid
    home win / away win    Yes on that team's win          best ask
    draw                   Yes on the draw                 best ask
    home +0.5 (win/draw)   No on the away team's win       1 - best bid
    away +0.5 (win/draw)   No on the home team's win       1 - best bid
    over / under X.5       Over / Under (or Yes / No)      ask / 1 - bid
    BTTS yes / no          Yes / No                        ask / 1 - bid
    team +1.5              the other side of a -1.5        ask / 1 - bid

bestBid / bestAsk belong to a market's first outcome. Where a market has
no order-book quote, the midpoint (outcomePrices) is used and the quote is
marked "mid": a price you may not get.

Events are found per league: GET /sports maps a sport code (e.g. "epl") to
its series and tags, then GET /events?series_id=... lists open events.
Which code belongs to which of our leagues is configurable
(polymarket.sports); if a league has none, open soccer events are
searched. An event counts as one of our fixtures only when both teams'
names match and its kick-off is within 36 hours of ours.
"""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import pandas as pd
import requests

from footypred.data.names import _ascii, _norm, clean_team_name
from footypred.logging_utils import get_logger

log = get_logger("data.polymarket")

GAMMA = "https://gamma-api.polymarket.com"
# our competition code -> Polymarket sport codes to look for in GET /sports
SPORT_CODES = {
    "E0": ["epl"], "SP1": ["lal", "laliga", "la-liga"], "I1": ["sea", "seriea", "serie-a"],
    "D1": ["bun", "bundesliga"], "F1": ["fl1", "ligue1", "ligue-1"],
    "N1": ["ere", "eredivisie"], "P1": ["por", "primeira-liga", "liga-portugal"],
    "T1": ["tur", "super-lig", "superlig"], "NOR": ["nor", "eliteserien"],
    "CL": ["ucl", "champions-league"],
}
LINES = ("1.5", "2.5", "3.5")
MATCH_HOURS = 36                 # an event this close to our kick-off can be the fixture


class PolymarketError(RuntimeError):
    pass


def _list(v) -> list:
    """outcomes / outcomePrices arrive as JSON-encoded strings (or lists)."""
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except ValueError:
            return []
    return list(v) if isinstance(v, (list, tuple)) else []


def _price(v) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if 0.0 < x < 1.0 else None


def _ts(v) -> pd.Timestamp | None:
    if v in (None, ""):
        return None
    try:
        t = pd.Timestamp(v)
    except (ValueError, TypeError):
        return None
    if pd.isna(t):
        return None
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


@dataclass
class Quote:
    key: str          # pick engine selection key
    price: float      # what one $1 share costs now
    kind: str         # "ask": order-book price · "mid": midpoint, not guaranteed
    market: str       # the market's question
    outcome: str      # the outcome bought

    @property
    def odds(self) -> float:
        return 1.0 / self.price

    def as_price(self, fee: float = 0.0) -> dict:
        """The pick engine's price format (fee added to what you pay)."""
        p = min(self.price * (1.0 + fee), 0.999)
        return {"odds": round(1.0 / p, 4), "price": round(p, 4), "kind": self.kind,
                "market": self.market, "outcome": self.outcome, "source": "polymarket"}


# ------------------------------------------------------------------ parsing
_VS = re.compile(r"\s+(?:vs\.?|v\.?|@)\s+", re.I)


def teams_from_title(title: str) -> tuple[str, str] | None:
    """"Arsenal FC vs. Chelsea FC" -> ("Arsenal FC", "Chelsea FC")."""
    parts = _VS.split((title or "").strip(), maxsplit=1)
    if len(parts) != 2:
        return None
    a = parts[0].strip(" ?.")
    b = re.split(r"\s*[:|(]\s*|\s+-\s+", parts[1].strip())[0].strip(" ?.")
    return (a, b) if a and b else None


def kickoff_of(event: dict) -> pd.Timestamp | None:
    for m in event.get("markets") or []:
        t = _ts(m.get("gameStartTime"))
        if t is not None:
            return t
    for k in ("gameStartTime", "startTime", "endDate", "startDate"):
        t = _ts(event.get(k))
        if t is not None:
            return t
    return None


def same_team(poly: str, ours: str, aliases: dict | None = None) -> bool:
    """Strict first (cleaned official name, normalised), then a high-bar
    fuzzy match (both teams and the date must also line up)."""
    if not poly or not ours:
        return False
    a, b = _norm(clean_team_name(poly, aliases)), _norm(ours)
    if a == b or _norm(poly) == b:
        return True
    from rapidfuzz import fuzz
    return fuzz.ratio(a, b) >= 88 or (min(len(a), len(b)) >= 5 and fuzz.token_set_ratio(a, b) >= 92)


def _keys(name: str, ours: str) -> list[str]:
    """Ways a team can appear inside a market question."""
    out = {_norm(name), _norm(clean_team_name(name)), _norm(ours)}
    return [k for k in out if len(k) >= 3]


def _mentions(text: str, keys: list[str]) -> bool:
    return any(re.search(rf"\b{re.escape(k)}\b", text) for k in keys)


def _line(m: dict, raw: str) -> float | None:
    for v in (m.get("line"),):
        try:
            return float(v)
        except (TypeError, ValueError):
            pass
    hit = re.search(r"(?:o/u|over/under|over|under|total[s]?)\s*([0-9]+\.5)", raw)
    return float(hit.group(1)) if hit else None


# markets about something other than the full-time result / goals of the match
PROP = re.compile(r"\b(half|halftime|1st|2nd|first|second|corners?|cards?|bookings?|exact|"
                  r"correct|scorers?|anytime|penalt\w*|minutes?|clean sheet|margin|players?|"
                  r"shots?|offsides?|extra time|qualify|advance|tournament|season|title)\b")
DOUBLE = re.compile(r"\b(or draw|win or tie|double chance|not lose|avoid defeat)\b")


def _spread(raw: str) -> float | None:
    hit = re.search(r"\(\s*([+-]\s*[0-9]+(?:\.[0-9]+)?)\s*\)", raw)
    return float(hit.group(1).replace(" ", "")) if hit else None


def event_quotes(event: dict, home_poly: str, away_poly: str, home: str, away: str) -> dict:
    """{selection key: Quote} for one event (best price per selection)."""
    out: dict[str, Quote] = {}
    hk, ak = _keys(home_poly, home), _keys(away_poly, away)

    def add(key, buy, market, outcome):
        price, kind = buy
        if price is None:
            return
        q, old = Quote(key, price, kind, market, outcome), out.get(key)
        # prefer an order-book quote, then the cheaper price
        if old is None or (q.kind == "ask" and old.kind != "ask") or (
                q.kind == old.kind and q.price < old.price):
            out[key] = q

    for m in event.get("markets") or []:
        if m.get("closed") or m.get("active") is False or m.get("acceptingOrders") is False:
            continue
        outs = [str(o).strip() for o in _list(m.get("outcomes"))]
        if len(outs) != 2:
            continue
        mids = [_price(x) for x in _list(m.get("outcomePrices"))] + [None, None]
        bid, ask = _price(m.get("bestBid")), _price(m.get("bestAsk"))

        def buy(i, bid=bid, ask=ask, mids=mids):
            if i == 0:
                return (ask, "ask") if ask is not None else (mids[0], "mid")
            return (round(1 - bid, 6), "ask") if bid is not None else (mids[1], "mid")
        q = str(m.get("question") or event.get("title") or "")
        raw = _ascii(" ".join(str(x) for x in (m.get("groupItemTitle"), q) if x)).lower()
        text = _norm(raw)
        kind = str(m.get("sportsMarketType") or "").lower()
        if PROP.search(text):
            continue                            # first half, corners, scorers, ...
        o = [_norm(x) for x in outs]
        mh, ma = _mentions(text, hk), _mentions(text, ak)
        label = _norm(_ascii(str(m.get("groupItemTitle") or "")).lower())
        lh, la = _mentions(label, hk), _mentions(label, ak)
        if lh != la:                            # the market's own label names one team
            mh, ma = lh, la
        if set(o) == {"yes", "no"}:
            yes, no = (0, 1) if o[0] == "yes" else (1, 0)
            line, spread = _line(m, raw), _spread(raw)
            if re.search(r"\bdraw\b", text):
                add("draw", buy(yes), q, "Yes")
            elif "both teams to score" in text or re.search(r"\bbtts\b", text):
                add("btts_yes", buy(yes), q, "Yes")
                add("btts_no", buy(no), q, "No")
            elif line is not None and f"{line:.1f}" in LINES and re.search(r"\bover\b|o/u|total", raw) \
                    and not (mh or ma):
                add(f"over_{line:.1f}", buy(yes), q, "Yes")
                add(f"under_{line:.1f}", buy(no), q, "No")
            elif spread is not None and mh != ma and abs(abs(spread) - 1.5) < 1e-9:
                team, other = ("home", "away") if mh else ("away", "home")
                if spread > 0:
                    add(f"{team}_plus_1.5", buy(yes), q, "Yes")
                else:
                    add(f"{other}_plus_1.5", buy(no), q, "No")
            elif mh != ma and DOUBLE.search(text):          # "win or draw"
                add(f"{'home' if mh else 'away'}_plus_0.5", buy(yes), q, "Yes")
            elif mh != ma and (re.search(r"\bwins?\b|\bbeat\b", text) or kind == "moneyline"):
                team, other = ("home", "away") if mh else ("away", "home")
                add(f"{team}_win", buy(yes), q, "Yes")
                add(f"{other}_plus_0.5", buy(no), q, "No")
        elif set(o) == {"over", "under"}:
            line = _line(m, raw)
            if line is not None and f"{line:.1f}" in LINES:
                i_over = o.index("over")
                add(f"over_{line:.1f}", buy(i_over), q, "Over")
                add(f"under_{line:.1f}", buy(1 - i_over), q, "Under")
        else:                                   # outcomes are the two teams (spreads)
            side = [("home" if _mentions(x, hk) else "away" if _mentions(x, ak) else None) for x in o]
            spread = _spread(raw)
            if None in side or side[0] == side[1] or spread is None or abs(abs(spread) - 1.5) > 1e-9:
                continue
            # the line belongs to the team written just before it in the title
            cut = raw.find("(")
            before = _norm(raw[:cut]) if cut > 0 else ""
            named = ("home" if _mentions(before, hk) and not _mentions(before, ak) else
                     "away" if _mentions(before, ak) and not _mentions(before, hk) else side[0])
            gets = named if spread > 0 else ("away" if named == "home" else "home")
            add(f"{gets}_plus_1.5", buy(side.index(gets)), q, outs[side.index(gets)])
    return out


# ------------------------------------------------------------------- client
class PolymarketClient:
    def __init__(self, base_url: str = GAMMA, timeout: float = 8.0, cache_seconds: float = 120,
                 sport_codes: dict | None = None, fee: float = 0.0, page_size: int = 100,
                 max_pages: int = 5, search_all: bool = True, session=None):
        self.base_url = base_url.rstrip("/")
        self.timeout, self.cache_seconds, self.fee = timeout, cache_seconds, fee
        self.sport_codes = {**SPORT_CODES, **(sport_codes or {})}
        self.page_size, self.max_pages, self.search_all = page_size, max_pages, search_all
        self.session = session or requests.Session()
        self.session.headers.setdefault("Accept", "application/json")
        self._cache: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()

    @classmethod
    def from_config(cls, cfg) -> "PolymarketClient | None":
        pm = cfg.raw.get("polymarket") or {}
        if not pm.get("enabled", True):
            return None
        return cls(pm.get("base_url") or GAMMA, float(pm.get("timeout_seconds", 8)),
                   float(pm.get("cache_seconds", 120)), pm.get("sports") or {},
                   float(pm.get("fee", 0.0)), search_all=bool(pm.get("search_all_soccer", True)))

    def _get(self, path: str, ttl: float | None = None, **params):
        url = self.base_url + path
        key = url + "?" + urlencode(sorted(params.items()))
        now = time.time()
        with self._lock:
            hit = self._cache.get(key)
        if hit and hit[0] > now:
            if isinstance(hit[1], Exception):
                raise hit[1]
            return hit[1]
        try:
            r = self.session.get(url, params=params, timeout=self.timeout)
            if r.status_code == 429:
                raise PolymarketError("Polymarket is rate-limiting requests; try again in a minute")
            if r.status_code != 200:
                raise PolymarketError(f"Polymarket answered HTTP {r.status_code} for {path}")
            data = r.json()
        except (requests.RequestException, ValueError) as exc:
            err = PolymarketError(f"couldn't reach Polymarket ({self.base_url}): {exc}")
            with self._lock:                          # don't hammer it: wait a minute
                self._cache[key] = (now + min(60.0, self.cache_seconds), err)
            raise err from exc
        except PolymarketError as err:
            with self._lock:
                self._cache[key] = (now + min(60.0, self.cache_seconds), err)
            raise
        with self._lock:
            self._cache[key] = (now + (ttl or self.cache_seconds), data)
        return data

    @staticmethod
    def _rows(d) -> list:
        if isinstance(d, list):
            return d
        if isinstance(d, dict):
            for k in ("data", "events", "sports", "results"):
                if isinstance(d.get(k), list):
                    return d[k]
        return []

    def sports(self) -> list[dict]:
        return self._rows(self._get("/sports", ttl=6 * 3600))

    def league(self, competition: str) -> tuple[list[str], list[str]]:
        """(series ids, tag ids) of our competition on Polymarket."""
        codes = {c.lower() for c in self.sport_codes.get(competition, [])}
        if not codes:
            return [], []
        for s in self.sports():
            if str(s.get("sport", "")).lower() in codes:
                split = lambda v: [x.strip() for x in str(v or "").split(",") if x.strip()]  # noqa: E731
                return split(s.get("series")), split(s.get("tags"))
        return [], []

    def events(self, competition: str, lo: pd.Timestamp, hi: pd.Timestamp) -> list[dict]:
        """Open events of a competition around [lo, hi]."""
        series, tags = self.league(competition)
        window = {"closed": "false", "limit": self.page_size,
                  "end_date_min": (lo - pd.Timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "end_date_max": (hi + pd.Timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")}
        queries = [{"series_id": s} for s in series] or [{"tag_id": t} for t in reversed(tags)]
        if not queries and self.search_all:
            queries = [{"tag_slug": "soccer"}]
        found: dict = {}
        for q in queries:
            for page in range(self.max_pages):
                rows = self._rows(self._get("/events", **window, **q, offset=page * self.page_size))
                for e in rows:
                    found[e.get("id") or e.get("slug") or id(e)] = e
                if len(rows) < self.page_size:
                    break
            if found and "tag_id" in q:              # the most specific tag that has events
                break
        return list(found.values())

    def quotes_for(self, fixtures: list[dict], aliases: dict | None = None) -> tuple[dict, dict]:
        """fixtures: dicts with id, home, away, competition and utc (or date).
        Returns ({id: {"event", "url", "kickoff", "quotes": {key: Quote}}}, info)."""
        info = {"source": "polymarket", "status": "ok", "errors": [], "events": 0,
                "matched": 0, "fixtures": len(fixtures),
                "fetched_at": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")}
        by_comp: dict[str, list[dict]] = {}
        for f in fixtures:
            by_comp.setdefault(f.get("competition") or "", []).append(f)
        out: dict = {}
        for comp, fx in by_comp.items():
            kick = {id(f): _fixture_time(f) for f in fx}
            times = [t for t in kick.values() if t is not None]
            if not times:
                continue
            try:
                evs = self.events(comp, min(times), max(times))
            except PolymarketError as exc:
                info["errors"].append(str(exc))
                continue
            info["events"] += len(evs)
            parsed = [(e, teams_from_title(e.get("title") or ""), kickoff_of(e)) for e in evs]
            for f in fx:
                fk = kick[id(f)]
                for e, teams, ko in parsed:
                    if not teams or (ko is not None and fk is not None
                                     and abs((ko - fk).total_seconds()) > MATCH_HOURS * 3600):
                        continue
                    a, b = teams
                    if same_team(a, f["home"], aliases) and same_team(b, f["away"], aliases):
                        hp, ap = a, b
                    elif same_team(a, f["away"], aliases) and same_team(b, f["home"], aliases):
                        hp, ap = b, a
                    else:
                        continue
                    q = event_quotes(e, hp, ap, f["home"], f["away"])
                    if not q:
                        continue
                    hit = out.setdefault(f["id"], {
                        "event": e.get("title"), "kickoff": None if ko is None else ko.isoformat(),
                        "url": f"https://polymarket.com/event/{e['slug']}" if e.get("slug") else None,
                        "quotes": {}})
                    for key, quote in q.items():        # the main event + "more markets"
                        old = hit["quotes"].get(key)
                        if old is None or (quote.kind == "ask" and old.kind != "ask") or (
                                quote.kind == old.kind and quote.price < old.price):
                            hit["quotes"][key] = quote
                if f["id"] in out:
                    info["matched"] += 1
        if info["errors"] and not out:
            info["status"] = "error"
        return out, info

    def prices(self, quotes: dict) -> dict:
        """{key: Quote} -> the pick engine's price dicts (fee included)."""
        return {k: q.as_price(self.fee) for k, q in quotes.items()}


def _fixture_time(f: dict) -> pd.Timestamp | None:
    t = _ts(f.get("utc"))
    if t is None and f.get("date"):
        t = _ts(str(f["date"])[:10] + "T15:00:00Z")      # date only: mid-afternoon UTC
    return t
