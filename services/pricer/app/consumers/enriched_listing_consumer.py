"""Consumes car.enriched.success and runs the margin rule engine."""

from __future__ import annotations

import logging

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from autopulse_shared.schemas.events import ListingEnrichedEvent
from services.pricer.app.core.config import Settings
from services.pricer.app.messaging.topology import connect_robust, declare_topology
from services.pricer.app.services.pricing_service import PricingService

logger = logging.getLogger(__name__)


class EnrichedListingConsumer:
    def __init__(self, settings: Settings, pricing: PricingService) -> None:
        self._settings = settings
        self._pricing = pricing
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._consumer_tag: str | None = None

    async def start(self) -> None:
        self._connection = await connect_robust(self._settings)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=8)
        _exchange, queue, _dlq = await declare_topology(self._channel, self._settings)
        self._consumer_tag = await queue.consume(self._on_message)
        logger.info(
            "EnrichedListingConsumer listening exchange=%s queue=%s",
            self._settings.rabbitmq_exchange,
            queue.name,
        )

    async def stop(self) -> None:
        try:
            if self._channel is not None and self._consumer_tag is not None:
                await self._channel.cancel(self._consumer_tag)
        finally:
            self._consumer_tag = None
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
        try:
            await self.handle_message(message.body)
        except Exception:
            logger.exception("Pricer handler failed")
            retry_count = self._read_retry_count(message)
            next_retry = retry_count + 1
            if next_retry < self._settings.pricer_max_retries:
                await self._requeue_with_retry(message, next_retry)
                await message.ack()
                return
            await message.reject(requeue=False)
            return
        await message.ack()

    async def handle_message(self, body: bytes) -> None:
        event = ListingEnrichedEvent.model_validate_json(body)
        logger.info(
            "Pricing external_id=%s event_id=%s retry=%s",
            event.listing.external_id,
            event.event_id,
            event.retry_count,
        )
        await self._pricing.price(event.listing)

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
        assert self._channel is not None
        exchange = await self._channel.get_exchange(self._settings.rabbitmq_exchange)
        await exchange.publish(
            aio_pika.Message(
                body=body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
                headers={"retry_count": retry_count},
            ),
            routing_key=self._settings.routing_key_enriched_success,
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
