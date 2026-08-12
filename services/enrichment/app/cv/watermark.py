"""Watermark detection via scene-text YOLO + overlay scoring."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from pydantic import HttpUrl

from autopulse_shared.schemas.listing import DefectInfo
from services.enrichment.app.cv.defects import watermark_suspected
from services.enrichment.app.cv.yolo_onnx import OnnxYoloDetector
from services.enrichment.app.cv.yolo_preprocess import Detection, to_normalized_bbox

# Large overlays, not tiny plate-sized text labels.
_MIN_AREA_FRAC = 0.012
_MAX_AREA_FRAC = 0.55
_MIN_WIDTH_FRAC = 0.12
_CENTER_BAND = (0.2, 0.8)
_MAX_BOXES = 5


def score_text_as_watermark(
    det: Detection,
    *,
    width: int,
    height: int,
) -> float | None:
    """Watermark confidence, or None for ordinary small text."""
    area = max(0.0, det.x2 - det.x1) * max(0.0, det.y2 - det.y1)
    image_area = float(max(1, width * height))
    area_frac = area / image_area
    box_w = max(0.0, det.x2 - det.x1) / float(width)
    box_h = max(0.0, det.y2 - det.y1) / float(height)
    if area_frac < _MIN_AREA_FRAC or area_frac > _MAX_AREA_FRAC:
        return None
    if box_w < _MIN_WIDTH_FRAC and area_frac < 0.04:
        return None
    # Prefer wide banners / big center logos over small labels.
    aspect = box_w / max(box_h, 1e-6)
    cx = ((det.x1 + det.x2) / 2.0) / float(width)
    cy = ((det.y1 + det.y2) / 2.0) / float(height)
    in_center = (
        _CENTER_BAND[0] <= cx <= _CENTER_BAND[1]
        and _CENTER_BAND[0] <= cy <= _CENTER_BAND[1]
    )
    if not in_center and aspect < 2.0 and area_frac < 0.05:
        return None

    base = float(det.confidence)
    boost = 0.0
    boost += min(0.2, area_frac * 1.5)
    if in_center:
        boost += 0.08
    if aspect >= 2.5:
        boost += 0.06
    return float(min(0.95, max(0.4, base * 0.75 + boost)))


def overlay_support(
    image: Image.Image,
    det: Detection,
) -> float:
    """Boost when the crop looks semi-transparent / low-contrast."""
    rgb = np.asarray(image)
    x1 = int(max(0, det.x1))
    y1 = int(max(0, det.y1))
    x2 = int(min(rgb.shape[1], det.x2))
    y2 = int(min(rgb.shape[0], det.y2))
    if x2 <= x1 or y2 <= y1:
        return 0.0
    crop = rgb[y1:y2, x1:x2]
    if crop.size == 0:
        return 0.0
    gray = crop.mean(axis=2)
    std = float(gray.std())
    # Soft overlays sit in a mid contrast band.
    if 6.0 <= std <= 55.0:
        return 0.07
    return 0.0


class OnnxTextWatermarkDetector:
    """Scene-text YOLO detections filtered into watermark suspects."""

    def __init__(
        self,
        model_path: Path,
        *,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.5,
        input_size: int = 640,
        max_boxes: int = _MAX_BOXES,
    ) -> None:
        self._detector = OnnxYoloDetector(
            model_path,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            input_size=input_size,
            label="scene-text",
        )
        self._max_boxes = max(1, max_boxes)

    def __call__(self, image: Image.Image, url: HttpUrl) -> list[DefectInfo]:
        return self.inspect(image, url)

    def inspect(self, image: Image.Image, url: HttpUrl) -> list[DefectInfo]:
        width, height = image.size
        scored: list[tuple[float, list[float]]] = []
        for det in self._detector.detect(image):
            conf = score_text_as_watermark(det, width=width, height=height)
            if conf is None:
                continue
            conf = min(0.98, conf + overlay_support(image, det))
            bbox = to_normalized_bbox(det, width=width, height=height)
            scored.append((conf, bbox))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            watermark_suspected(url, conf, bbox)
            for conf, bbox in scored[: self._max_boxes]
        ]
