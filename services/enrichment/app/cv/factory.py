"""Build the CV analyzer from settings (composition helper)."""

from __future__ import annotations

from pathlib import Path

from services.enrichment.app.core.config import Settings
from services.enrichment.app.cv.analyzer import ImageAnalyzer, ImageCheck
from services.enrichment.app.cv.plate_onnx import OnnxYoloPlateDetector
from services.enrichment.app.cv.watermark import OnnxTextWatermarkDetector


def build_image_analyzer(settings: Settings) -> ImageAnalyzer:
    """Compose brightness + optional watermark/plate ONNX checks."""
    checks: list[ImageCheck] = [ImageAnalyzer._check_brightness]
    if settings.cv_watermark_enabled:
        checks.append(
            OnnxTextWatermarkDetector(
                Path(settings.cv_watermark_onnx_path),
                conf_threshold=settings.cv_watermark_conf_threshold,
                iou_threshold=settings.cv_watermark_iou_threshold,
            )
        )
    if settings.cv_plate_enabled:
        checks.append(
            OnnxYoloPlateDetector(
                Path(settings.cv_plate_onnx_path),
                conf_threshold=settings.cv_plate_conf_threshold,
                iou_threshold=settings.cv_plate_iou_threshold,
            )
        )
    return ImageAnalyzer(checks=checks)


def build_cv_service(settings: Settings):
    """Wire CvService with the configured analyzer."""
    from services.enrichment.app.cv.service import CvService

    return CvService(
        analyzer=build_image_analyzer(settings),
        max_workers=settings.cv_max_workers,
    )
