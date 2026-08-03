"""Coordinates LLM + CV enrichment and Mongo state before ack."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Protocol, TypeVar

from autopulse_shared.schemas.events import (
    EnrichmentFailedEvent,
    ListingEnrichedEvent,
    RawListingEvent,
)
from autopulse_shared.schemas.listing import (
    DefectInfo,
    EnrichedListing,
    ListingOptions,
    RawListing,
)
from services.enrichment.app.core.exceptions import EnrichmentError
from services.enrichment.app.services.cv_service import CvService
from services.enrichment.app.services.llm_service import LlmService

T = TypeVar("T")


class ListingStore(Protocol):
    async def upsert(self, listing: EnrichedListing) -> None: ...

    async def get(self, external_id: str) -> EnrichedListing: ...

    async def get_optional(self, external_id: str) -> EnrichedListing | None: ...


class EventSink(Protocol):
    async def publish_raw(self, event: RawListingEvent) -> None: ...

    async def publish_enriched(self, event: ListingEnrichedEvent) -> None: ...

    async def publish_failed(self, event: EnrichmentFailedEvent) -> None: ...


logger = logging.getLogger(__name__)


async def _const(value: T) -> T:
    return value


class EnrichmentOrchestrator:
    def __init__(
        self,
        repository: ListingStore,
        llm: LlmService,
        cv: CvService,
        publisher: EventSink | None = None,
    ) -> None:
        self._repository = repository
        self._llm = llm
        self._cv = cv
        self._publisher = publisher

    def set_publisher(self, publisher: EventSink) -> None:
        self._publisher = publisher

    async def enqueue_raw(
        self,
        listing: RawListing,
        request_id: str | None = None,
    ) -> str:
        event_id = str(uuid.uuid4())
        state = EnrichedListing(**listing.model_dump())
        await self._repository.upsert(state)
        event = RawListingEvent(
            event_id=event_id,
            listing=listing,
            request_id=request_id,
        )
        if self._publisher is None:
            raise EnrichmentError("Event publisher is not configured", stage="publish")
        await self._publisher.publish_raw(event)
        logger.info(
            "Queued raw listing external_id=%s event_id=%s request_id=%s",
            listing.external_id,
            event_id,
            request_id,
        )
        return event_id

    async def enrich(
        self,
        listing: RawListing,
        *,
        event_id: str | None = None,
        request_id: str | None = None,
        retry_count: int = 0,
    ) -> EnrichedListing:
        existing = await self._repository.get_optional(listing.external_id)
        if existing is not None and existing.is_fully_enriched:
            await self._publish_enriched(
                existing,
                event_id=event_id,
                request_id=request_id,
                retry_count=retry_count,
            )
            return existing

        state = EnrichedListing(**listing.model_dump())
        if existing is not None:
            state.llm_done = existing.llm_done
            state.cv_done = existing.cv_done
            state.options = existing.options
            state.defects = existing.defects
        await self._repository.upsert(state)

        options, defects = await self._run_stages(listing, state)
        state.options = options
        state.defects = defects
        state.llm_done = True
        state.cv_done = True
        state.enriched_at = datetime.now(UTC)
        await self._repository.upsert(state)

        if not state.is_fully_enriched:
            raise EnrichmentError("Aggregation incomplete", stage="aggregate")

        await self._publish_enriched(
            state,
            event_id=event_id,
            request_id=request_id,
            retry_count=retry_count,
        )
        return state

    async def _run_stages(
        self,
        listing: RawListing,
        state: EnrichedListing,
    ) -> tuple[ListingOptions, list[DefectInfo]]:
        llm_coro = (
            self._llm.extract_options(listing)
            if not state.llm_done
            else _const(state.options)
        )
        cv_coro = (
            self._cv.detect_defects(listing)
            if not state.cv_done
            else _const(state.defects)
        )
        return await asyncio.gather(llm_coro, cv_coro)

    async def publish_failure(
        self,
        *,
        external_id: str,
        error: str,
        stage: str | None,
        event_id: str | None = None,
        request_id: str | None = None,
        retry_count: int = 0,
    ) -> None:
        if self._publisher is None:
            return
        await self._publisher.publish_failed(
            EnrichmentFailedEvent(
                event_id=event_id or str(uuid.uuid4()),
                external_id=external_id,
                error=error,
                stage=stage,
                request_id=request_id,
                retry_count=retry_count,
            )
        )

    async def _publish_enriched(
        self,
        listing: EnrichedListing,
        *,
        event_id: str | None,
        request_id: str | None,
        retry_count: int,
    ) -> None:
        if self._publisher is None:
            raise EnrichmentError("Event publisher is not configured", stage="publish")
        await self._publisher.publish_enriched(
            ListingEnrichedEvent(
                event_id=event_id or str(uuid.uuid4()),
                listing=listing,
                request_id=request_id,
                retry_count=retry_count,
            )
        )

    async def get_state(self, external_id: str) -> EnrichedListing:
        return await self._repository.get(external_id)
