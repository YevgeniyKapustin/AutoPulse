"""Unit tests for heuristic CV without network."""

from io import BytesIO

from PIL import Image
from services.enrichment.app.services.cv_service import CvService


def test_analyze_dark_image_flags_defect() -> None:
    cv = CvService()
    dark = Image.new("RGB", (64, 64), color=(5, 5, 5))
    buf = BytesIO()
    dark.save(buf, format="JPEG")
    defects = cv._inspect_bytes(buf.getvalue(), "https://example.com/dark.jpg")
    assert any(d.label == "very_dark_image" for d in defects)
