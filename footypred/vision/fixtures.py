"""Turn OCR text boxes into fixtures (home vs away), one image -> many.

Handles the usual screenshot layouts:
  * one line per match:        "Arsenal vs Chelsea", "Arsenal - Chelsea 19:30"
  * two columns on one row:    "Arsenal    2.10  3.40  3.25    Chelsea"
  * stacked (betting apps):    "Arsenal" on one line, "Chelsea" right below
plus date headers ("Sat 25 Oct", "25/10/2026", "Today") and kick-off times.

Team names are matched against the database (with aliases), longest
phrase first, exact or near-exact only, so stray words don't become teams.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

from footypred.data.names import BUILTIN_ALIASES
from footypred.vision.ocr import TextBox

STOPWORDS = {"home", "away", "draw", "over", "under", "vs", "v", "x", "live", "today",
             "tomorrow", "ft", "ht", "odds", "more", "bet", "win", "yes", "no", "btts",
             "goals", "total", "match", "result", "league", "cup", "the", "and", "fc", "cf"}
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


_AFFIX = re.compile(r"^(fc|cf|afc|sc|sv|fk|ac|as|ssc|us|cd|ud|rc|sl|ca|club)\s+|\s+(fc|cf|afc|sc|sv|fk)$")


class TeamMatcher:
    def __init__(self, teams: list[str], aliases: dict[str, str] | None = None):
        known = set(teams)
        self.keys: dict[str, str] = {}
        for t in teams:
            self._add(t, t)
        for alias, canon in {**BUILTIN_ALIASES, **(aliases or {})}.items():
            if canon in known:
                self._add(alias, canon)
        self._choices = list(self.keys)
        # spaceless forms for text OCR glued together ("o0Arsenalvs Chelsea")
        self._compact = {k.replace(" ", ""): v for k, v in self.keys.items()
                         if len(k.replace(" ", "")) >= 6}

    def _add(self, name: str, canon: str) -> None:
        n = _norm(name)
        if n:
            self.keys.setdefault(n, canon)
            stripped = _AFFIX.sub("", n).strip()
            if stripped and stripped != n:
                self.keys.setdefault(stripped, canon)

    def match(self, text: str) -> tuple[str | None, float]:
        n = _norm(text)
        if len(n) < 3 or n in STOPWORDS or n.replace(" ", "").isdigit():
            return None, 0.0
        if n in self.keys:
            return self.keys[n], 100.0
        n2 = _AFFIX.sub("", n).strip()
        if n2 in self.keys:
            return self.keys[n2], 99.0
        if any(tok.isdigit() for tok in n.split()):
            return None, 0.0                  # numbers (times, odds) only via exact names
        if len(n) <= 5:                       # short words must match exactly
            return None, 0.0
        best = process.extractOne(n, self._choices, scorer=fuzz.ratio, score_cutoff=85)
        return (self.keys[best[0]], float(best[1])) if best else (None, 0.0)

    def find_all(self, text: str) -> list[tuple[str, float, int, int]]:
        """Teams inside free text, longest phrases first, non-overlapping.
        Returns (team, score, word_position, n_words) in reading order."""
        words = _norm(text).split()
        used = [False] * len(words)
        found = []
        for n in (5, 4, 3, 2, 1):
            for i in range(0, len(words) - n + 1):
                if any(used[i:i + n]):
                    continue
                team, score = self.match(" ".join(words[i:i + n]))
                if team:
                    found.append((team, score, i, n))
                    for k in range(i, i + n):
                        used[k] = True
        return sorted(found, key=lambda t: t[2])


    def find_glued(self, text: str) -> list[tuple[str, float, float]]:
        """Teams inside text with missing spaces. Returns (team, score,
        relative position 0..1), longest names first, non-overlapping."""
        compact = _norm(text).replace(" ", "")
        if len(compact) < 8:
            return []
        hits = []
        for key, canon in self._compact.items():
            start = compact.find(key)
            while start != -1:
                hits.append((start, start + len(key), canon))
                start = compact.find(key, start + 1)
        chosen = []
        for h in sorted(hits, key=lambda h: (-(h[1] - h[0]), h[0])):
            if all(h[1] <= c[0] or h[0] >= c[1] for c in chosen):
                chosen.append(h)
        return [(c[2], 90.0, (c[0] + c[1]) / 2 / len(compact)) for c in sorted(chosen)]


# ------------------------------------------------------------------ dates
_DATE_PATTERNS = [
    (re.compile(r"\b(20\d\d)-(\d{1,2})-(\d{1,2})\b"), "ymd"),
    (re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](20\d\d|\d\d)\b"), "dmy"),
    (re.compile(r"\b(\d{1,2})/(\d{1,2})\b(?!/\d)"), "dm"),
    (re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(?!\d)"), "dm"),          # 26.10.  (odds have no trailing dot)
    (re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3})[a-z]*\.?(?:\s+(20\d\d))?\b", re.I), "d_mon"),
    (re.compile(r"\b([a-z]{3})[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(20\d\d))?\b", re.I), "mon_d"),
]
_TIME = re.compile(r"(?<!\d)([01]?\d|2[0-3])(?::|h)([0-5]\d)(?!\d)")   # 19:30 / 19h30 (not odds like 1.35)


def _clean_ocr(t: str) -> str:
    """Undo common OCR slips in date text: glued tokens, 0 read for O."""
    t = re.sub(r"(?<=\d)(?=[a-z])|(?<=[a-z])(?=\d)", " ", t.lower())
    t = re.sub(r"(\d) (st|nd|rd|th)\b", r"\1\2", t)      # keep ordinals: 25th
    t = re.sub(r"\b0(?=ct\b|ct[a-z])", "o", t)          # 0ct / 0ctober
    return re.sub(r"\s+0\s+(?=ct)", " o", t)


def _nearest_year(month: int, day: int, today: pd.Timestamp) -> pd.Timestamp | None:
    best = None
    for y in (today.year - 1, today.year, today.year + 1):
        try:
            d = pd.Timestamp(year=y, month=month, day=day)
        except ValueError:
            continue
        if best is None or abs((d - today).days) < abs((best - today).days):
            best = d
    return best


def parse_date(text: str, today: pd.Timestamp | None = None) -> pd.Timestamp | None:
    today = (today or pd.Timestamp.today()).normalize()
    t = _clean_ocr(text)
    if re.search(r"\btoday\b", t):
        return today
    if re.search(r"\btomorrow\b", t):
        return today + pd.Timedelta(days=1)
    for rx, kind in _DATE_PATTERNS:
        for m in rx.finditer(t):
            try:
                if kind == "ymd":
                    return pd.Timestamp(int(m[1]), int(m[2]), int(m[3]))
                if kind == "dmy":
                    y = int(m[3]); y = y + 2000 if y < 100 else y
                    return pd.Timestamp(y, int(m[2]), int(m[1]))
                if kind == "dm":
                    d, mo = int(m[1]), int(m[2])
                    if 1 <= mo <= 12 and 1 <= d <= 31:
                        return _nearest_year(mo, d, today)
                if kind in ("d_mon", "mon_d"):
                    d, mon = (m[1], m[2]) if kind == "d_mon" else (m[2], m[1])
                    mo = MONTHS.get(mon[:3].lower())
                    if mo:
                        if m[3]:
                            return pd.Timestamp(int(m[3]), mo, int(d))
                        return _nearest_year(mo, int(d), today)
            except (ValueError, TypeError):
                continue
    return None


def find_time(text: str) -> str | None:
    # OCR reads 0 as o/O inside times: "15:o0" -> "15:00"
    text = re.sub(r"(?<!\d)(\d{1,2})([:h])([0-9oO]{2})",
                  lambda m: m[1] + m[2] + m[3].replace("o", "0").replace("O", "0"), text)
    m = _TIME.search(text)
    return f"{int(m[1]):02d}:{m[2]}" if m else None


# ------------------------------------------------------------------ layout
@dataclass
class Line:
    boxes: list[TextBox]
    y: float
    h: float

    @property
    def text(self) -> str:
        return "  ".join(b.text for b in self.boxes)

    @property
    def x0(self) -> float:
        return min(b.x0 for b in self.boxes)


def group_lines(boxes: list[TextBox]) -> list[Line]:
    lines: list[Line] = []
    for b in sorted(boxes, key=lambda b: b.yc):
        if lines and abs(b.yc - lines[-1].y) <= 0.55 * max(b.h, lines[-1].h):
            ln = lines[-1]
            ln.boxes.append(b)
            ln.y = float(np.mean([x.yc for x in ln.boxes]))
            ln.h = float(np.median([x.h for x in ln.boxes]))
        else:
            lines.append(Line([b], b.yc, b.h))
    for ln in lines:
        ln.boxes.sort(key=lambda b: b.x0)
    return lines


@dataclass
class Mention:
    team: str
    score: float
    line: int
    x: float


@dataclass
class DetectedFixture:
    home: str
    away: str
    confidence: float
    layout: str
    date: str | None = None
    time: str | None = None
    source: str = ""
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"home": self.home, "away": self.away, "confidence": round(self.confidence, 2),
                "layout": self.layout, "date": self.date, "time": self.time,
                "source": self.source}


def parse_fixtures(boxes: list[TextBox], matcher: TeamMatcher,
                   today: pd.Timestamp | None = None) -> tuple[list[DetectedFixture], list[str]]:
    lines = group_lines(boxes)
    texts = [ln.text for ln in lines]
    mentions: list[Mention] = []
    consumed: set[int] = set()
    for li, ln in enumerate(lines):
        for b in ln.boxes:
            if id(b) in consumed:
                continue
            words = max(len(_norm(b.text).split()), 1)
            found = matcher.find_all(b.text)
            # a team name wrapped onto the next line ("Atlético" / "Madrid")
            below = (_box_below(b, lines, li, consumed)
                     if not found and re.search(r"[a-z]{3}", _norm(b.text)) else None)
            if below is not None:
                joined = matcher.find_all(b.text + " " + below.text)
                if any(pos < words < pos + n for _, _, pos, n in joined):
                    found = [f for f in joined if f[2] < words]
                    consumed.add(id(below))
            glued = matcher.find_glued(b.text) if len(found) < 2 else []
            if len(glued) > len(found):
                for team, score, frac in glued:
                    mentions.append(Mention(team, score, li, b.x0 + (b.x1 - b.x0) * frac))
                continue
            for team, score, pos, _ in found:
                x = b.x0 + (b.x1 - b.x0) * (min(pos, words - 1) + 0.5) / words
                mentions.append(Mention(team, score, li, x))

    # date context: the latest date seen on or above each line
    line_date, line_time = [], []
    current = None
    for t in texts:
        d = parse_date(t, today)
        if d is not None:
            current = d
        line_date.append(current)
        line_time.append(find_time(t))

    by_line: dict[int, list[Mention]] = {}
    for m in mentions:
        by_line.setdefault(m.line, []).append(m)
    fixtures: list[DetectedFixture] = []
    singles: list[Mention] = []
    for li in sorted(by_line):
        ms = sorted(by_line[li], key=lambda m: m.x)
        while len(ms) >= 2:
            a, b = ms.pop(0), ms.pop(0)
            if a.team == b.team:
                ms.insert(0, b)
                continue
            fixtures.append(_fixture(a, b, "same line", 1.0, li, li, texts, line_date, line_time,
                                     by_line))
        singles.extend(ms)

    # stacked layout: consecutive single-team lines close together
    med_h = float(np.median([ln.h for ln in lines])) if lines else 10.0
    i = 0
    while i < len(singles) - 1:
        a, b = singles[i], singles[i + 1]
        gap = lines[b.line].y - lines[a.line].y
        between = [x for x in range(a.line + 1, b.line) if x in by_line]
        aligned = abs(lines[a.line].x0 - lines[b.line].x0) <= 6 * med_h
        if a.team != b.team and not between and gap <= 4.5 * med_h and aligned:
            fixtures.append(_fixture(a, b, "stacked", 0.9, a.line, b.line, texts, line_date,
                                     line_time, by_line))
            i += 2
        else:
            i += 1

    seen, out = set(), []
    for f in sorted(fixtures, key=lambda f: f.extra["line"]):
        key = (f.home, f.away, f.date)
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out, texts


def _box_below(b: TextBox, lines: list[Line], li: int, consumed: set) -> TextBox | None:
    """The box directly under `b` on the next line (same left edge)."""
    if li + 1 >= len(lines):
        return None
    for c in lines[li + 1].boxes:
        if (id(c) not in consumed and abs(c.x0 - b.x0) <= 1.2 * b.h
                and 0 < c.yc - b.yc <= 2.2 * max(b.h, c.h)):
            return c
    return None


def _fixture(a, b, layout, factor, la, lb, texts, line_date, line_time,
             team_lines) -> DetectedFixture:
    d = line_date[lb]
    # kick-off time: on the team lines, between them (stacked cards), or on a
    # bare time line just above (never borrowed from another fixture's line)
    t = next((line_time[x] for x in range(la, lb + 1) if line_time[x]), None)
    if t is None and la > 0 and (la - 1) not in team_lines:
        t = line_time[la - 1]
    src = texts[la] if la == lb else f"{texts[la]} / {texts[lb]}"
    return DetectedFixture(a.team, b.team, factor * min(a.score, b.score) / 100, layout,
                           None if d is None else str(d.date()), t, src, {"line": la})
