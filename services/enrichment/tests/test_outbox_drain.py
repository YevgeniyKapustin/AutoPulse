"""Unit tests for outbox claim / release during drain."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest

from services.enrichment.app.messaging.outbox_sink import OutboxEventSink
from services.enrichment.app.messaging.routes import PublishRoutes
from services.enrichment.app.repositories.messaging_store import OutboxPendingDoc


class _MemoryOutbox:
    """In-memory outbox with claim semantics (stand-in for Mongo)."""

    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    async def enqueue(
        self,
        routing_key: str,
        body: bytes,
        headers: dict[str, str],
    ) -> str:
        outbox_id = f"ob-{len(self.docs) + 1}"
        self.docs[outbox_id] = {
            "_id": outbox_id,
            "routing_key": routing_key,
            "body": body,
            "headers": headers,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC)
            + timedelta(seconds=len(self.docs)),
            "published_at": None,
            "status": "pending",
            "claimed_at": None,
        }
        return outbox_id

    async def claim_pending(self, limit: int = 50) -> list[OutboxPendingDoc]:
        claimed: list[OutboxPendingDoc] = []
        now = datetime.now(UTC)
        for doc in sorted(self.docs.values(), key=lambda item: item["created_at"]):
            if doc["status"] != "pending":
                continue
            if len(claimed) >= limit:
                break
            doc["status"] = "processing"
            doc["claimed_at"] = now
            claimed.append(doc)  # type: ignore[arg-type]
        return claimed

    async def mark_published(self, outbox_id: str) -> None:
        self.docs[outbox_id]["status"] = "published"
        self.docs[outbox_id]["published_at"] = datetime.now(UTC)
        self.docs[outbox_id]["claimed_at"] = None

    async def release_claim(self, outbox_id: str) -> None:
        self.docs[outbox_id]["status"] = "pending"
        self.docs[outbox_id]["claimed_at"] = None


@pytest.mark.asyncio
async def test_drain_publishes_claimed_rows_only_once() -> None:
    outbox = _MemoryOutbox()
    await outbox.enqueue("car.raw.created", b"{}", {})
    await outbox.enqueue("car.raw.created", b"{}", {})
    publisher = AsyncMock()
    publisher.publish_raw_body = AsyncMock()
    sink = OutboxEventSink(
        PublishRoutes(
            raw_created="car.raw.created",
            enriched_success="car.enriched.success",
            enrichment_failed="car.enrichment.failed",
        ),
        outbox,  # type: ignore[arg-type]
        publisher,
    )

    assert await sink.drain() == 2
    assert publisher.publish_raw_body.await_count == 2
    assert all(doc["status"] == "published" for doc in outbox.docs.values())
    assert await sink.drain() == 0
    assert publisher.publish_raw_body.await_count == 2


@pytest.mark.asyncio
async def test_drain_releases_claim_on_publish_failure() -> None:
    outbox = _MemoryOutbox()
    await outbox.enqueue("car.raw.created", b"{}", {})
    publisher = AsyncMock()
    publisher.publish_raw_body = AsyncMock(side_effect=RuntimeError("broker down"))
    sink = OutboxEventSink(
        PublishRoutes(
            raw_created="car.raw.created",
            enriched_success="car.enriched.success",
            enrichment_failed="car.enrichment.failed",
        ),
        outbox,  # type: ignore[arg-type]
        publisher,
    )

    with pytest.raises(RuntimeError, match="broker down"):
        await sink.drain()
    assert outbox.docs["ob-1"]["status"] == "pending"
