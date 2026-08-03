"""Coordinates LLM + CV enrichment and Mongo state before ack."""

from __future__ import annotations

import logging
import uuid

from autopulse_shared.schemas.listing import EnrichedListing, RawListing
from services.enrichment.app.repositories.listing_repository import ListingRepository
from services.enrichment.app.services.cv_service import CvService
from services.enrichment.app.services.llm_service import LlmService

logger = logging.getLogger(__name__)


class EnrichmentOrchestrator:
    def __init__(
        self,
        repository: ListingRepository,
        llm: LlmService,
        cv: CvService,
    ) -> None:
        self._repository = repository
        self._llm = llm
        self._cv = cv

    async def enqueue_raw(
        self,
        listing: RawListing,
        request_id: str | None = None,
    ) -> str:
        """Persist initial state and publish car.raw.created (stub)."""
        event_id = str(uuid.uuid4())
        state = EnrichedListing(**listing.model_dump())
        await self._repository.upsert(state)
        logger.info(
            "Queued raw listing external_id=%s event_id=%s request_id=%s",
            listing.external_id,
            event_id,
            request_id,
        )
        # TODO(week-1): publish RawListingEvent to RabbitMQ
        return event_id

    async def enrich(self, listing: RawListing) -> EnrichedListing:
        """Run LLM + CV in parallel aggregation; persist; caller acks broker."""
        state = EnrichedListing(**listing.model_dump())
        await self._repository.upsert(state)

        options = await self._llm.extract_options(listing)
        state.options = options
        state.llm_done = True
        await self._repository.upsert(state)

        defects = await self._cv.detect_defects(listing)
        state.defects = defects
        state.cv_done = True
        await self._repository.upsert(state)

        if not state.is_fully_enriched:
            raise RuntimeError("Aggregation incomplete")
        return state

    async def get_state(self, external_id: str) -> EnrichedListing:
        return await self._repository.get(external_id)
