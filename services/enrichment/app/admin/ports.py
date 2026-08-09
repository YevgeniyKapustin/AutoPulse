"""Admin ops ports (DIP for dashboard aggregators)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from autopulse_shared.schemas.listing import EnrichedListing, RawListing
from autopulse_shared.schemas.pricing import PricingResult
from services.enrichment.app.repositories.listing_repository import (
    ListingPageItem,
    ListingStatusFilter,
)


class ListingAdminStore(Protocol):
    async def count_listings(self) -> int: ...

    async def count_fully_enriched(self) -> int: ...

    async def count_partial(self) -> int: ...

    async def list_recent(
        self,
        *,
        limit: int = 20,
        before_updated_at: datetime | None = None,
        status: ListingStatusFilter | None = None,
    ) -> list[ListingPageItem]: ...

    async def get(self, external_id: str) -> EnrichedListing: ...

    async def get_optional(self, external_id: str) -> EnrichedListing | None: ...


class StatusCountStore(Protocol):
    async def count_by_status(self) -> dict[str, int]: ...


class QueueDepthProbe(Protocol):
    async def depths(self, queue_names: list[str]) -> dict[str, int | None]: ...


class PricerAdminClient(Protocol):
    async def overview(self) -> dict[str, object] | None: ...

    async def get_pricing(self, external_id: str) -> PricingResult | None: ...


class RawReEnricher(Protocol):
    async def enqueue_raw(
        self,
        listing: RawListing,
        request_id: str | None = None,
    ) -> str: ...
