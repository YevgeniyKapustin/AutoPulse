"""Publish enrichment domain events to the topic exchange."""

from __future__ import annotations

import logging

import aio_pika
from aio_pika.abc import AbstractExchange
from pydantic import BaseModel

from autopulse_shared.schemas.events import (
    EnrichmentFailedEvent,
    ListingEnrichedEvent,
    RawListingEvent,
)
from services.enrichment.app.core.config import Settings

logger = logging.getLogger(__name__)


class EventPublisher:
    def __init__(self, exchange: AbstractExchange, settings: Settings) -> None:
        self._exchange = exchange
        self._settings = settings

    async def publish_raw(self, event: RawListingEvent) -> None:
        await self._publish(event, self._settings.routing_key_raw_created)

    async def publish_enriched(self, event: ListingEnrichedEvent) -> None:
        await self._publish(event, self._settings.routing_key_enriched_success)

    async def publish_failed(self, event: EnrichmentFailedEvent) -> None:
        await self._publish(event, self._settings.routing_key_enrichment_failed)

    async def _publish(self, event: BaseModel, routing_key: str) -> None:
        # model_dump_json (not model_dump) so HttpUrl becomes a plain string.
        body = event.model_dump_json().encode("utf-8")
        message = aio_pika.Message(
            body=body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
            headers={"event_type": getattr(event, "event_type", None)},
        )
        await self._exchange.publish(message, routing_key=routing_key)
        logger.info("Published %s key=%s", event.__class__.__name__, routing_key)
