"""YOLOv8 decode / NMS unit tests (no ONNX file)."""

import numpy as np
import pytest
from services.enrichment.app.cv.yolo_preprocess import (
    LetterboxMeta,
    decode_yolov8,
    letterbox,
    to_nchw_float,
)


def test_letterbox_square_and_tensor_shape() -> None:
    bgr = np.zeros((240, 320, 3), dtype=np.uint8)
    canvas, meta = letterbox(bgr, size=640)
    assert canvas.shape == (640, 640, 3)
    assert meta.orig_w == 320
    assert meta.orig_h == 240
    tensor = to_nchw_float(canvas)
    assert tensor.shape == (1, 3, 640, 640)
    assert float(tensor.max()) <= 1.0


def test_decode_yolov8_channels_first_single_class() -> None:
    # One high-confidence plate + one below threshold, shape (1, 5, N).
    pred = np.zeros((1, 5, 2), dtype=np.float32)
    # cx,cy,w,h in letterbox pixels, score
    pred[0, :, 0] = [320, 320, 100, 40, 0.9]
    pred[0, :, 1] = [100, 100, 50, 20, 0.05]
    meta = LetterboxMeta(gain=1.0, pad_x=0.0, pad_y=0.0, orig_w=640, orig_h=640)
    dets = decode_yolov8(
        pred,
        meta=meta,
        conf_threshold=0.35,
        iou_threshold=0.45,
    )
    assert len(dets) == 1
    assert dets[0].confidence == pytest.approx(0.9)
    assert dets[0].x2 > dets[0].x1
    assert dets[0].y2 > dets[0].y1


def test_nms_suppresses_overlap() -> None:
    pred = np.zeros((1, 5, 2), dtype=np.float32)
    pred[0, :, 0] = [320, 320, 120, 50, 0.95]
    pred[0, :, 1] = [325, 322, 118, 48, 0.9]
    meta = LetterboxMeta(gain=1.0, pad_x=0.0, pad_y=0.0, orig_w=640, orig_h=640)
    dets = decode_yolov8(
        pred,
        meta=meta,
        conf_threshold=0.35,
        iou_threshold=0.45,
    )
    assert len(dets) == 1
    assert dets[0].confidence >= 0.94
