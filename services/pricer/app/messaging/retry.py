"""Delayed retry via TTL queue + DLX back to the work routing key."""

from __future__ import annotations

import logging
from typing import Any, cast

import aio_pika
from aio_pika.abc import AbstractExchange

from services.pricer.app.core.config import Settings
from services.pricer.app.core.metrics import METRICS, MetricsRecorder

logger = logging.getLogger(__name__)

HEADER_RETRY_COUNT = "retry_count"


def retry_delay_sec(retry_count: int, base: float, cap: float) -> float:
    """Exponential backoff for retry_count >= 1, capped."""
    return float(min(cap, base * (2 ** max(retry_count - 1, 0))))


class PricerRetryPublisher:
    """Publish failed work into the TTL retry queue."""

    def __init__(
        self,
        exchange: AbstractExchange,
        settings: Settings,
        metrics: MetricsRecorder = METRICS,
    ) -> None:
        self._exchange = exchange
        self._settings = settings
        self._metrics = metrics

    async def publish_retry(
        self,
        body: bytes,
        *,
        retry_count: int,
        delay_sec: float,
    ) -> None:
        expiration_ms = max(1, int(delay_sec * 1000))
        headers: dict[str, Any] = {HEADER_RETRY_COUNT: retry_count}
        await self._exchange.publish(
            aio_pika.Message(
                body=body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
                expiration=cast(Any, str(expiration_ms)),
                headers=cast(Any, headers),
            ),
            routing_key=self._settings.routing_key_pricer_retry,
            mandatory=True,
        )
        self._metrics.inc(
            "autopulse_retry_published_total",
            service="pricer",
            retry_count=str(retry_count),
        )
        logger.warning(
            "Scheduled pricer retry_count=%s delay_sec=%.2f",
            retry_count,
            delay_sec,
        )
