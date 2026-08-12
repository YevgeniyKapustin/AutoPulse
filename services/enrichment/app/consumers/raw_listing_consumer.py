"""RabbitMQ consumer for car.raw.created.

Ack only after full aggregation and outbox drain. Retries use a
TTL queue (no in-process sleep on the consume loop).
"""

from __future__ import annotations

import logging
import uuid

from aio_pika.abc import AbstractChannel, AbstractIncomingMessage, AbstractQueue
from pydantic import ValidationError

from autopulse_shared.logging import bind_trace_context, clear_contextvars
from autopulse_shared.schemas.events import RawListingEvent
from services.enrichment.app.core.config import Settings
from services.enrichment.app.core.exceptions import (
    EnrichmentError,
    MalformedMessageError,
)
from services.enrichment.app.core.metrics import METRICS, MetricsRecorder
from services.enrichment.app.enrichment.ports import InboxClaimer, ListingEnricher
from services.enrichment.app.messaging.constants import (
    HEADER_RETRY_COUNT,
    METRIC_CONSUMER_ACK,
    METRIC_CONSUMER_DUPLICATES,
    METRIC_CONSUMER_ERRORS,
    METRIC_DLQ,
    UNKNOWN_EXTERNAL_ID,
)
from services.enrichment.app.messaging.retry import (
    EnrichmentRetryPublisher,
    retry_delay_sec,
)

logger = logging.getLogger(__name__)


class RawListingConsumer:
    def __init__(
        self,
        settings: Settings,
        orchestrator: ListingEnricher,
        retry_publisher: EnrichmentRetryPublisher,
        *,
        inbox: InboxClaimer | None = None,
        metrics: MetricsRecorder = METRICS,
    ) -> None:
        self._settings = settings
        self._orchestrator = orchestrator
        self._retry_publisher = retry_publisher
        self._inbox = inbox
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
        """Begin consuming; owns ``channel`` until ``stop()``.

        Callers must not reuse ``channel`` after ``stop()`` (or after a
        subsequent ``start()``, which closes the previous channel).
        """
        await self._release_consume_resources()
        self._stopping = False
        self._channel = channel
        self._queue = queue
        self._consumer_tag = await queue.consume(self._on_message)
        logger.info(
            "RawListingConsumer listening exchange=%s queue=%s",
            self._settings.rabbitmq_exchange,
            queue.name,
        )

    async def stop(self) -> None:
        self._stopping = True
        await self._release_consume_resources()
        logger.info("RawListingConsumer stopped")

    async def handle_message(
        self,
        body: bytes,
        *,
        redelivered: bool = False,
    ) -> None:
        try:
            event = RawListingEvent.model_validate_json(body)
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
            if self._inbox is not None:
                claimed = await self._inbox.try_claim(
                    event.event_id,
                    reclaim_processing=redelivered,
                )
                if not claimed:
                    logger.info(
                        "Skipping duplicate enrichment event_id=%s",
                        event.event_id,
                        extra={
                            "event_id": event.event_id,
                            "request_id": event.request_id,
                        },
                    )
                    self._metrics.inc(METRIC_CONSUMER_DUPLICATES, service="enrichment")
                    return
            await self._orchestrator.enrich(
                event.listing,
                event_id=event.event_id,
                request_id=event.request_id,
                retry_count=event.retry_count,
            )
            if claimed and self._inbox is not None:
                await self._inbox.mark_completed(event.event_id)
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
            logger.error("Malformed enrichment message: %s", exc)
            self._metrics.inc(METRIC_CONSUMER_ERRORS, service="enrichment")
            await self._handle_exhausted(message, self._read_retry_count(message), exc)
            await message.reject(requeue=False)
            self._metrics.inc(METRIC_DLQ, service="enrichment")
            return
        except Exception as exc:
            logger.exception("Enrichment handler failed: %s", exc)
            self._metrics.inc(METRIC_CONSUMER_ERRORS, service="enrichment")
            if not self._is_retryable(exc):
                await self._handle_exhausted(
                    message,
                    self._read_retry_count(message),
                    exc,
                )
                await message.reject(requeue=False)
                self._metrics.inc(METRIC_DLQ, service="enrichment")
                return
            retry_count = self._read_retry_count(message)
            next_retry = retry_count + 1
            if next_retry < self._settings.enrichment_max_retries:
                delay = retry_delay_sec(
                    next_retry,
                    self._settings.enrichment_retry_base_delay_sec,
                    self._settings.enrichment_retry_max_delay_sec,
                )
                await self._schedule_retry(message, next_retry, delay)
                await message.ack()
                return
            await self._handle_exhausted(message, next_retry, exc)
            await message.reject(requeue=False)
            self._metrics.inc(METRIC_DLQ, service="enrichment")
            return
        await message.ack()
        self._metrics.inc(METRIC_CONSUMER_ACK, service="enrichment")

    async def _schedule_retry(
        self,
        message: AbstractIncomingMessage,
        retry_count: int,
        delay_sec: float,
    ) -> None:
        try:
            event = RawListingEvent.model_validate_json(message.body)
            event.retry_count = retry_count
            body = event.model_dump_json().encode("utf-8")
        except Exception:
            body = message.body
        await self._retry_publisher.publish_retry(
            body,
            retry_count=retry_count,
            delay_sec=delay_sec,
        )

    async def _handle_exhausted(
        self,
        message: AbstractIncomingMessage,
        retry_count: int,
        exc: Exception,
    ) -> None:
        external_id = UNKNOWN_EXTERNAL_ID
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
        if isinstance(exc, EnrichmentError):
            return exc.retryable
        return True

    @staticmethod
    def _read_retry_count(message: AbstractIncomingMessage) -> int:
        headers = message.headers or {}
        header_count = headers.get(HEADER_RETRY_COUNT)
        if isinstance(header_count, int):
            return header_count
        try:
            event = RawListingEvent.model_validate_json(message.body)
            return event.retry_count
        except Exception:
            return 0
