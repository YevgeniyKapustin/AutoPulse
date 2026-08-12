"""Publish pricer outbox messages with confirms."""

from __future__ import annotations

import logging
from typing import Any, cast

import aio_pika
from aio_pika.abc import AbstractExchange
from aio_pika.exceptions import DeliveryError
from pamqp.commands import Basic

from services.pricer.app.core.metrics import METRICS, MetricsRecorder
from services.pricer.app.services.ports import OutboxStore

logger = logging.getLogger(__name__)


class PublishError(RuntimeError):
    pass


class OutboxPublisher:
    def __init__(
        self,
        exchange: AbstractExchange,
        repository: OutboxStore,
        metrics: MetricsRecorder = METRICS,
    ) -> None:
        self._exchange = exchange
        self._repository = repository
        self._metrics = metrics

    async def drain(self, limit: int = 50) -> int:
        """Claim and publish pending outbox rows; continue on failures."""
        pending = await self._repository.claim_pending(limit=limit)
        published = 0
        for item in pending:
            outbox_id = item["id"]
            try:
                await self._publish_message(
                    item["payload"],
                    item["routing_key"],
                    item["headers"],
                )
                await self._repository.mark_published(outbox_id)
                published += 1
            except Exception:
                logger.exception(
                    "Outbox publish failed outbox_id=%s; releasing claim",
                    outbox_id,
                )
                await self._repository.release_outbox_claim(outbox_id)
        if published:
            logger.info("Drained pricer outbox count=%s", published)
        return published

    async def _publish_message(
        self,
        body: bytes,
        routing_key: str,
        headers: dict[str, str],
    ) -> None:
        message = aio_pika.Message(
            body=body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
            headers=cast(Any, headers) if headers else None,
        )
        try:
            confirmation = await self._exchange.publish(
                message,
                routing_key=routing_key,
                mandatory=True,
            )
            if isinstance(confirmation, Basic.Nack | Basic.Reject):
                self._metrics.inc(
                    "autopulse_publish_nack_total",
                    routing_key=routing_key,
                )
                raise PublishError(f"Outbox publish NACKed key={routing_key}")
        except DeliveryError as err:
            self._metrics.inc(
                "autopulse_publish_unroutable_total",
                routing_key=routing_key,
            )
            raise PublishError(
                f"Unroutable outbox message for key={routing_key}"
            ) from err
        self._metrics.inc("autopulse_publish_ok_total", routing_key=routing_key)
