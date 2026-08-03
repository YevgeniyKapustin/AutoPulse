"""In-memory listing repository for unit tests."""

from __future__ import annotations

from autopulse_shared.schemas.listing import EnrichedListing
from services.enrichment.app.core.exceptions import ListingNotFoundError


class InMemoryListingRepository:
    def __init__(self) -> None:
        self._items: dict[str, EnrichedListing] = {}

    async def ensure_indexes(self) -> None:
        return None

    async def upsert(self, listing: EnrichedListing) -> None:
        self._items[listing.external_id] = listing.model_copy(deep=True)

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
