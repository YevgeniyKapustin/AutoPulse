"""MongoDB listing state repository via Motor."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from autopulse_shared.schemas.listing import EnrichedListing
from services.enrichment.app.core.exceptions import ListingNotFoundError


class ListingRepository:
    def __init__(self, collection: AsyncIOMotorCollection) -> None:
        self._collection = collection

    @classmethod
    def from_settings(
        cls,
        mongodb_uri: str,
        db_name: str,
        collection_name: str,
        client: AsyncIOMotorClient | None = None,
    ) -> tuple[ListingRepository, AsyncIOMotorClient]:
        motor_client = client or AsyncIOMotorClient(mongodb_uri)
        collection = motor_client[db_name][collection_name]
        return cls(collection), motor_client

    async def ensure_indexes(self) -> None:
        await self._collection.create_index("external_id", unique=True)

    async def upsert(self, listing: EnrichedListing) -> None:
        payload = listing.model_dump(mode="json")
        payload["updated_at"] = datetime.now(UTC).isoformat()
        await self._collection.update_one(
            {"external_id": listing.external_id},
            {"$set": payload},
            upsert=True,
        )

    async def get(self, external_id: str) -> EnrichedListing:
        doc = await self._collection.find_one({"external_id": external_id})
        if doc is None:
            raise ListingNotFoundError(external_id)
        return self._to_listing(doc)

    async def get_optional(self, external_id: str) -> EnrichedListing | None:
        doc = await self._collection.find_one({"external_id": external_id})
        if doc is None:
            return None
        return self._to_listing(doc)

    @staticmethod
    def _to_listing(doc: dict[str, Any]) -> EnrichedListing:
        data = {k: v for k, v in doc.items() if k not in {"_id", "updated_at"}}
        return EnrichedListing.model_validate(data)
