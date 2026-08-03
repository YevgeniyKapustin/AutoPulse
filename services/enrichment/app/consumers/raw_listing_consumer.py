"""RabbitMQ consumer for car.raw.created.

Ack only after full aggregation.
"""

from __future__ import annotations

import logging
import uuid

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from autopulse_shared.schemas.events import RawListingEvent
from services.enrichment.app.core.config import Settings
from services.enrichment.app.messaging.publisher import EventPublisher
from services.enrichment.app.messaging.topology import connect_robust, declare_topology
from services.enrichment.app.services.enrichment_orchestrator import (
    EnrichmentOrchestrator,
)

logger = logging.getLogger(__name__)


class RawListingConsumer:
    def __init__(
        self,
        settings: Settings,
        orchestrator: EnrichmentOrchestrator,
    ) -> None:
        self._settings = settings
        self._orchestrator = orchestrator
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._consumer_tag: str | None = None

    async def start(self) -> None:
        self._connection = await connect_robust(self._settings)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=4)
        exchange, queue, _dlq = await declare_topology(self._channel, self._settings)
        publisher = EventPublisher(exchange, self._settings)
        self._orchestrator.set_publisher(publisher)
        self._consumer_tag = await queue.consume(self._on_message)
        logger.info(
            "RawListingConsumer listening exchange=%s queue=%s",
            self._settings.rabbitmq_exchange,
            queue.name,
        )

    async def stop(self) -> None:
        if self._channel is not None and self._consumer_tag is not None:
            await self._channel.cancel(self._consumer_tag)
        if self._channel is not None:
            await self._channel.close()
        if self._connection is not None:
            await self._connection.close()
        logger.info("RawListingConsumer stopped")

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        try:
            await self.handle_message(message.body)
        except Exception as exc:
            logger.exception("Enrichment handler failed: %s", exc)
            retry_count = self._read_retry_count(message)
            next_retry = retry_count + 1
            if next_retry < self._settings.enrichment_max_retries:
                await self._requeue_with_retry(message, next_retry)
                await message.ack()
                return
            await self._handle_exhausted(message, next_retry, exc)
            await message.reject(requeue=False)
            return
        await message.ack()

    async def handle_message(self, body: bytes) -> None:
        event = RawListingEvent.model_validate_json(body)
        await self._orchestrator.enrich(
            event.listing,
            event_id=event.event_id,
            request_id=event.request_id,
            retry_count=event.retry_count,
        )

    async def _requeue_with_retry(
        self,
        message: AbstractIncomingMessage,
        retry_count: int,
    ) -> None:
        try:
            event = RawListingEvent.model_validate_json(message.body)
            event.retry_count = retry_count
            body = event.model_dump_json().encode("utf-8")
        except Exception:
            body = message.body
        assert self._channel is not None
        exchange = await self._channel.get_exchange(self._settings.rabbitmq_exchange)
        await exchange.publish(
            aio_pika.Message(
                body=body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
                headers={"retry_count": retry_count},
            ),
            routing_key=self._settings.routing_key_raw_created,
        )
        logger.warning("Requeued enrichment retry_count=%s", retry_count)

    async def _handle_exhausted(
        self,
        message: AbstractIncomingMessage,
        retry_count: int,
        exc: Exception,
    ) -> None:
        external_id = "unknown"
        stage = getattr(exc, "stage", None)
        error = str(exc) or "enrichment failed after max retries"
        event_id = str(uuid.uuid4())
        request_id: str | None = None
        try:
            event = RawListingEvent.model_validate_json(message.body)
            external_id = event.listing.external_id
            event_id = event.event_id
            request_id = event.request_id
        except Exception:
            pass
        await self._orchestrator.publish_failure(
            external_id=external_id,
            error=error,
            stage=stage if isinstance(stage, str) else None,
            event_id=event_id,
            request_id=request_id,
            retry_count=retry_count,
        )
        logger.error(
            "Enrichment exhausted external_id=%s retries=%s",
            external_id,
            retry_count,
        )

    @staticmethod
    def _read_retry_count(message: AbstractIncomingMessage) -> int:
        headers = message.headers or {}
        header_count = headers.get("retry_count")
        if isinstance(header_count, int):
            return header_count
        try:
            event = RawListingEvent.model_validate_json(message.body)
            return event.retry_count
        except Exception:
            return 0
