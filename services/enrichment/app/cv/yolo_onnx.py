"""Shared ONNX Runtime YOLO detector (lazy session load)."""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from services.enrichment.app.cv.yolo_preprocess import (
    Detection,
    decode_yolov8,
    letterbox,
    to_nchw_float,
)

logger = logging.getLogger(__name__)


class OnnxYoloDetector:
    """Lazy ONNX YOLO session; returns [] when weights are missing."""

    def __init__(
        self,
        model_path: Path,
        *,
        conf_threshold: float = 0.35,
        iou_threshold: float = 0.45,
        input_size: int = 640,
        label: str = "yolo",
    ) -> None:
        self._model_path = Path(model_path)
        self._conf_threshold = conf_threshold
        self._iou_threshold = iou_threshold
        self._input_size = input_size
        self._label = label
        self._session: object | None = None
        self._input_name: str | None = None
        self._load_attempted = False
        self._unavailable_logged = False

    def detect(self, image: Image.Image) -> list[Detection]:
        session = self._ensure_session()
        if session is None or self._input_name is None:
            return []

        rgb = np.asarray(image)
        if rgb.ndim != 3 or rgb.shape[2] != 3:
            return []
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        canvas, meta = letterbox(bgr, size=self._input_size)
        tensor = to_nchw_float(canvas)
        try:
            outputs = session.run(  # type: ignore[attr-defined]
                None,
                {self._input_name: tensor},
            )
        except Exception as exc:
            logger.warning("%s ONNX inference failed: %s", self._label, exc)
            return []
        if not outputs:
            return []
        try:
            return decode_yolov8(
                np.asarray(outputs[0]),
                meta=meta,
                conf_threshold=self._conf_threshold,
                iou_threshold=self._iou_threshold,
            )
        except ValueError as exc:
            logger.warning("%s ONNX decode failed: %s", self._label, exc)
            return []

    def _ensure_session(self) -> object | None:
        if self._session is not None:
            return self._session
        if self._load_attempted:
            return None
        self._load_attempted = True
        if not self._model_path.is_file():
            if not self._unavailable_logged:
                logger.warning(
                    "%s ONNX model missing at %s; skipped",
                    self._label,
                    self._model_path,
                )
                self._unavailable_logged = True
            return None
        try:
            import onnxruntime as ort

            session = ort.InferenceSession(
                str(self._model_path),
                providers=["CPUExecutionProvider"],
            )
            self._session = session
            self._input_name = session.get_inputs()[0].name
            logger.info("Loaded %s ONNX from %s", self._label, self._model_path)
            return session
        except Exception as exc:
            logger.warning("Failed to load %s ONNX: %s", self._label, exc)
            return None
