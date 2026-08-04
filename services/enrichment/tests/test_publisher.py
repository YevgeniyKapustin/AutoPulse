"""Unit tests for enrichment event publisher collaborators."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aio_pika.exceptions import DeliveryError
from pamqp.commands import Basic
from services.enrichment.app.messaging.event_message import serialize_event
from services.enrichment.app.messaging.publisher import EventPublisher, PublishError
from services.enrichment.app.messaging.routes import PublishRoutes

from autopulse_shared.schemas.events import EventType, RawListingEvent
from autopulse_shared.schemas.listing import ListingSource, RawListing


class FakeMetrics:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    def inc(self, name: str, amount: float = 1.0, **labels: str) -> None:
        self.calls.append((name, labels))


@pytest.fixture
def routes() -> PublishRoutes:
    return PublishRoutes(
        raw_created="car.raw.created",
        enriched_success="car.enriched.success",
        enrichment_failed="car.enrichment.failed",
    )


def test_serialize_event_sets_headers() -> None:
    event = RawListingEvent(
        listing=RawListing(external_id="x", source=ListingSource.MANUAL),
        request_id="req-1",
    )
    payload = serialize_event(event)
    assert b'"external_id":"x"' in payload.body or b'"external_id": "x"' in payload.body
    assert payload.headers["event_type"] == EventType.RAW_CREATED
    assert payload.headers["event_id"] == event.event_id
    assert payload.headers["x-request-id"] == "req-1"
    assert "schema_version" in payload.headers


def test_routes_for_event(routes: PublishRoutes) -> None:
    event = RawListingEvent(
        listing=RawListing(external_id="x", source=ListingSource.MANUAL),
    )
    assert routes.for_event(event) == "car.raw.created"


@pytest.mark.asyncio
async def test_publish_event_uses_injected_metrics(routes: PublishRoutes) -> None:
    exchange = MagicMock()
    exchange.publish = AsyncMock(return_value=Basic.Ack())
    metrics = FakeMetrics()
    publisher = EventPublisher(exchange, routes, metrics=metrics)
    event = RawListingEvent(
        listing=RawListing(external_id="x", source=ListingSource.MANUAL),
    )
    await publisher.publish_event(event)
    assert metrics.calls[-1][0] == "autopulse_publish_ok_total"
    exchange.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_publish_unroutable_wrapped(routes: PublishRoutes) -> None:
    exchange = MagicMock()
    exchange.publish = AsyncMock(side_effect=DeliveryError(None, None))
    metrics = FakeMetrics()
    publisher = EventPublisher(exchange, routes, metrics=metrics)
    event = RawListingEvent(
        listing=RawListing(external_id="x", source=ListingSource.MANUAL),
    )
    with pytest.raises(PublishError, match="Unroutable"):
        await publisher.publish_event(event)
    assert metrics.calls[-1][0] == "autopulse_publish_unroutable_total"
