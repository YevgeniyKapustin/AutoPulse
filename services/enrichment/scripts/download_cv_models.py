#!/usr/bin/env python3
"""Download pretrained CV ONNX models when missing."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

_MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
_DEFAULTS = (
    (
        "plate",
        _MODELS_DIR / "plate_yolov8n.onnx",
        "https://huggingface.co/joker5914/yolov8n-license-plate/"
        "resolve/main/best.onnx",
    ),
    (
        "scene-text",
        _MODELS_DIR / "scene_text_yolo11n.onnx",
        "https://huggingface.co/RyanBours/yolo11n-text/resolve/main/model.onnx",
    ),
)


def download_model(
    *,
    dest: Path,
    url: str,
    force: bool = False,
    timeout_sec: float = 180.0,
    label: str = "model",
) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and not force:
        print(f"{label} already present: {dest}")
        return dest

    print(f"Downloading {label} from {url}")
    with httpx.Client(follow_redirects=True, timeout=timeout_sec) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            tmp = dest.with_suffix(dest.suffix + ".partial")
            with tmp.open("wb") as handle:
                for chunk in resp.iter_bytes():
                    handle.write(chunk)
            tmp.replace(dest)
    print(f"Saved {label} to {dest} ({dest.stat().st_size} bytes)")
    return dest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--only",
        choices=["plate", "scene-text", "all"],
        default="all",
    )
    args = parser.parse_args(argv)
    try:
        for label, dest, url in _DEFAULTS:
            if args.only != "all" and args.only != label:
                continue
            download_model(dest=dest, url=url, force=args.force, label=label)
    except Exception as exc:
        print(f"download failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
