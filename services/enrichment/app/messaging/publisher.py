"""Publish enrichment domain events with confirms and mandatory routing."""
from __future__ import annotations

import logging
from typing import Any, cast

import aio_pika
from aio_pika.abc import AbstractExchange
from aio_pika.exceptions import DeliveryError
from pamqp.commands import Basic

from autopulse_shared.schemas.events import (
    BaseEvent,
    EnrichmentFailedEvent,
    ListingEnrichedEvent,
    RawListingEvent,
)
from services.enrichment.app.core.metrics import METRICS, MetricsRecorder
from services.enrichment.app.messaging.event_message import serialize_event
from services.enrichment.app.messaging.routes import PublishRoutes

logger = logging.getLogger(__name__)


class PublishError(RuntimeError):
    """Broker nack/reject or unroutable mandatory publish."""


class EventPublisher:
    """AMQP delivery only — serialization and routes are injected collaborators."""

    def __init__(
        self,
        exchange: AbstractExchange,
        routes: PublishRoutes,
        metrics: MetricsRecorder = METRICS,
    ) -> None:
        self._exchange = exchange
        self._routes = routes
        self._metrics = metrics

    async def publish_event(
        self,
        event: BaseEvent,
        routing_key: str | None = None,
    ) -> None:
        key = routing_key or self._routes.for_event(event)
        payload = serialize_event(event)
        await self.publish_raw_body(payload.body, key, headers=payload.headers)
        logger.info(
            "Published %s key=%s",
            event.__class__.__name__,
            key,
            extra={"event_id": event.event_id, "request_id": event.request_id},
        )

    async def publish_raw(self, event: RawListingEvent) -> None:
        await self.publish_event(event, self._routes.raw_created)

    async def publish_enriched(self, event: ListingEnrichedEvent) -> None:
        await self.publish_event(event, self._routes.enriched_success)

    async def publish_failed(self, event: EnrichmentFailedEvent) -> None:
        await self.publish_event(event, self._routes.enrichment_failed)

    async def publish_raw_body(
        self,
        body: bytes,
        routing_key: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        message = aio_pika.Message(
            body=body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
            headers=cast(Any, headers) if headers else None,
        )
        await self._deliver(message, routing_key)

    async def _deliver(
        self,
        message: aio_pika.Message,
        routing_key: str,
    ) -> None:
        try:
            confirmation = await self._exchange.publish(
                message,
                routing_key=routing_key,
                mandatory=True,
            )
            if isinstance(confirmation, (Basic.Nack, Basic.Reject)):
                self._metrics.inc(
                    "autopulse_publish_nack_total",
                    routing_key=routing_key,
                )
                raise PublishError(f"Publish NACKed for key={routing_key}")
        except DeliveryError as err:
            self._metrics.inc(
                "autopulse_publish_unroutable_total",
                routing_key=routing_key,
            )
            raise PublishError(
                f"Unroutable message for key={routing_key}"
            ) from err
        self._metrics.inc("autopulse_publish_ok_total", routing_key=routing_key)
