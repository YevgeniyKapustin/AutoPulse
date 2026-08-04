"""Consumes car.enriched.success and runs the margin rule engine."""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

import aio_pika
from aio_pika.abc import (
    AbstractChannel,
    AbstractIncomingMessage,
    AbstractQueue,
    AbstractRobustConnection,
)

from autopulse_shared.logging import bind_trace_context, clear_contextvars
from autopulse_shared.schemas.events import ListingEnrichedEvent
from services.pricer.app.core.config import Settings
from services.pricer.app.core.metrics import METRICS
from services.pricer.app.messaging.outbox_publisher import OutboxPublisher
from services.pricer.app.messaging.topology import (
    connect_robust,
    declare_topology,
    open_publisher_channel,
)
from services.pricer.app.repositories.pricing_repository import PricingRepository
from services.pricer.app.services.pricing_service import PricingService

logger = logging.getLogger(__name__)


class InboxClaimer(Protocol):
    async def try_claim_event(self, event_id: str) -> bool: ...


def retry_delay_sec(retry_count: int, base: float, cap: float) -> float:
    return float(min(cap, base * (2 ** max(retry_count - 1, 0))))


class EnrichedListingConsumer:
    def __init__(
        self,
        settings: Settings,
        pricing: PricingService,
        *,
        repository: PricingRepository | None = None,
        inbox: InboxClaimer | None = None,
    ) -> None:
        self._settings = settings
        self._pricing = pricing
        self._repository = repository
        self._inbox = inbox or repository
        self._outbox_publisher: OutboxPublisher | None = None
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
        if self._repository is not None:
            exchange = await self._pub_channel.get_exchange(
                self._settings.rabbitmq_exchange
            )
            self._outbox_publisher = OutboxPublisher(exchange, self._repository)
            await self._outbox_publisher.drain()

        _, queue, _dlq = await declare_topology(self._channel, self._settings)
        self._queue = queue
        self._consumer_tag = await queue.consume(self._on_message)
        logger.info(
            "EnrichedListingConsumer listening exchange=%s queue=%s",
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
                    logger.info("EnrichedListingConsumer stopped")

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        if self._stopping:
            await message.nack(requeue=True)
            return
        try:
            await self.handle_message(message.body)
        except Exception:
            logger.exception("Pricer handler failed")
            METRICS.inc("autopulse_consumer_errors_total", service="pricer")
            retry_count = self._read_retry_count(message)
            next_retry = retry_count + 1
            if next_retry < self._settings.pricer_max_retries:
                delay = retry_delay_sec(
                    next_retry,
                    self._settings.pricer_retry_base_delay_sec,
                    self._settings.pricer_retry_max_delay_sec,
                )
                await asyncio.sleep(delay)
                await self._requeue_with_retry(message, next_retry)
                await message.ack()
                return
            await message.reject(requeue=False)
            METRICS.inc("autopulse_dlq_total", service="pricer")
            return
        await message.ack()
        METRICS.inc("autopulse_consumer_ack_total", service="pricer")

    async def handle_message(self, body: bytes) -> None:
        event = ListingEnrichedEvent.model_validate_json(body)
        clear_contextvars()
        bind_trace_context(
            trace_id=event.request_id or event.event_id,
            request_id=event.request_id,
            event_id=event.event_id,
            external_id=event.listing.external_id,
        )
        try:
            logger.info(
                "Pricing external_id=%s event_id=%s retry=%s",
                event.listing.external_id,
                event.event_id,
                event.retry_count,
                extra={"event_id": event.event_id, "request_id": event.request_id},
            )
            if self._inbox is not None and not await self._inbox.try_claim_event(
                event.event_id
            ):
                logger.info(
                    "Skipping duplicate pricing event_id=%s",
                    event.event_id,
                )
                METRICS.inc(
                    "autopulse_consumer_duplicates_total",
                    service="pricer",
                )
                return
            await self._pricing.price(event.listing, event_id=event.event_id)
            if self._outbox_publisher is not None:
                await self._outbox_publisher.drain()
        finally:
            clear_contextvars()

    async def _requeue_with_retry(
        self,
        message: AbstractIncomingMessage,
        retry_count: int,
    ) -> None:
        try:
            event = ListingEnrichedEvent.model_validate_json(message.body)
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
            routing_key=self._settings.routing_key_enriched_success,
            mandatory=True,
        )
        logger.warning("Requeued pricing retry_count=%s", retry_count)

    @staticmethod
    def _read_retry_count(message: AbstractIncomingMessage) -> int:
        headers = message.headers or {}
        header_count = headers.get("retry_count")
        if isinstance(header_count, int):
            return header_count
        try:
            event = ListingEnrichedEvent.model_validate_json(message.body)
            return event.retry_count
        except Exception:
            return 0
