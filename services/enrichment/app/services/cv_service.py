"""Computer vision defect detection (stub). Offload to thread pool."""

from __future__ import annotations

import asyncio
import logging

from autopulse_shared.schemas.listing import DefectInfo, RawListing

logger = logging.getLogger(__name__)


class CvService:
    async def detect_defects(self, listing: RawListing) -> list[DefectInfo]:
        return await asyncio.to_thread(self._detect_sync, listing)

    def _detect_sync(self, listing: RawListing) -> list[DefectInfo]:
        # TODO(week-1): Pillow resize + YOLOv8 / OpenCV heuristics
        logger.debug("CV stub for %s images=%s", listing.external_id, len(listing.image_urls))
        return []
