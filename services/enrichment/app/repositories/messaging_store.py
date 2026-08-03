"""Mongo inbox / outbox for enrichment messaging reliability."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from pymongo.errors import DuplicateKeyError


class InboxRepository:
    def __init__(self, collection: AsyncIOMotorCollection[dict[str, Any]]) -> None:
        self._collection = collection

    @classmethod
    def from_client(
        cls,
        client: AsyncIOMotorClient[dict[str, Any]],
        db_name: str,
        collection_name: str,
    ) -> InboxRepository:
        return cls(client[db_name][collection_name])

    async def ensure_indexes(self) -> None:
        await self._collection.create_index("event_id", unique=True)

    async def try_claim(self, event_id: str) -> bool:
        try:
            await self._collection.insert_one(
                {
                    "event_id": event_id,
                    "claimed_at": datetime.now(UTC).isoformat(),
                }
            )
            return True
        except DuplicateKeyError:
            return False


class OutboxRepository:
    def __init__(self, collection: AsyncIOMotorCollection[dict[str, Any]]) -> None:
        self._collection = collection

    @classmethod
    def from_client(
        cls,
        client: AsyncIOMotorClient[dict[str, Any]],
        db_name: str,
        collection_name: str,
    ) -> OutboxRepository:
        return cls(client[db_name][collection_name])

    async def ensure_indexes(self) -> None:
        await self._collection.create_index("published_at")

    async def enqueue(self, routing_key: str, body: bytes, headers: dict[str, object]) -> str:
        outbox_id = str(uuid4())
        await self._collection.insert_one(
            {
                "_id": outbox_id,
                "routing_key": routing_key,
                "body": body,
                "headers": headers,
                "created_at": datetime.now(UTC).isoformat(),
                "published_at": None,
            }
        )
        return outbox_id

    async def list_pending(self, limit: int = 50) -> list[dict[str, Any]]:
        cursor = (
            self._collection.find({"published_at": None})
            .sort("created_at", 1)
            .limit(limit)
        )
        return [doc async for doc in cursor]

    async def mark_published(self, outbox_id: str) -> None:
        await self._collection.update_one(
            {"_id": outbox_id},
            {"$set": {"published_at": datetime.now(UTC).isoformat()}},
        )
