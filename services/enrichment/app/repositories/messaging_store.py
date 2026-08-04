"""Mongo inbox / outbox for enrichment messaging reliability."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Final, Literal, TypedDict, cast
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

OutboxStatus = Literal["pending", "processing", "published"]

# Stuck "processing" rows become claimable again after a pod crash/restart.
_CLAIM_STALE_AFTER: Final[timedelta] = timedelta(minutes=5)


class OutboxPendingDoc(TypedDict):
    _id: str
    routing_key: str
    body: Any
    headers: dict[str, str]
    created_at: str
    published_at: str | None
    status: OutboxStatus
    claimed_at: str | None


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
        await self._collection.create_index(
            [("status", 1), ("created_at", 1)],
            name="outbox_status_created",
        )
        await self._collection.create_index("published_at")

    async def enqueue(
        self,
        routing_key: str,
        body: bytes,
        headers: dict[str, str],
    ) -> str:
        outbox_id = str(uuid4())
        await self._collection.insert_one(
            {
                "_id": outbox_id,
                "routing_key": routing_key,
                "body": body,
                "headers": headers,
                "created_at": datetime.now(UTC).isoformat(),
                "published_at": None,
                "status": "pending",
                "claimed_at": None,
            }
        )
        return outbox_id

    async def claim_pending(self, limit: int = 50) -> list[OutboxPendingDoc]:
        """Atomically move up to ``limit`` rows to ``processing``.

        Safe for multi-replica API drain: each document is claimed by at most
        one caller via ``find_one_and_update``. Stale ``processing`` rows
        (crashed publisher) are reclaimed after ``_CLAIM_STALE_AFTER``.
        """
        claimed: list[OutboxPendingDoc] = []
        now = datetime.now(UTC)
        now_iso = now.isoformat()
        stale_before = (now - _CLAIM_STALE_AFTER).isoformat()
        claimable = {
            "$or": [
                {"status": "pending"},
                # Legacy rows written before status existed.
                {"status": {"$exists": False}, "published_at": None},
                {
                    "status": "processing",
                    "claimed_at": {"$lt": stale_before},
                },
            ]
        }
        for _ in range(limit):
            doc = await self._collection.find_one_and_update(
                claimable,
                {
                    "$set": {
                        "status": "processing",
                        "claimed_at": now_iso,
                    }
                },
                sort=[("created_at", 1)],
                return_document=ReturnDocument.AFTER,
            )
            if doc is None:
                break
            claimed.append(cast(OutboxPendingDoc, doc))
        return claimed

    async def mark_published(self, outbox_id: str) -> None:
        await self._collection.update_one(
            {"_id": outbox_id, "status": "processing"},
            {
                "$set": {
                    "status": "published",
                    "published_at": datetime.now(UTC).isoformat(),
                    "claimed_at": None,
                }
            },
        )

    async def release_claim(self, outbox_id: str) -> None:
        """Return a failed publish attempt to ``pending`` for another replica."""
        await self._collection.update_one(
            {"_id": outbox_id, "status": "processing"},
            {"$set": {"status": "pending", "claimed_at": None}},
        )
