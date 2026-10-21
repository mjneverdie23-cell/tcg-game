import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace

import matplotlib
import pandas as pd
import pytest

from footypred.vision.fixtures import TeamMatcher, find_time, parse_date, parse_fixtures
from footypred.vision.ocr import TextBox
from footypred.vision.reader import read_image

TODAY = pd.Timestamp("2026-10-21")
TEAMS = ["Arsenal", "Chelsea", "Manchester City", "Liverpool", "Real Madrid", "Barcelona",
         "Atletico Madrid", "Valencia", "Napoli", "AC Milan", "Mainz 05", "Aston Villa",
         "Brighton", "Nottingham Forest", "Wolverhampton"]
DATA = Path(__file__).parent / "data"
HAS_OCR = importlib.util.find_spec("rapidocr_onnxruntime") is not None


def box(text, x, y, w=200, h=24):
    return TextBox(text, x, y, x + w, y + h, 0.99)


def test_dates_and_times():
    assert parse_date("Saturday 25 October 2026", TODAY) == pd.Timestamp("2026-10-25")
    assert parse_date("Saturday25 0ctober 2026", TODAY) == pd.Timestamp("2026-10-25")  # OCR slips
    assert parse_date("Sun 26/10", TODAY) == pd.Timestamp("2026-10-26")
    assert parse_date("26.10.", TODAY) == pd.Timestamp("2026-10-26")
    assert parse_date("Tomorrow", TODAY) == pd.Timestamp("2026-10-22")
    assert parse_date("2nd Nov", TODAY) == pd.Timestamp("2026-11-02")
    assert parse_date("Jan 3", TODAY) == pd.Timestamp("2027-01-03")      # nearest occurrence
    assert parse_date("2.05 3.60 3.40", TODAY) is None                   # odds aren't dates
    assert find_time("15:00 Arsenal") == "15:00" and find_time("19h30") == "19:30"
    assert find_time("1.85 3.70") is None                                # odds aren't times


def test_team_matcher():
    m = TeamMatcher(TEAMS)
    assert m.match("Man City")[0] == "Manchester City"
    assert m.match("Atlético Madrid")[0] == "Atletico Madrid"
    assert m.match("Valencia CF")[0] == "Valencia"
    assert m.match("Arsenai")[0] == "Arsenal"                            # OCR typo
    assert m.match("Mainz 05")[0] == "Mainz 05"
    assert m.match("00 aston villa")[0] is None                          # no digit-padded fuzz
    assert m.match("Draw")[0] is None and m.match("Home")[0] is None
    found = [t for t, *_ in m.find_all("15:00 Real Madrid v Barcelona 2.10")]
    assert found == ["Real Madrid", "Barcelona"]


def test_layouts():
    m = TeamMatcher(TEAMS)
    boxes = [box("Saturday 25 October", 20, 10),
             box("15:00", 20, 60, 60), box("Arsenal vs Chelsea", 100, 60),            # one line
             box("Real Madrid", 20, 110), box("2.10 3.40 3.20", 300, 110),
             box("Barcelona", 600, 110),                                               # columns
             box("Sun 26/10", 20, 170),
             box("18:30", 20, 210, 60),
             box("Atlético", 100, 240, 90), box("Madrid", 100, 268, 70),             # wrapped
             box("1.55 4.10 6.00", 300, 282), box("Valencia CF", 100, 296),            # stacked
             box("Napoli", 100, 360), box("AC Milan", 100, 390)]
    fx, lines = parse_fixtures(boxes, m, TODAY)
    got = [(f.home, f.away, f.date, f.time) for f in fx]
    assert got == [("Arsenal", "Chelsea", "2026-10-25", "15:00"),
                   ("Real Madrid", "Barcelona", "2026-10-25", None),
                   ("Atletico Madrid", "Valencia", "2026-10-26", "18:30"),
                   ("Napoli", "AC Milan", "2026-10-26", None)]
    assert all(0 < f.confidence <= 1 for f in fx)


