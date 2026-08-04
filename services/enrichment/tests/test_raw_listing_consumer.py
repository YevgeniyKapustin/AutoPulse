"""Unit tests for TTL-based enrichment retries."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.enrichment.app.consumers.raw_listing_consumer import RawListingConsumer
from services.enrichment.app.core.config import Settings
from services.enrichment.app.messaging.retry import retry_delay_sec


def test_retry_delay_exponential_and_capped() -> None:
    assert retry_delay_sec(1, base=1.0, cap=30.0) == 1.0
    assert retry_delay_sec(2, base=1.0, cap=30.0) == 2.0
    assert retry_delay_sec(3, base=1.0, cap=30.0) == 4.0
    assert retry_delay_sec(10, base=1.0, cap=30.0) == 30.0


@pytest.mark.asyncio
async def test_failure_schedules_ttl_retry_without_sleep() -> None:
    settings = Settings(enrichment_max_retries=5, enrichment_retry_base_delay_sec=1.0)
    orchestrator = MagicMock()
    orchestrator.enrich = AsyncMock(side_effect=RuntimeError("boom"))
    orchestrator.publish_failure = AsyncMock()
    retry_publisher = MagicMock()
    retry_publisher.publish_retry = AsyncMock()

    from autopulse_shared.schemas.events import RawListingEvent
    from autopulse_shared.schemas.listing import RawListing

    event = RawListingEvent(listing=RawListing(external_id="e1", title="x"))
    body = event.model_dump_json().encode("utf-8")
    message = SimpleNamespace(
        body=body,
        headers={},
        ack=AsyncMock(),
        reject=AsyncMock(),
        nack=AsyncMock(),
    )

    consumer = RawListingConsumer(
        settings,
        orchestrator,
        retry_publisher,
    )
    await consumer._on_message(message)  # type: ignore[arg-type]

    retry_publisher.publish_retry.assert_awaited_once()
    kwargs = retry_publisher.publish_retry.await_args.kwargs
    assert kwargs["retry_count"] == 1
    assert kwargs["delay_sec"] == 1.0
    message.ack.assert_awaited_once()
    message.reject.assert_not_called()
