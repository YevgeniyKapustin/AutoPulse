"""Coordinates LLM + CV enrichment and Mongo state before ack."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from autopulse_shared.schemas.events import (
    EnrichmentFailedEvent,
    ListingEnrichedEvent,
    RawListingEvent,
)
from autopulse_shared.schemas.listing import (
    EnrichedListing,
    RawListing,
)
from services.enrichment.app.core.exceptions import (
    EnrichmentError,
    EnrichmentStage,
)
from services.enrichment.app.enrichment.ports import (
    DefectDetector,
    EventSink,
    ListingStore,
    OptionsExtractor,
)

logger = logging.getLogger(__name__)


def _enrichment_fingerprint(listing: RawListing) -> tuple[object, ...]:
    """Fields that should trigger re-enrichment when they change."""
    return (
        listing.title,
        listing.description,
        listing.make,
        listing.model,
        listing.year,
        listing.asking_price,
        tuple(str(url) for url in listing.image_urls),
    )


class EnrichmentOrchestrator:
    def __init__(
        self,
        repository: ListingStore,
        llm: OptionsExtractor,
        cv: DefectDetector,
        publisher: EventSink | None = None,
    ) -> None:
        self._repository = repository
        self._llm = llm
        self._cv = cv
        self._publisher = publisher

    def set_publisher(self, publisher: EventSink) -> None:
        self._publisher = publisher

    async def aclose(self) -> None:
        """Release owned downstream resources (HTTP client pools)."""
        await self._llm.aclose()
        await self._cv.aclose()

    async def enqueue_raw(
        self,
        listing: RawListing,
        request_id: str | None = None,
    ) -> str:
        """Persist initial state and publish ``car.raw.created``."""
        state = EnrichedListing.model_validate(listing.model_dump())
        await self._repository.upsert(state)
        event = RawListingEvent(listing=listing, request_id=request_id)
        await self._require_publisher().publish_raw(event)
        logger.info(
            "Queued raw listing external_id=%s event_id=%s request_id=%s",
            listing.external_id,
            event.event_id,
            request_id,
        )
        return event.event_id

    async def enrich(
        self,
        listing: RawListing,
        *,
        event_id: str | None = None,
        request_id: str | None = None,
        retry_count: int = 0,
    ) -> EnrichedListing:
        """Run LLM/CV stages, persist aggregation, publish success."""
        existing = await self._repository.get_optional(listing.external_id)
        if (
            existing is not None
            and existing.is_fully_enriched
            and _enrichment_fingerprint(existing) == _enrichment_fingerprint(listing)
        ):
            await self._publish_enriched(
                existing,
                event_id=event_id,
                request_id=request_id,
                retry_count=retry_count,
            )
            return existing

        state = await self._prepare_state(listing, existing)
        state = await self._run_stages(listing, state)
        state = await self._finalize_aggregation(state)
        await self._publish_enriched(
            state,
            event_id=event_id,
            request_id=request_id,
            retry_count=retry_count,
        )
        return state

    async def get_state(self, external_id: str) -> EnrichedListing:
        """Return the current enriched listing document."""
        return await self._repository.get(external_id)

    async def publish_failure(
        self,
        *,
        external_id: str,
        error: str,
        stage: EnrichmentStage | str | None,
        event_id: str | None = None,
        request_id: str | None = None,
        retry_count: int = 0,
    ) -> None:
        """Best-effort publish of ``car.enrichment.failed``."""
        if self._publisher is None:
            return
        failed = EnrichmentFailedEvent(
            external_id=external_id,
            error=error,
            stage=stage,
            request_id=request_id,
            retry_count=retry_count,
        )
        if event_id is not None:
            failed = failed.model_copy(update={"event_id": event_id})
        await self._publisher.publish_failed(failed)

    async def _prepare_state(
        self,
        listing: RawListing,
        existing: EnrichedListing | None,
    ) -> EnrichedListing:
        """Build working state, resume partial progress, and persist."""
        state = EnrichedListing.model_validate(listing.model_dump())
        if existing is not None:
            same_inputs = _enrichment_fingerprint(existing) == _enrichment_fingerprint(
                listing
            )
            if same_inputs:
                state.llm_done = existing.llm_done
                state.cv_done = existing.cv_done
                state.options = existing.options
                state.defects = existing.defects
            # Changed payload: re-run stages from scratch on the new raw
            # body.
        await self._repository.upsert(state)
        return state

    async def _run_stages(
        self,
        listing: RawListing,
        state: EnrichedListing,
    ) -> EnrichedListing:
        """Run pending LLM/CV work; persist each finished stage."""
        persist_lock = asyncio.Lock()

        async def run_llm() -> None:
            if state.llm_done:
                return
            options = await self._llm.extract_options(listing)
            async with persist_lock:
                state.options = options
                state.llm_done = True
                await self._repository.upsert(state)

        async def run_cv() -> None:
            if state.cv_done:
                return
            defects = await self._cv.detect_defects(listing)
            async with persist_lock:
                state.defects = defects
                state.cv_done = True
                await self._repository.upsert(state)

        results = await asyncio.gather(run_llm(), run_cv(), return_exceptions=True)
        errors = [item for item in results if isinstance(item, BaseException)]
        if errors:
            raise errors[0]
        return state

    async def _finalize_aggregation(self, state: EnrichedListing) -> EnrichedListing:
        """Stamp enriched_at and require both stages before publish."""
        if not state.is_fully_enriched:
            raise EnrichmentError("Aggregation incomplete", stage="aggregate")
        state.enriched_at = datetime.now(UTC)
        await self._repository.upsert(state)
        return state

    async def _publish_enriched(
        self,
        listing: EnrichedListing,
        *,
        event_id: str | None,
        request_id: str | None,
        retry_count: int,
    ) -> None:
        enriched = ListingEnrichedEvent(
            listing=listing,
            request_id=request_id,
            retry_count=retry_count,
        )
        if event_id is not None:
            enriched = enriched.model_copy(update={"event_id": event_id})
        await self._require_publisher().publish_enriched(enriched)

    def _require_publisher(self) -> EventSink:
        if self._publisher is None:
            raise EnrichmentError("Event publisher is not configured", stage="publish")
        return self._publisher
