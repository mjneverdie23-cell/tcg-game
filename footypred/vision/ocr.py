"""Offline OCR via RapidOCR (ONNX models ship inside the pip wheel, so no
system install and no network). Returns positioned text boxes."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from footypred.logging_utils import get_logger

log = get_logger("vision.ocr")

_ENGINE = None


class OCRUnavailable(RuntimeError):
    pass


@dataclass
class TextBox:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    conf: float

    @property
    def yc(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def h(self) -> float:
        return max(self.y1 - self.y0, 1.0)


def _engine():
    global _ENGINE
    if _ENGINE is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as exc:
            raise OCRUnavailable("image reading needs the OCR engine: "
                                 "pip install rapidocr_onnxruntime") from exc
        _ENGINE = RapidOCR()
    return _ENGINE


def load_image(image) -> np.ndarray:
    """Path / bytes / PIL image / array -> RGB uint8 array. Small images are
    upscaled (OCR struggles with tiny phone-screenshot text)."""
    from PIL import Image, ImageOps
    if isinstance(image, np.ndarray):
        img = Image.fromarray(image)
    elif isinstance(image, (bytes, bytearray)):
        img = Image.open(io.BytesIO(image))
    elif isinstance(image, (str, Path)):
        img = Image.open(image)
    else:
        img = image
    img = ImageOps.exif_transpose(img).convert("RGB")
    if max(img.size) < 1000:
        k = 1000 / max(img.size)
        img = img.resize((int(img.width * k), int(img.height * k)), Image.LANCZOS)
    return np.asarray(img)


def read_text(image) -> tuple[list[TextBox], tuple[int, int]]:
    arr = load_image(image)
    result, _ = _engine()(arr)
    boxes = []
    for pts, text, conf in result or []:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        if str(text).strip():
            boxes.append(TextBox(str(text).strip(), min(xs), min(ys), max(xs), max(ys),
                                 float(conf)))
    log.debug("ocr: %d text boxes", len(boxes))
    return boxes, (arr.shape[1], arr.shape[0])
