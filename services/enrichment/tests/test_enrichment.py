"""Focused smoke for analyzer + package wiring (no orchestrator
overlap)."""

from io import BytesIO

from PIL import Image
from pydantic import HttpUrl
from services.enrichment.app.cv.analyzer import ImageAnalyzer


def test_cv_inspect_dark_image() -> None:
    buf = BytesIO()
    Image.new("RGB", (64, 64), color=(5, 5, 5)).save(buf, format="JPEG")
    defects = ImageAnalyzer().inspect(
        buf.getvalue(),
        HttpUrl("https://example.com/dark.jpg"),
    )
    assert any(d.label == "very_dark_image" for d in defects)
