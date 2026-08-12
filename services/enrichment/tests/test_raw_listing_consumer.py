"""Unit tests for TTL-based enrichment retries and inbox lifecycle."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from services.enrichment.app.consumers.raw_listing_consumer import RawListingConsumer
from services.enrichment.app.core.config import Settings
from services.enrichment.app.core.exceptions import (
    MalformedMessageError,
    PermanentEnrichmentError,
)
from services.enrichment.app.messaging.retry import retry_delay_sec

from autopulse_shared.schemas.events import RawListingEvent
from autopulse_shared.schemas.listing import RawListing


def test_retry_delay_exponential_and_capped() -> None:
    assert retry_delay_sec(1, base=1.0, cap=30.0) == 1.0
    assert retry_delay_sec(2, base=1.0, cap=30.0) == 2.0
    assert retry_delay_sec(3, base=1.0, cap=30.0) == 4.0
    assert retry_delay_sec(10, base=1.0, cap=30.0) == 30.0


class _MemoryInbox:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    async def try_claim(
        self,
        event_id: str,
        *,
        reclaim_processing: bool = False,
    ) -> bool:
        doc = self.docs.get(event_id)
        if doc is None:
            self.docs[event_id] = {"status": "processing"}
            return True
        if doc["status"] == "completed":
            return False
        return doc["status"] == "processing" and reclaim_processing

    async def mark_completed(self, event_id: str) -> None:
        self.docs[event_id] = {"status": "completed"}

    async def release_claim(self, event_id: str) -> None:
        doc = self.docs.get(event_id)
        if doc is not None and doc["status"] == "processing":
            del self.docs[event_id]


def _message(body: bytes, *, redelivered: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        body=body,
        headers={},
        redelivered=redelivered,
        ack=AsyncMock(),
        reject=AsyncMock(),
        nack=AsyncMock(),
    )


def _consumer(
    *,
    enrich: AsyncMock,
    publish_failure: AsyncMock | None = None,
    inbox: _MemoryInbox | None = None,
    max_retries: int = 5,
) -> RawListingConsumer:
    settings = Settings(
        enrichment_max_retries=max_retries,
        enrichment_retry_base_delay_sec=1.0,
    )
    orchestrator = MagicMock()
    orchestrator.enrich = enrich
    orchestrator.publish_failure = publish_failure or AsyncMock()
    retry_publisher = MagicMock()
    retry_publisher.publish_retry = AsyncMock()
    return RawListingConsumer(
        settings,
        orchestrator,
        retry_publisher,
        inbox=inbox,
        metrics=MagicMock(),
    )


@pytest.mark.asyncio
async def test_failure_schedules_ttl_retry_without_sleep() -> None:
    event = RawListingEvent(listing=RawListing(external_id="e1", title="x"))
    body = event.model_dump_json().encode("utf-8")
    message = _message(body)
    consumer = _consumer(enrich=AsyncMock(side_effect=RuntimeError("boom")))

    await consumer._on_message(message)  # type: ignore[arg-type]

    consumer._retry_publisher.publish_retry.assert_awaited_once()
    kwargs = consumer._retry_publisher.publish_retry.await_args.kwargs
    assert kwargs["retry_count"] == 1
    assert kwargs["delay_sec"] == 1.0
    message.ack.assert_awaited_once()
    message.reject.assert_not_called()


@pytest.mark.asyncio
async def test_claim_failure_releases_so_retry_can_reclaim() -> None:
    inbox = _MemoryInbox()
    event = RawListingEvent(listing=RawListing(external_id="e1", title="x"))
    body = event.model_dump_json().encode("utf-8")
    message = _message(body)
    consumer = _consumer(
        enrich=AsyncMock(side_effect=RuntimeError("boom")),
        inbox=inbox,
    )

    await consumer._on_message(message)  # type: ignore[arg-type]

    assert event.event_id not in inbox.docs
    message.ack.assert_awaited_once()

    # Retry delivery can claim again.
    claimed = await inbox.try_claim(event.event_id)
    assert claimed is True


@pytest.mark.asyncio
async def test_redelivery_reclaims_processing_claim() -> None:
    inbox = _MemoryInbox()
    event = RawListingEvent(listing=RawListing(external_id="e1", title="x"))
    await inbox.try_claim(event.event_id)

    consumer = _consumer(enrich=AsyncMock(), inbox=inbox)
    await consumer.handle_message(
        event.model_dump_json().encode("utf-8"),
        redelivered=True,
    )

    consumer._orchestrator.enrich.assert_awaited_once()
    assert inbox.docs[event.event_id]["status"] == "completed"


@pytest.mark.asyncio
async def test_completed_duplicate_is_acked_without_enrich() -> None:
    inbox = _MemoryInbox()
    event = RawListingEvent(listing=RawListing(external_id="e1", title="x"))
    await inbox.try_claim(event.event_id)
    await inbox.mark_completed(event.event_id)

    message = _message(event.model_dump_json().encode("utf-8"))
    consumer = _consumer(enrich=AsyncMock(), inbox=inbox)
    await consumer._on_message(message)  # type: ignore[arg-type]

    consumer._orchestrator.enrich.assert_not_awaited()
    message.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_success_marks_inbox_completed() -> None:
    inbox = _MemoryInbox()
    event = RawListingEvent(listing=RawListing(external_id="e1", title="x"))
    message = _message(event.model_dump_json().encode("utf-8"))
    consumer = _consumer(enrich=AsyncMock(), inbox=inbox)

    await consumer._on_message(message)  # type: ignore[arg-type]

    assert inbox.docs[event.event_id]["status"] == "completed"
    message.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_exhausted_retries_publish_failure_and_reject() -> None:
    event = RawListingEvent(listing=RawListing(external_id="e1", title="x"))
    body = event.model_dump_json().encode("utf-8")
    message = _message(body)
    publish_failure = AsyncMock()
    consumer = _consumer(
        enrich=AsyncMock(side_effect=RuntimeError("boom")),
        publish_failure=publish_failure,
        max_retries=1,
    )

    await consumer._on_message(message)  # type: ignore[arg-type]

    publish_failure.assert_awaited_once()
    message.reject.assert_awaited_once_with(requeue=False)
    message.ack.assert_not_called()


@pytest.mark.asyncio
async def test_permanent_error_goes_straight_to_dlq() -> None:
    event = RawListingEvent(listing=RawListing(external_id="e1", title="x"))
    body = event.model_dump_json().encode("utf-8")
    message = _message(body)
    publish_failure = AsyncMock()
    consumer = _consumer(
        enrich=AsyncMock(
            side_effect=PermanentEnrichmentError("bad client", stage="llm"),
        ),
        publish_failure=publish_failure,
        max_retries=5,
    )

    await consumer._on_message(message)  # type: ignore[arg-type]

    consumer._retry_publisher.publish_retry.assert_not_awaited()
    publish_failure.assert_awaited_once()
    message.reject.assert_awaited_once_with(requeue=False)


@pytest.mark.asyncio
async def test_malformed_message_rejects_without_retry() -> None:
    message = _message(b"{not-json")
    consumer = _consumer(enrich=AsyncMock())

    await consumer._on_message(message)  # type: ignore[arg-type]

    consumer._orchestrator.enrich.assert_not_awaited()
    consumer._retry_publisher.publish_retry.assert_not_awaited()
    message.reject.assert_awaited_once_with(requeue=False)


@pytest.mark.asyncio
async def test_handle_message_raises_malformed() -> None:
    consumer = _consumer(enrich=AsyncMock())
    with pytest.raises(MalformedMessageError):
        await consumer.handle_message(b"[]")
