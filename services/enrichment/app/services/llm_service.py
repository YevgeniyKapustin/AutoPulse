"""LLM option extraction with circuit-breaker / retries (stub)."""

from __future__ import annotations

import logging

from autopulse_shared.schemas.listing import ListingOptions, RawListing

logger = logging.getLogger(__name__)


class LlmService:
    async def extract_options(self, listing: RawListing) -> ListingOptions:
        # TODO(week-1): call OpenAI/Claude via httpx;
        # wrap with tenacity retry + circuit breaker;
        # offload blocking SDK via asyncio.to_thread if needed.
        logger.debug("LLM extract stub for %s", listing.external_id)
        return ListingOptions(
            features=[],
            packages=[],
            tags=["stub"],
            notes="LLM not configured",
        )
