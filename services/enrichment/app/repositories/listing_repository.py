"""MongoDB listing state repository (Motor stub)."""

from __future__ import annotations

from autopulse_shared.schemas.listing import EnrichedListing


class ListingRepository:
    async def upsert(self, listing: EnrichedListing) -> None:
        # TODO(week-1): motor upsert by external_id
        _ = listing

    async def get(self, external_id: str) -> EnrichedListing:
        # TODO(week-1): fetch from Mongo; raise 404 if missing
        raise NotImplementedError(f"Listing {external_id} not in store yet")
