"""RabbitMQ consumer for car.raw.created.

Ack only after full aggregation and outbox drain.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Protocol

import aio_pika
from aio_pika.abc import (
    AbstractChannel,
    AbstractIncomingMessage,
    AbstractQueue,
    AbstractRobustConnection,
)

from autopulse_shared.logging import bind_trace_context, clear_contextvars
from autopulse_shared.schemas.events import RawListingEvent
from services.enrichment.app.core.config import Settings
from services.enrichment.app.core.metrics import METRICS
from services.enrichment.app.messaging.outbox_sink import OutboxEventSink
from services.enrichment.app.messaging.publisher import EventPublisher
from services.enrichment.app.messaging.routes import PublishRoutes
from services.enrichment.app.messaging.topology import (
    connect_robust,
    declare_topology,
    open_publisher_channel,
)
from services.enrichment.app.repositories.messaging_store import OutboxRepository
from services.enrichment.app.services.enrichment_orchestrator import (
    EnrichmentOrchestrator,
)

logger = logging.getLogger(__name__)


class InboxClaimer(Protocol):
    async def try_claim(self, event_id: str) -> bool: ...


def retry_delay_sec(retry_count: int, base: float, cap: float) -> float:
    return float(min(cap, base * (2 ** max(retry_count - 1, 0))))


class RawListingConsumer:
    def __init__(
        self,
        settings: Settings,
        orchestrator: EnrichmentOrchestrator,
        *,
        inbox: InboxClaimer | None = None,
        outbox: OutboxRepository | None = None,
    ) -> None:
        self._settings = settings
        self._orchestrator = orchestrator
        self._inbox = inbox
        self._outbox = outbox
        self._outbox_sink: OutboxEventSink | None = None
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractChannel | None = None
        self._pub_channel: AbstractChannel | None = None
        self._queue: AbstractQueue | None = None
        self._consumer_tag: str | None = None
        self._stopping = False

    @property
    def is_ready(self) -> bool:
        """True when the consumer connection and channel are open."""
        return (
            self._connection is not None
            and not self._connection.is_closed
            and self._channel is not None
            and not self._channel.is_closed
        )

    async def start(self) -> None:
        self._connection = await connect_robust(self._settings)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self._settings.rabbitmq_prefetch)
        await declare_topology(self._channel, self._settings)
        self._pub_channel = await open_publisher_channel(self._connection)
        pub_exchange = await self._pub_channel.get_exchange(
            self._settings.rabbitmq_exchange
        )
        routes = PublishRoutes(
            raw_created=self._settings.routing_key_raw_created,
            enriched_success=self._settings.routing_key_enriched_success,
            enrichment_failed=self._settings.routing_key_enrichment_failed,
        )
        publisher = EventPublisher(pub_exchange, routes, metrics=METRICS)
        if self._outbox is not None:
            self._outbox_sink = OutboxEventSink(routes, self._outbox, publisher)
            self._orchestrator.set_publisher(self._outbox_sink)
            await self._outbox_sink.drain()
        else:
            self._orchestrator.set_publisher(publisher)

        _exchange, queue, _dlq = await declare_topology(self._channel, self._settings)
        self._queue = queue
        self._consumer_tag = await queue.consume(self._on_message)
        logger.info(
            "RawListingConsumer listening exchange=%s queue=%s",
            self._settings.rabbitmq_exchange,
            queue.name,
        )

    async def stop(self) -> None:
        self._stopping = True
        try:
            if self._queue is not None and self._consumer_tag is not None:
                await self._queue.cancel(self._consumer_tag)
        finally:
            self._consumer_tag = None
            self._queue = None
            try:
                if self._pub_channel is not None and not self._pub_channel.is_closed:
                    await self._pub_channel.close()
            finally:
                self._pub_channel = None
                try:
                    if self._channel is not None and not self._channel.is_closed:
                        await self._channel.close()
                finally:
                    self._channel = None
                    if self._connection is not None and not self._connection.is_closed:
                        await self._connection.close()
                    self._connection = None
                    logger.info("RawListingConsumer stopped")

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        if self._stopping:
            await message.nack(requeue=True)
            return
        try:
            await self.handle_message(message.body)
        except Exception as exc:
            logger.exception("Enrichment handler failed: %s", exc)
            METRICS.inc("autopulse_consumer_errors_total", service="enrichment")
            retry_count = self._read_retry_count(message)
            next_retry = retry_count + 1
            if next_retry < self._settings.enrichment_max_retries:
                delay = retry_delay_sec(
                    next_retry,
                    self._settings.enrichment_retry_base_delay_sec,
                    self._settings.enrichment_retry_max_delay_sec,
                )
                await asyncio.sleep(delay)
                await self._requeue_with_retry(message, next_retry)
                await message.ack()
                return
            await self._handle_exhausted(message, next_retry, exc)
            await message.reject(requeue=False)
            METRICS.inc("autopulse_dlq_total", service="enrichment")
            return
        await message.ack()
        METRICS.inc("autopulse_consumer_ack_total", service="enrichment")

    async def handle_message(self, body: bytes) -> None:
        event = RawListingEvent.model_validate_json(body)
        clear_contextvars()
        bind_trace_context(
            trace_id=event.request_id or event.event_id,
            request_id=event.request_id,
            event_id=event.event_id,
            external_id=event.listing.external_id,
        )
        try:
            if self._inbox is not None and not await self._inbox.try_claim(
                event.event_id
            ):
                logger.info(
                    "Skipping duplicate enrichment event_id=%s",
                    event.event_id,
                    extra={
                        "event_id": event.event_id,
                        "request_id": event.request_id,
                    },
                )
                METRICS.inc(
                    "autopulse_consumer_duplicates_total",
                    service="enrichment",
                )
                return
            await self._orchestrator.enrich(
                event.listing,
                event_id=event.event_id,
                request_id=event.request_id,
                retry_count=event.retry_count,
            )
        finally:
            clear_contextvars()

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
        assert self._pub_channel is not None
        exchange = await self._pub_channel.get_exchange(
            self._settings.rabbitmq_exchange
        )
        await exchange.publish(
            aio_pika.Message(
                body=body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
                headers={"retry_count": retry_count},
            ),
            routing_key=self._settings.routing_key_raw_created,
            mandatory=True,
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
            extra={"event_id": event_id, "request_id": request_id},
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
