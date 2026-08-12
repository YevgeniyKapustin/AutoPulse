"""Consumer retry / inbox / DLQ unit tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from services.pricer.app.consumers.enriched_listing_consumer import (
    EnrichedListingConsumer,
)
from services.pricer.app.core.config import Settings
from services.pricer.app.core.exceptions import PermanentPricingError
from services.pricer.app.messaging.retry import retry_delay_sec
from services.pricer.app.repositories.memory import InMemoryPricingRepository

from autopulse_shared.schemas.events import ListingEnrichedEvent
from autopulse_shared.schemas.listing import EnrichedListing, ListingSource


def test_retry_delay_exponential_and_capped() -> None:
    assert retry_delay_sec(1, base=1.0, cap=30.0) == 1.0
    assert retry_delay_sec(2, base=1.0, cap=30.0) == 2.0
    assert retry_delay_sec(3, base=1.0, cap=30.0) == 4.0
    assert retry_delay_sec(10, base=1.0, cap=30.0) == 30.0


def _listing() -> EnrichedListing:
    return EnrichedListing(
        external_id="car-1",
        source=ListingSource.MANUAL,
        asking_price=10_000,
        llm_done=True,
        cv_done=True,
    )


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
    price: AsyncMock,
    inbox: InMemoryPricingRepository | None = None,
    max_retries: int = 5,
) -> EnrichedListingConsumer:
    pricing = MagicMock()
    pricing.price = price
    retry_publisher = MagicMock()
    retry_publisher.publish_retry = AsyncMock()
    return EnrichedListingConsumer(
        Settings(
            pricer_max_retries=max_retries,
            pricer_retry_base_delay_sec=1.0,
        ),
        pricing,
        inbox=inbox,
        retry_publisher=retry_publisher,
        metrics=MagicMock(),
    )


@pytest.mark.asyncio
async def test_failure_schedules_ttl_retry_and_releases_claim() -> None:
    inbox = InMemoryPricingRepository()
    event = ListingEnrichedEvent(event_id="evt-1", listing=_listing())
    body = event.model_dump_json().encode("utf-8")
    message = _message(body)
    consumer = _consumer(
        price=AsyncMock(side_effect=RuntimeError("db down")),
        inbox=inbox,
    )

    await consumer._on_message(message)  # type: ignore[arg-type]

    assert "evt-1" not in inbox._inbox
    consumer._retry_publisher.publish_retry.assert_awaited_once()  # type: ignore[union-attr]
    message.ack.assert_awaited_once()
    message.reject.assert_not_called()


@pytest.mark.asyncio
async def test_redelivery_reclaims_processing() -> None:
    inbox = InMemoryPricingRepository()
    await inbox.try_claim("evt-2")
    event = ListingEnrichedEvent(event_id="evt-2", listing=_listing())
    consumer = _consumer(price=AsyncMock(), inbox=inbox)

    await consumer.handle_message(
        event.model_dump_json().encode("utf-8"),
        redelivered=True,
    )

    consumer._pricing.price.assert_awaited_once()  # type: ignore[attr-defined]
    assert inbox._inbox["evt-2"] == "completed"


@pytest.mark.asyncio
async def test_completed_duplicate_skips_price() -> None:
    inbox = InMemoryPricingRepository()
    await inbox.try_claim("evt-3")
    await inbox.mark_completed("evt-3")
    event = ListingEnrichedEvent(event_id="evt-3", listing=_listing())
    message = _message(event.model_dump_json().encode("utf-8"))
    consumer = _consumer(price=AsyncMock(), inbox=inbox)

    await consumer._on_message(message)  # type: ignore[arg-type]

    consumer._pricing.price.assert_not_awaited()  # type: ignore[attr-defined]
    message.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_permanent_error_goes_to_dlq() -> None:
    event = ListingEnrichedEvent(event_id="evt-4", listing=_listing())
    message = _message(event.model_dump_json().encode("utf-8"))
    consumer = _consumer(
        price=AsyncMock(side_effect=PermanentPricingError("bad input")),
        max_retries=5,
    )

    await consumer._on_message(message)  # type: ignore[arg-type]

    consumer._retry_publisher.publish_retry.assert_not_awaited()  # type: ignore[union-attr]
    message.reject.assert_awaited_once_with(requeue=False)


@pytest.mark.asyncio
async def test_malformed_message_rejects() -> None:
    message = _message(b"{not-json")
    consumer = _consumer(price=AsyncMock())

    await consumer._on_message(message)  # type: ignore[arg-type]

    consumer._pricing.price.assert_not_awaited()  # type: ignore[attr-defined]
    message.reject.assert_awaited_once_with(requeue=False)


@pytest.mark.asyncio
async def test_exhausted_retries_reject() -> None:
    event = ListingEnrichedEvent(event_id="evt-5", listing=_listing())
    message = _message(event.model_dump_json().encode("utf-8"))
    consumer = _consumer(
        price=AsyncMock(side_effect=RuntimeError("boom")),
        max_retries=1,
    )

    await consumer._on_message(message)  # type: ignore[arg-type]

    consumer._retry_publisher.publish_retry.assert_not_awaited()  # type: ignore[union-attr]
    message.reject.assert_awaited_once_with(requeue=False)
