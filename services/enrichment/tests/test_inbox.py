"""In-memory stand-in tests for inbox claim / complete / release."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from services.enrichment.app.repositories.messaging_store import InboxRepository


class _FakeCollection:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}
        self.indexes: list[object] = []

    async def create_index(self, *args: object, **kwargs: object) -> str:
        self.indexes.append((args, kwargs))
        return "ok"

    async def insert_one(self, doc: dict[str, Any]) -> None:
        event_id = doc["event_id"]
        if event_id in self.docs:
            from pymongo.errors import DuplicateKeyError

            raise DuplicateKeyError("dup")
        self.docs[event_id] = dict(doc)

    async def find_one_and_update(
        self,
        filt: dict[str, Any],
        update: dict[str, Any],
        *,
        return_document: object = None,
    ) -> dict[str, Any] | None:
        event_id = filt.get("event_id")
        if event_id is None or event_id not in self.docs:
            return None
        doc = self.docs[event_id]
        if not _matches(doc, filt):
            return None
        doc.update(update.get("$set", {}))
        return dict(doc)

    async def update_one(
        self,
        filt: dict[str, Any],
        update: dict[str, Any],
        *,
        upsert: bool = False,
    ) -> None:
        event_id = filt.get("event_id")
        if event_id is None:
            return
        if event_id not in self.docs:
            if not upsert:
                return
            self.docs[event_id] = {"event_id": event_id}
        if _matches(self.docs[event_id], filt):
            self.docs[event_id].update(update.get("$set", {}))

    async def delete_one(self, filt: dict[str, Any]) -> None:
        event_id = filt.get("event_id")
        if event_id is None:
            return
        doc = self.docs.get(event_id)
        if doc is not None and _matches(doc, filt):
            del self.docs[event_id]


def _matches(doc: dict[str, Any], filt: dict[str, Any]) -> bool:
    for key, expected in filt.items():
        if key == "$or":
            if not any(_matches(doc, clause) for clause in expected):
                return False
            continue
        if isinstance(expected, dict):
            if "$lt" in expected:
                value = doc.get(key)
                if value is None or not value < expected["$lt"]:
                    return False
            if "$exists" in expected:
                exists = key in doc
                if exists is not expected["$exists"]:
                    return False
            continue
        if doc.get(key) != expected:
            return False
    return True


@pytest.mark.asyncio
async def test_try_claim_then_complete_rejects_duplicates() -> None:
    inbox = InboxRepository(_FakeCollection())  # type: ignore[arg-type]
    assert await inbox.try_claim("e1") is True
    assert await inbox.try_claim("e1") is False
    await inbox.mark_completed("e1")
    assert await inbox.try_claim("e1") is False
    assert await inbox.try_claim("e1", reclaim_processing=True) is False


@pytest.mark.asyncio
async def test_release_allows_retry_claim() -> None:
    inbox = InboxRepository(_FakeCollection())  # type: ignore[arg-type]
    assert await inbox.try_claim("e1") is True
    await inbox.release_claim("e1")
    assert await inbox.try_claim("e1") is True


@pytest.mark.asyncio
async def test_redelivery_reclaims_fresh_processing() -> None:
    coll = _FakeCollection()
    inbox = InboxRepository(coll)  # type: ignore[arg-type]
    assert await inbox.try_claim("e1") is True
    assert await inbox.try_claim("e1") is False
    assert await inbox.try_claim("e1", reclaim_processing=True) is True


@pytest.mark.asyncio
async def test_stale_processing_is_reclaimed() -> None:
    coll = _FakeCollection()
    inbox = InboxRepository(coll)  # type: ignore[arg-type]
    coll.docs["e1"] = {
        "event_id": "e1",
        "status": "processing",
        "claimed_at": datetime.now(UTC) - timedelta(minutes=10),
        "completed_at": None,
    }
    assert await inbox.try_claim("e1") is True
