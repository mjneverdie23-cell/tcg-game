"""Optional reader: Claude vision for screenshots OCR can't handle well
(logos instead of names, unusual layouts, very low resolution).

Needs `pip install anthropic` and credentials (ANTHROPIC_API_KEY or an
`ant auth login` profile). Sends the image to the Anthropic API.
"""

from __future__ import annotations

import base64
import io
import json

from footypred.logging_utils import get_logger

log = get_logger("vision.claude")

DEFAULT_MODEL = "claude-opus-5-5"

SCHEMA = {
    "type": "object",
    "properties": {
        "fixtures": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "home": {"type": "string"},
                    "away": {"type": "string"},
                    "date": {"type": ["string", "null"],
                             "description": "YYYY-MM-DD if shown or inferable, else null"},
                    "time": {"type": ["string", "null"], "description": "HH:MM if shown"},
                    "competition": {"type": ["string", "null"]},
                },
                "required": ["home", "away", "date", "time", "competition"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["fixtures"],
    "additionalProperties": False,
}

PROMPT = (
    "This image shows one or more upcoming football (soccer) matches, for example a "
    "fixture list, a betting coupon or a match card. List every match in reading order. "
    "Use the team names exactly as shown (expand obvious abbreviations only when certain). "
    "The home team is the one listed first or on the left. Ignore odds, scores of finished "
    "matches and adverts. Today is {today}; resolve relative dates such as 'Today' or "
    "'Sat 25 Oct' against it. Return an empty list if no fixtures are visible."
)


class ClaudeVisionError(RuntimeError):
    pass


def read_fixtures_claude(image_bytes: bytes, today: str, model: str = DEFAULT_MODEL,
                         client=None) -> list[dict]:
    """Returns [{home, away, date, time, competition}, ...] as printed."""
    if client is None:
        try:
            import anthropic
        except ImportError as exc:
            raise ClaudeVisionError("the Claude reader needs: pip install anthropic") from exc
        client = anthropic.Anthropic()
    media_type, data = _encode(image_bytes)
    response = client.beta.messages.create(
        model=model,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",                      # re-run declined requests server-side
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                         "data": data}},
            {"type": "text", "text": PROMPT.format(today=today)},
        ]}],
    )
    if response.stop_reason == "refusal":
        raise ClaudeVisionError("the request was declined by the model")
    if response.stop_reason == "max_tokens":
        raise ClaudeVisionError("the response was cut off (too many fixtures in one image?)")
    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise ClaudeVisionError("no answer returned")
    return json.loads(text)["fixtures"]


def _encode(image_bytes: bytes) -> tuple[str, str]:
    """PNG/JPEG/GIF/WebP pass through; anything else is converted to PNG."""
    sig = image_bytes[:12]
    if sig.startswith(b"\x89PNG"):
        mt = "image/png"
    elif sig.startswith(b"\xff\xd8"):
        mt = "image/jpeg"
    elif sig[:4] == b"RIFF" and sig[8:12] == b"WEBP":
        mt = "image/webp"
    elif sig.startswith(b"GIF8"):
        mt = "image/gif"
    else:
        from PIL import Image
        buf = io.BytesIO()
        Image.open(io.BytesIO(image_bytes)).convert("RGB").save(buf, format="PNG")
        image_bytes, mt = buf.getvalue(), "image/png"
    return mt, base64.standard_b64encode(image_bytes).decode("ascii")
