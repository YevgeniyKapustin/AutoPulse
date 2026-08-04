"""MongoDB listing state repository via Motor."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from autopulse_shared.schemas.listing import EnrichedListing
from services.enrichment.app.core.exceptions import ListingNotFoundError

# Repo metadata key; not part of EnrichedListing.
_UPDATED_AT = "updated_at"
_DATETIME_FIELDS = ("received_at", "enriched_at")


class ListingRepository:
    def __init__(self, collection: AsyncIOMotorCollection[dict[str, Any]]) -> None:
        self._collection = collection

    @classmethod
    def from_settings(
        cls,
        mongodb_uri: str,
        db_name: str,
        collection_name: str,
        client: AsyncIOMotorClient[dict[str, Any]] | None = None,
    ) -> tuple[ListingRepository, AsyncIOMotorClient[dict[str, Any]]]:
        motor_client = client or AsyncIOMotorClient(mongodb_uri)
        collection = motor_client[db_name][collection_name]
        return cls(collection), motor_client

    async def ensure_indexes(self) -> None:
        # Idempotent; createIndex is a no-op when the index already matches.
        # Large prod clusters should still prefer explicit migrations.
        await self._collection.create_index("external_id", unique=True)

    async def upsert(self, listing: EnrichedListing) -> None:
        """Replace listing fields for ``external_id`` (full document $set).

        Uses JSON-safe scalars for URLs/enums, but keeps datetime fields as
        native BSON dates so reads stay type-stable across upserts.
        """
        payload = self._to_document(listing)
        await self._collection.update_one(
            {"external_id": listing.external_id},
            {"$set": payload},
            upsert=True,
        )

    async def get_optional(self, external_id: str) -> EnrichedListing | None:
        doc = await self._collection.find_one({"external_id": external_id})
        if doc is None:
            return None
        return self._to_listing(doc)

    async def get(self, external_id: str) -> EnrichedListing:
        listing = await self.get_optional(external_id)
        if listing is None:
            raise ListingNotFoundError(external_id)
        return listing

    @classmethod
    def _to_document(cls, listing: EnrichedListing) -> dict[str, Any]:
        payload = listing.model_dump(mode="json")
        for key in _DATETIME_FIELDS:
            payload[key] = getattr(listing, key, None)
        payload[_UPDATED_AT] = datetime.now(UTC)
        return payload

    @staticmethod
    def _to_listing(doc: dict[str, Any]) -> EnrichedListing:
        data = {k: v for k, v in doc.items() if k not in {"_id", _UPDATED_AT}}
        return EnrichedListing.model_validate(data)
