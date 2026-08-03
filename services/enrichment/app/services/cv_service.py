"""Computer vision helpers — Pillow off the event loop."""

from __future__ import annotations

import asyncio
import io
import logging
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageStat

from autopulse_shared.schemas.listing import DefectInfo, RawListing

logger = logging.getLogger(__name__)

_MAX_IMAGES = 5
_FETCH_TIMEOUT_SEC = 8.0
_RESIZE = (512, 512)


class CvService:
    async def detect_defects(self, listing: RawListing) -> list[DefectInfo]:
        return await asyncio.to_thread(self._detect_sync, listing)

    def _detect_sync(self, listing: RawListing) -> list[DefectInfo]:
        defects: list[DefectInfo] = []
        urls = listing.image_urls[:_MAX_IMAGES]
        if not urls:
            return defects

        with httpx.Client(timeout=_FETCH_TIMEOUT_SEC, follow_redirects=True) as client:
            for url in urls:
                url_str = str(url)
                try:
                    defects.extend(self._inspect_url(client, url_str))
                except Exception as exc:
                    logger.warning("CV skip %s: %s", url_str, exc)
        return defects

    def _inspect_url(self, client: httpx.Client, url: str) -> list[DefectInfo]:
        if urlparse(url).scheme not in {"http", "https"}:
            return []
        response = client.get(url)
        if response.status_code >= 400:
            return [
                DefectInfo(
                    label="image_fetch_failed",
                    confidence=0.5,
                    image_url=url,
                )
            ]
        return self._inspect_bytes(response.content, url)

    def _inspect_bytes(self, data: bytes, url: str) -> list[DefectInfo]:
        with Image.open(io.BytesIO(data)) as image:
            rgb = image.convert("RGB")
            resized = rgb.resize(_RESIZE)
            mean = ImageStat.Stat(resized).mean
            brightness = sum(mean) / 3.0
            defects: list[DefectInfo] = []
            if brightness < 35:
                defects.append(
                    DefectInfo(
                        label="very_dark_image",
                        confidence=0.7,
                        image_url=url,
                    )
                )
            if brightness > 245:
                defects.append(
                    DefectInfo(
                        label="overexposed_image",
                        confidence=0.65,
                        image_url=url,
                    )
                )
            return defects
