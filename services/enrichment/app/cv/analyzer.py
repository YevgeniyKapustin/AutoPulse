"""Synchronous image analysis for listing photos (CPU-bound)."""

from __future__ import annotations

import io
from collections.abc import Callable, Sequence

from PIL import Image, ImageFile, ImageStat, UnidentifiedImageError
from pydantic import HttpUrl

from autopulse_shared.schemas.listing import DefectInfo
from services.enrichment.app.cv.defects import (
    defect,
    image_too_large,
    image_unreadable,
)

# Process-wide Pillow policy — not analyzer instance state.
_MAX_IMAGE_PIXELS = 25_000_000
Image.MAX_IMAGE_PIXELS = _MAX_IMAGE_PIXELS
ImageFile.LOAD_TRUNCATED_IMAGES = True

ImageCheck = Callable[[Image.Image, HttpUrl], list[DefectInfo]]


class ImageAnalyzer:
    """Decode image bytes once and run pluggable image checks."""

    _RESIZE = (512, 512)
    _RGB_CHANNELS_COUNT = 3.0
    _DARK_IMAGE_BRIGHTNESS_THRESHOLD = 35.0
    _OVEREXPOSED_BRIGHTNESS_THRESHOLD = 245.0

    def __init__(
        self,
        checks: Sequence[ImageCheck] | None = None,
    ) -> None:
        self._checks = tuple(checks) if checks is not None else self._default_checks()

    @classmethod
    def _default_checks(cls) -> tuple[ImageCheck, ...]:
        return (cls._check_brightness,)

    @classmethod
    def _check_brightness(
        cls,
        image: Image.Image,
        url: HttpUrl,
    ) -> list[DefectInfo]:
        resized = image.resize(cls._RESIZE)
        brightness = sum(ImageStat.Stat(resized).mean) / cls._RGB_CHANNELS_COUNT
        found: list[DefectInfo] = []
        if brightness < cls._DARK_IMAGE_BRIGHTNESS_THRESHOLD:
            found.append(defect("very_dark_image", 0.7, url))
        if brightness > cls._OVEREXPOSED_BRIGHTNESS_THRESHOLD:
            found.append(defect("overexposed_image", 0.65, url))
        return found

    def inspect(self, data: bytes, url: HttpUrl) -> list[DefectInfo]:
        try:
            image = self._decode_rgb(data)
        except Image.DecompressionBombError:
            return [image_too_large(url, confidence=0.7)]
        except (UnidentifiedImageError, OSError, ValueError):
            return [image_unreadable(url)]

        defects: list[DefectInfo] = []
        with image:
            for check in self._checks:
                defects.extend(check(image, url))
        return defects

    def _decode_rgb(self, data: bytes) -> Image.Image:
        with Image.open(io.BytesIO(data)) as opened:
            opened.load()
            return opened.convert("RGB")
