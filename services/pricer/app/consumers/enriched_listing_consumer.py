"""Consumes car.enriched.success via the pricing engine."""

from __future__ import annotations

import logging

from aio_pika.abc import AbstractChannel, AbstractIncomingMessage, AbstractQueue
from pydantic import ValidationError

from autopulse_shared.logging import bind_trace_context, clear_contextvars
from autopulse_shared.schemas.events import ListingEnrichedEvent
from services.pricer.app.core.config import Settings
from services.pricer.app.core.exceptions import (
    MalformedMessageError,
    PricingError,
)
from services.pricer.app.core.metrics import METRICS, MetricsRecorder
from services.pricer.app.messaging.outbox_publisher import OutboxPublisher
from services.pricer.app.messaging.retry import (
    HEADER_RETRY_COUNT,
    PricerRetryPublisher,
    retry_delay_sec,
)
from services.pricer.app.services.ports import InboxStore, PricingCommand

logger = logging.getLogger(__name__)


class EnrichedListingConsumer:
    def __init__(
        self,
        settings: Settings,
        pricing: PricingCommand,
        *,
        inbox: InboxStore | None = None,
        outbox_publisher: OutboxPublisher | None = None,
        retry_publisher: PricerRetryPublisher | None = None,
        metrics: MetricsRecorder = METRICS,
    ) -> None:
        self._settings = settings
        self._pricing = pricing
        self._inbox = inbox
        self._outbox_publisher = outbox_publisher
        self._retry_publisher = retry_publisher
        self._metrics = metrics
        self._channel: AbstractChannel | None = None
        self._queue: AbstractQueue | None = None
        self._consumer_tag: str | None = None
        self._stopping = False

    @property
    def is_ready(self) -> bool:
        """True when the consumer channel is open and bound."""
        return (
            self._channel is not None
            and not self._channel.is_closed
            and self._queue is not None
            and self._consumer_tag is not None
        )

    async def start(
        self,
        *,
        channel: AbstractChannel,
        queue: AbstractQueue,
    ) -> None:
        """Begin consuming; owns ``channel`` until ``stop()``."""
        await self._release_consume_resources()
        self._stopping = False
        self._channel = channel
        self._queue = queue
        self._consumer_tag = await queue.consume(self._on_message)
        logger.info(
            "EnrichedListingConsumer listening exchange=%s queue=%s",
            self._settings.rabbitmq_exchange,
            queue.name,
        )

    async def stop(self) -> None:
        self._stopping = True
        await self._release_consume_resources()
        logger.info("EnrichedListingConsumer stopped")

    async def handle_message(
        self,
        body: bytes,
        *,
        redelivered: bool = False,
    ) -> None:
        try:
            event = ListingEnrichedEvent.model_validate_json(body)
        except ValidationError as exc:
            raise MalformedMessageError(str(exc)) from exc

        clear_contextvars()
        bind_trace_context(
            trace_id=event.request_id or event.event_id,
            request_id=event.request_id,
            event_id=event.event_id,
            external_id=event.listing.external_id,
        )
        claimed = False
        try:
            logger.info(
                "Pricing external_id=%s event_id=%s retry=%s",
                event.listing.external_id,
                event.event_id,
                event.retry_count,
                extra={"event_id": event.event_id, "request_id": event.request_id},
            )
            if self._inbox is not None:
                claimed = await self._inbox.try_claim(
                    event.event_id,
                    reclaim_processing=redelivered,
                )
                if not claimed:
                    logger.info(
                        "Skipping duplicate pricing event_id=%s",
                        event.event_id,
                    )
                    self._metrics.inc(
                        "autopulse_consumer_duplicates_total",
                        service="pricer",
                    )
                    return
            await self._pricing.price(
                event.listing,
                event_id=event.event_id,
                request_id=event.request_id,
            )
            if claimed and self._inbox is not None:
                await self._inbox.mark_completed(event.event_id)
            if self._outbox_publisher is not None:
                await self._outbox_publisher.drain()
        except Exception:
            if claimed and self._inbox is not None:
                await self._inbox.release_claim(event.event_id)
            raise
        finally:
            clear_contextvars()

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        if self._stopping:
            await message.nack(requeue=True)
            return
        try:
            await self.handle_message(
                message.body,
                redelivered=bool(message.redelivered),
            )
        except MalformedMessageError as exc:
            logger.error("Malformed pricing message: %s", exc)
            self._metrics.inc("autopulse_consumer_errors_total", service="pricer")
            await message.reject(requeue=False)
            self._metrics.inc("autopulse_dlq_total", service="pricer")
            return
        except Exception as exc:
            logger.exception("Pricer handler failed: %s", exc)
            self._metrics.inc("autopulse_consumer_errors_total", service="pricer")
            if not self._is_retryable(exc):
                await message.reject(requeue=False)
                self._metrics.inc("autopulse_dlq_total", service="pricer")
                return
            retry_count = self._read_retry_count(message)
            next_retry = retry_count + 1
            if next_retry < self._settings.pricer_max_retries:
                delay = retry_delay_sec(
                    next_retry,
                    self._settings.pricer_retry_base_delay_sec,
                    self._settings.pricer_retry_max_delay_sec,
                )
                await self._schedule_retry(message, next_retry, delay)
                await message.ack()
                return
            await message.reject(requeue=False)
            self._metrics.inc("autopulse_dlq_total", service="pricer")
            return
        await message.ack()
        self._metrics.inc("autopulse_consumer_ack_total", service="pricer")

    async def _schedule_retry(
        self,
        message: AbstractIncomingMessage,
        retry_count: int,
        delay_sec: float,
    ) -> None:
        if self._retry_publisher is None:
            raise RuntimeError("Retry publisher is not configured")
        try:
            event = ListingEnrichedEvent.model_validate_json(message.body)
            event.retry_count = retry_count
            body = event.model_dump_json().encode("utf-8")
        except Exception:
            body = message.body
        await self._retry_publisher.publish_retry(
            body,
            retry_count=retry_count,
            delay_sec=delay_sec,
        )

    async def _release_consume_resources(self) -> None:
        try:
            if self._queue is not None and self._consumer_tag is not None:
                await self._queue.cancel(self._consumer_tag)
        finally:
            self._consumer_tag = None
            self._queue = None
            channel = self._channel
            self._channel = None
            if channel is not None and not channel.is_closed:
                await channel.close()

    @staticmethod
    def _is_retryable(exc: BaseException) -> bool:
        if isinstance(exc, PricingError):
            return exc.retryable
        return True

    @staticmethod
    def _read_retry_count(message: AbstractIncomingMessage) -> int:
        headers = message.headers or {}
        header_count = headers.get(HEADER_RETRY_COUNT)
        if isinstance(header_count, int):
            return header_count
        try:
            event = ListingEnrichedEvent.model_validate_json(message.body)
            return event.retry_count
        except Exception:
            return 0
