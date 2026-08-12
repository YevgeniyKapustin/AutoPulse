"""ONNX Runtime YOLO license-plate detector."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from pydantic import HttpUrl

from autopulse_shared.schemas.listing import DefectInfo
from services.enrichment.app.cv.defects import license_plate_detected
from services.enrichment.app.cv.yolo_onnx import OnnxYoloDetector
from services.enrichment.app.cv.yolo_preprocess import to_normalized_bbox


class OnnxYoloPlateDetector:
    """Plate boxes via a pretrained plate YOLO ONNX model."""

    def __init__(
        self,
        model_path: Path,
        *,
        conf_threshold: float = 0.35,
        iou_threshold: float = 0.45,
        input_size: int = 640,
    ) -> None:
        self._detector = OnnxYoloDetector(
            model_path,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            input_size=input_size,
            label="plate",
        )

    def __call__(self, image: Image.Image, url: HttpUrl) -> list[DefectInfo]:
        return self.inspect(image, url)

    def inspect(self, image: Image.Image, url: HttpUrl) -> list[DefectInfo]:
        width, height = image.size
        defects: list[DefectInfo] = []
        for det in self._detector.detect(image):
            bbox = to_normalized_bbox(det, width=width, height=height)
            conf = float(min(1.0, max(0.0, det.confidence)))
            defects.append(license_plate_detected(url, conf, bbox))
        return defects
