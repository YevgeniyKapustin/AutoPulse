"""Computer vision helpers — async fetch, Pillow off the event loop."""

from __future__ import annotations

import asyncio
import logging
from types import TracebackType
from typing import Self

import httpx
from pydantic import HttpUrl

from autopulse_shared.schemas.listing import DefectInfo, RawListing
from services.enrichment.app.cv.analyzer import ImageAnalyzer
from services.enrichment.app.cv.defects import (
    image_fetch_failed,
    image_too_large,
)

logger = logging.getLogger(__name__)

_MAX_IMAGES = 5
_FETCH_TIMEOUT_SEC = 8.0
_MAX_DOWNLOAD_BYTES = 5 * 1024 * 1024

_FetchedImage = tuple[HttpUrl, bytes]
_FetchResult = _FetchedImage | DefectInfo


class CvService:
    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        analyzer: ImageAnalyzer | None = None,
    ) -> None:
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient(
            timeout=_FETCH_TIMEOUT_SEC,
            follow_redirects=True,
        )
        self._analyzer = analyzer or ImageAnalyzer()

    async def aclose(self) -> None:
        """Close the owned HTTP client (no-op if client was injected)."""
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def detect_defects(self, listing: RawListing) -> list[DefectInfo]:
        """Download images concurrently, then analyze pixels off the loop."""
        urls = listing.image_urls[:_MAX_IMAGES]
        if not urls:
            return []

        fetched = await asyncio.gather(
            *(self._fetch_image(url) for url in urls),
        )
        defects: list[DefectInfo] = []
        payloads: list[_FetchedImage] = []
        for item in fetched:
            if isinstance(item, DefectInfo):
                defects.append(item)
            else:
                payloads.append(item)

        if payloads:
            analyzed = await asyncio.gather(
                *(
                    asyncio.to_thread(self._analyzer.inspect, data, url)
                    for url, data in payloads
                ),
            )
            for part in analyzed:
                defects.extend(part)
        return defects

    async def _fetch_image(self, url: HttpUrl) -> _FetchResult:
        url_str = str(url)
        try:
            async with self._http.stream("GET", url_str) as response:
                if response.status_code >= 400:
                    return image_fetch_failed(url)
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > _MAX_DOWNLOAD_BYTES:
                        return image_too_large(url)
                    chunks.append(chunk)
            return url, b"".join(chunks)
        except Exception as exc:
            logger.warning("CV skip %s: %s", url_str, exc)
            return image_fetch_failed(url)
