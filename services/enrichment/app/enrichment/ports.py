"""Ports for enrichment use-cases and stage adapters (DIP / ISP)."""

from __future__ import annotations

from typing import Protocol

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
from services.enrichment.app.core.exceptions import EnrichmentStage


class ListingStore(Protocol):
    async def upsert(self, listing: EnrichedListing) -> None: ...

    async def get(self, external_id: str) -> EnrichedListing: ...

    async def get_optional(self, external_id: str) -> EnrichedListing | None: ...


class EventSink(Protocol):
    async def publish_raw(self, event: RawListingEvent) -> None: ...

    async def publish_enriched(self, event: ListingEnrichedEvent) -> None: ...

    async def publish_failed(self, event: EnrichmentFailedEvent) -> None: ...


class OptionsExtractor(Protocol):
    async def extract_options(self, listing: RawListing) -> ListingOptions: ...

    async def aclose(self) -> None: ...


class DefectDetector(Protocol):
    async def detect_defects(self, listing: RawListing) -> list[DefectInfo]: ...

    async def aclose(self) -> None: ...


class ListingEnricher(Protocol):
    async def enrich(
        self,
        listing: RawListing,
        *,
        event_id: str | None = None,
        request_id: str | None = None,
        retry_count: int = 0,
    ) -> EnrichedListing: ...

    async def publish_failure(
        self,
        *,
        external_id: str,
        error: str,
        stage: EnrichmentStage | str | None,
        event_id: str | None = None,
        request_id: str | None = None,
        retry_count: int = 0,
    ) -> None: ...


class RawListingIngestor(Protocol):
    async def enqueue_raw(
        self,
        listing: RawListing,
        request_id: str | None = None,
    ) -> str: ...


class ListingReader(Protocol):
    async def get_state(self, external_id: str) -> EnrichedListing: ...


class InboxClaimer(Protocol):
    async def try_claim(
        self,
        event_id: str,
        *,
        reclaim_processing: bool = False,
    ) -> bool: ...

    async def mark_completed(self, event_id: str) -> None: ...

    async def release_claim(self, event_id: str) -> None: ...