def _render(lines_xy, size=(900, 420)):
    from PIL import Image, ImageDraw, ImageFont
    fdir = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    font = ImageFont.truetype(str(fdir / "DejaVuSans.ttf"), 28)
    im = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(im)
    for text, xy in lines_xy:
        d.text(xy, text, font=font, fill="black")
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.skipif(not HAS_OCR, reason="rapidocr_onnxruntime not installed")
def test_ocr_reads_multiple_fixtures_from_an_image():
    img = _render([("Saturday 25 October 2026", (30, 20)), ("15:00  Arsenal vs Chelsea", (30, 100)),
                   ("17:30  Man City v Liverpool", (30, 180)), ("20:00  Aston Villa - Brighton", (30, 260))])
    res = read_image(img, TEAMS, engine="ocr", today=TODAY)
    got = [(f["home"], f["away"], f["date"], f["time"]) for f in res["fixtures"]]
    assert got == [("Arsenal", "Chelsea", "2026-10-25", "15:00"),
                   ("Manchester City", "Liverpool", "2026-10-25", "17:30"),
                   ("Aston Villa", "Brighton", "2026-10-25", "20:00")]


@pytest.mark.skipif(not HAS_OCR, reason="rapidocr_onnxruntime not installed")
def test_ocr_reads_a_browser_rendered_betting_coupon():
    """Real Chromium screenshot of a dark mobile coupon: badges, odds
    buttons, stacked teams, a team name wrapped over two lines."""
    res = read_image((DATA / "coupon_mobile.png").read_bytes(), TEAMS, engine="ocr", today=TODAY)
    got = [(f["home"], f["away"], f["date"], f["time"]) for f in res["fixtures"]]
    assert got == [("Arsenal", "Chelsea", "2026-10-25", "15:00"),
                   ("Manchester City", "Liverpool", "2026-10-25", "17:30"),
                   ("Real Madrid", "Barcelona", "2026-10-26", "16:15"),
                   ("Atletico Madrid", "Valencia", "2026-10-26", "18:30"),
                   ("Napoli", "AC Milan", "2026-10-26", "20:45")]


class _FakeClaude:
    """Stands in for anthropic.Anthropic(): records the request, returns JSON."""

    def __init__(self, payload, stop_reason="end_turn"):
        self.payload, self.stop_reason, self.kwargs = payload, stop_reason, None
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.kwargs = kw
        return SimpleNamespace(stop_reason=self.stop_reason,
                               content=[SimpleNamespace(type="text", text=json.dumps(self.payload))])


def test_claude_reader_resolves_names_and_reports_unknowns():
    fake = _FakeClaude({"fixtures": [
        {"home": "Man City", "away": "Liverpool FC", "date": "2026-10-25", "time": "17:30",
         "competition": "Premier League"},
        {"home": "Arsenal", "away": "Galatasaray", "date": None, "time": None, "competition": None}]})
    res = read_image(_render([("x", (10, 10))]), TEAMS, engine="claude", today=TODAY,
                     claude_client=fake)
    assert res["engine"] == "claude"
    assert [(f["home"], f["away"], f["date"]) for f in res["fixtures"]] == \
        [("Manchester City", "Liverpool", "2026-10-25")]
    assert res["unmatched"] == ["Arsenal vs Galatasaray"]
    kw = fake.kwargs
    assert kw["model"] == "claude-opus-5-5" and kw["fallbacks"] == "default"
    assert kw["output_config"]["format"]["type"] == "json_schema"
    assert kw["messages"][0]["content"][0]["source"]["media_type"] == "image/png"


def test_claude_reader_surfaces_refusals():
    from footypred.vision.claude_reader import ClaudeVisionError
    with pytest.raises(ClaudeVisionError):
        read_image(_render([("x", (10, 10))]), TEAMS, engine="claude", today=TODAY,
                   claude_client=_FakeClaude({"fixtures": []}, stop_reason="refusal"))
