"""Synchronous Pillow heuristics for listing images (CPU-bound)."""

from __future__ import annotations

import io
from collections.abc import Callable

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

BrightnessCheck = Callable[[float, HttpUrl], DefectInfo | None]


class ImageAnalyzer:
    """Decode image bytes and run pluggable brightness heuristics."""

    _RESIZE = (512, 512)
    _RGB_CHANNELS_COUNT = 3.0
    _DARK_IMAGE_BRIGHTNESS_THRESHOLD = 35.0
    _OVEREXPOSED_BRIGHTNESS_THRESHOLD = 245.0

    def __init__(
        self,
        brightness_checks: tuple[BrightnessCheck, ...] | None = None,
    ) -> None:
        self._brightness_checks = brightness_checks or self._default_checks()

    @classmethod
    def _default_checks(cls) -> tuple[BrightnessCheck, ...]:
        return (cls._check_darkness, cls._check_overexposure)

    @classmethod
    def _check_darkness(cls, brightness: float, url: HttpUrl) -> DefectInfo | None:
        if brightness < cls._DARK_IMAGE_BRIGHTNESS_THRESHOLD:
            return defect("very_dark_image", 0.7, url)
        return None

    @classmethod
    def _check_overexposure(
        cls,
        brightness: float,
        url: HttpUrl,
    ) -> DefectInfo | None:
        if brightness > cls._OVEREXPOSED_BRIGHTNESS_THRESHOLD:
            return defect("overexposed_image", 0.65, url)
        return None

    def inspect(self, data: bytes, url: HttpUrl) -> list[DefectInfo]:
        try:
            mean = self._mean_rgb(data)
        except Image.DecompressionBombError:
            return [image_too_large(url, confidence=0.7)]
        except (UnidentifiedImageError, OSError, ValueError):
            return [image_unreadable(url)]

        brightness = sum(mean) / self._RGB_CHANNELS_COUNT
        defects: list[DefectInfo] = []
        for check in self._brightness_checks:
            found = check(brightness, url)
            if found is not None:
                defects.append(found)
        return defects

    def _mean_rgb(self, data: bytes) -> list[float]:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            rgb = image.convert("RGB")
            resized = rgb.resize(self._RESIZE)
            return list(ImageStat.Stat(resized).mean)
