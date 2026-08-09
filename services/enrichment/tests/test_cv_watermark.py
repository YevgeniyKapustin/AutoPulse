"""Watermark scoring unit tests (no ONNX file required)."""

from services.enrichment.app.cv.watermark import score_text_as_watermark
from services.enrichment.app.cv.yolo_preprocess import Detection


def test_large_center_text_scores_as_watermark() -> None:
    det = Detection(x1=80, y1=180, x2=560, y2=280, confidence=0.8)
    score = score_text_as_watermark(det, width=640, height=480)
    assert score is not None
    assert score >= 0.4


def test_tiny_corner_label_is_ignored() -> None:
    det = Detection(x1=10, y1=10, x2=40, y2=22, confidence=0.9)
    assert score_text_as_watermark(det, width=640, height=480) is None


def test_fake_watermark_check_emits_bbox() -> None:
    from io import BytesIO

    from PIL import Image
    from pydantic import HttpUrl
    from services.enrichment.app.cv.analyzer import ImageAnalyzer
    from services.enrichment.app.cv.defects import watermark_suspected

    def fake_wm(image: Image.Image, url: HttpUrl):
        return [watermark_suspected(url, 0.7, [0.1, 0.4, 0.9, 0.6])]

    buf = BytesIO()
    Image.new("RGB", (64, 64), color=(128, 128, 128)).save(buf, format="JPEG")
    defects = ImageAnalyzer(checks=(fake_wm,)).inspect(
        buf.getvalue(),
        HttpUrl("https://example.com/car.jpg"),
    )
    assert defects[0].label == "watermark_suspected"
    assert defects[0].bbox == [0.1, 0.4, 0.9, 0.6]
