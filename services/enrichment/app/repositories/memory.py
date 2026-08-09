"""In-memory listing repository for unit tests."""

from __future__ import annotations

from datetime import UTC, datetime

from autopulse_shared.schemas.listing import EnrichedListing
from services.enrichment.app.core.exceptions import ListingNotFoundError
from services.enrichment.app.repositories.listing_repository import (
    ListingPageItem,
    ListingStatusFilter,
)


class InMemoryListingRepository:
    def __init__(self) -> None:
        self._items: dict[str, EnrichedListing] = {}
        self._updated_at: dict[str, datetime] = {}

    async def ensure_indexes(self) -> None:
        return None

    async def upsert(self, listing: EnrichedListing) -> None:
        self._items[listing.external_id] = listing.model_copy(deep=True)
        self._updated_at[listing.external_id] = datetime.now(UTC)

    async def get(self, external_id: str) -> EnrichedListing:
        listing = await self.get_optional(external_id)
        if listing is None:
            raise ListingNotFoundError(external_id)
        return listing

    async def get_optional(self, external_id: str) -> EnrichedListing | None:
        item = self._items.get(external_id)
        if item is None:
            return None
        return item.model_copy(deep=True)

    async def count_listings(self) -> int:
        return len(self._items)

    async def count_fully_enriched(self) -> int:
        return sum(1 for item in self._items.values() if item.is_fully_enriched)

    async def count_partial(self) -> int:
        return sum(1 for item in self._items.values() if not item.is_fully_enriched)

    async def list_recent(
        self,
        *,
        limit: int = 20,
        before_updated_at: datetime | None = None,
        status: ListingStatusFilter | None = None,
    ) -> list[ListingPageItem]:
        rows = sorted(
            self._items.items(),
            key=lambda pair: self._updated_at.get(
                pair[0],
                datetime.min.replace(tzinfo=UTC),
            ),
            reverse=True,
        )
        items: list[ListingPageItem] = []
        for external_id, listing in rows:
            updated = self._updated_at.get(external_id)
            if before_updated_at is not None and (
                updated is None or updated >= before_updated_at
            ):
                continue
            if status == "enriched" and not listing.is_fully_enriched:
                continue
            if status == "partial" and listing.is_fully_enriched:
                continue
            items.append(
                ListingPageItem(
                    listing=listing.model_copy(deep=True),
                    updated_at=updated,
                )
            )
            if len(items) >= max(1, min(limit, 100)):
                break
        return items
