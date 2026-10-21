"""Image -> list of fixtures, via offline OCR (default) or Claude vision."""

from __future__ import annotations

import importlib.util

import pandas as pd

from footypred.data.names import NameResolver, TeamNameError
from footypred.logging_utils import get_logger
from footypred.vision.fixtures import TeamMatcher, parse_fixtures

log = get_logger("vision.reader")

ENGINES = ("auto", "ocr", "claude")


def _claude_installed() -> bool:
    return importlib.util.find_spec("anthropic") is not None


def read_image(image_bytes: bytes, teams: list[str], aliases: dict | None = None,
               engine: str = "auto", today=None, claude_model: str | None = None,
               claude_client=None) -> dict:
    """Returns {engine, fixtures: [...], lines: [...], warnings: [...], unmatched: [...]}."""
    if engine not in ENGINES:
        raise ValueError(f"engine must be one of {ENGINES}")
    today = pd.Timestamp(today or pd.Timestamp.today()).normalize()
    warnings: list[str] = []
    if engine in ("auto", "ocr"):
        from footypred.vision.ocr import OCRUnavailable, read_text
        try:
            boxes, _ = read_text(image_bytes)
            fixtures, lines = parse_fixtures(boxes, TeamMatcher(teams, aliases), today)
            if fixtures or engine == "ocr" or not _claude_installed():
                if not fixtures:
                    warnings.append("no fixtures recognised: check that team names are "
                                    "readable and are teams in the database")
                return {"engine": "ocr", "fixtures": [f.to_dict() for f in fixtures],
                        "lines": lines, "warnings": warnings, "unmatched": []}
            warnings.append("OCR found no fixtures; trying Claude vision")
        except OCRUnavailable as exc:
            if engine == "ocr" or not _claude_installed():
                raise
            warnings.append(str(exc))
    return _read_with_claude(image_bytes, teams, aliases, today, claude_model, claude_client,
                             warnings)


def _read_with_claude(image_bytes, teams, aliases, today, model, client, warnings) -> dict:
    from footypred.vision.claude_reader import DEFAULT_MODEL, read_fixtures_claude
    raw = read_fixtures_claude(image_bytes, str(today.date()), model or DEFAULT_MODEL, client)
    resolver = NameResolver(teams, aliases)
    fixtures, unmatched, seen = [], [], set()
    for r in raw:
        try:
            home, away = resolver.resolve(r["home"]), resolver.resolve(r["away"])
        except TeamNameError:
            unmatched.append(f"{r['home']} vs {r['away']}")
            continue
        if home == away or (home, away, r.get("date")) in seen:
            continue
        seen.add((home, away, r.get("date")))
        fixtures.append({"home": home, "away": away, "confidence": 0.95, "layout": "claude",
                         "date": r.get("date"), "time": r.get("time"),
                         "source": f"{r['home']} vs {r['away']}"
                                   + (f" ({r['competition']})" if r.get("competition") else "")})
    if unmatched:
        warnings.append(f"{len(unmatched)} fixture(s) had teams not in the database")
    return {"engine": "claude", "fixtures": fixtures, "lines": [], "warnings": warnings,
            "unmatched": unmatched}
