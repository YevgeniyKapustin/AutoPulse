"""YOLOv8 letterbox preprocess and NMS postprocess (CPU/numpy)."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True, slots=True)
class LetterboxMeta:
    """Maps letterboxed detector coords back to the original image."""

    gain: float
    pad_x: float
    pad_y: float
    orig_w: int
    orig_h: int


@dataclass(frozen=True, slots=True)
class Detection:
    """Axis-aligned box in original image pixel coords + score."""

    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float


def letterbox(
    bgr: np.ndarray,
    *,
    size: int = 640,
    color: tuple[int, int, int] = (114, 114, 114),
) -> tuple[np.ndarray, LetterboxMeta]:
    """Resize with unchanged aspect ratio and pad to a square canvas."""
    orig_h, orig_w = bgr.shape[:2]
    gain = min(size / orig_h, size / orig_w)
    new_w = int(round(orig_w * gain))
    new_h = int(round(orig_h * gain))
    resized = cv2.resize(bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), color, dtype=np.uint8)
    pad_x = (size - new_w) / 2.0
    pad_y = (size - new_h) / 2.0
    left = int(round(pad_x - 0.1))
    top = int(round(pad_y - 0.1))
    canvas[top : top + new_h, left : left + new_w] = resized
    meta = LetterboxMeta(
        gain=gain,
        pad_x=pad_x,
        pad_y=pad_y,
        orig_w=orig_w,
        orig_h=orig_h,
    )
    return canvas, meta


def to_nchw_float(bgr_letterboxed: np.ndarray) -> np.ndarray:
    """BGR uint8 HWC → RGB float32 NCHW in [0, 1]."""
    rgb = cv2.cvtColor(bgr_letterboxed, cv2.COLOR_BGR2RGB)
    chw = np.transpose(rgb.astype(np.float32) / 255.0, (2, 0, 1))
    return np.expand_dims(chw, axis=0)


def decode_yolov8(
    output: np.ndarray,
    *,
    meta: LetterboxMeta,
    conf_threshold: float,
    iou_threshold: float,
) -> list[Detection]:
    """Decode YOLOv8 ONNX ``(1, 4+nc, N)`` or ``(1, N, 4+nc)``."""
    pred = np.squeeze(output, axis=0)
    if pred.ndim != 2:
        raise ValueError(f"Unexpected YOLO output shape: {output.shape}")
    # Ultralytics export is typically (4+nc, N). Rows that look like
    # boxes (width 4/5/6/84) are already transposed.
    _box_widths = {4, 5, 6, 84}
    if pred.shape[0] <= 84 and pred.shape[1] not in _box_widths:
        pred = pred.T
    if pred.shape[1] < 5:
        raise ValueError(f"Unexpected YOLO feature width: {pred.shape}")

    boxes_xywh = pred[:, :4]
    class_scores = pred[:, 4:]
    if class_scores.shape[1] == 1:
        scores = class_scores[:, 0]
    else:
        scores = class_scores.max(axis=1)

    keep = scores >= conf_threshold
    if not np.any(keep):
        return []
    boxes_xywh = boxes_xywh[keep]
    scores = scores[keep]

    # cx,cy,w,h (letterboxed pixels) → x1,y1,x2,y2
    cx, cy, w, h = boxes_xywh.T
    x1 = cx - w / 2.0
    y1 = cy - h / 2.0
    x2 = cx + w / 2.0
    y2 = cy + h / 2.0
    boxes = np.stack([x1, y1, x2, y2], axis=1)

    order = scores.argsort()[::-1]
    boxes = boxes[order]
    scores = scores[order]
    indices = _nms(boxes, scores, iou_threshold)

    detections: list[Detection] = []
    for idx in indices:
        bx1, by1, bx2, by2 = boxes[idx]
        ox1 = (bx1 - meta.pad_x) / meta.gain
        oy1 = (by1 - meta.pad_y) / meta.gain
        ox2 = (bx2 - meta.pad_x) / meta.gain
        oy2 = (by2 - meta.pad_y) / meta.gain
        ox1 = float(np.clip(ox1, 0, meta.orig_w))
        oy1 = float(np.clip(oy1, 0, meta.orig_h))
        ox2 = float(np.clip(ox2, 0, meta.orig_w))
        oy2 = float(np.clip(oy2, 0, meta.orig_h))
        if ox2 <= ox1 or oy2 <= oy1:
            continue
        detections.append(
            Detection(
                x1=ox1,
                y1=oy1,
                x2=ox2,
                y2=oy2,
                confidence=float(scores[idx]),
            )
        )
    return detections


def _nms(
    boxes: np.ndarray,
    scores: np.ndarray,
    iou_threshold: float,
) -> list[int]:
    if len(boxes) == 0:
        return []
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        rest = order[1:]
        xx1 = np.maximum(x1[i], x1[rest])
        yy1 = np.maximum(y1[i], y1[rest])
        xx2 = np.minimum(x2[i], x2[rest])
        yy2 = np.minimum(y2[i], y2[rest])
        inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
        union = areas[i] + areas[rest] - inter
        iou = np.where(union > 0, inter / union, 0.0)
        order = rest[iou <= iou_threshold]
    return keep


def to_normalized_bbox(det: Detection, *, width: int, height: int) -> list[float]:
    return [
        det.x1 / width,
        det.y1 / height,
        det.x2 / width,
        det.y2 / height,
    ]
