"""Publish pricer outbox messages with confirms."""

from __future__ import annotations

import json
import logging
from typing import Any, cast

import aio_pika
from aio_pika.abc import AbstractExchange
from aio_pika.exceptions import DeliveryError
from pamqp.commands import Basic

from services.pricer.app.core.metrics import METRICS
from services.pricer.app.repositories.pricing_repository import PricingRepository

logger = logging.getLogger(__name__)


class PublishError(RuntimeError):
    pass


class OutboxPublisher:
    def __init__(
        self,
        exchange: AbstractExchange,
        repository: PricingRepository,
    ) -> None:
        self._exchange = exchange
        self._repository = repository

    async def drain(self, limit: int = 50) -> int:
        pending = await self._repository.list_pending_outbox(limit=limit)
        snapshots = [
            (
                row.id,
                row.routing_key,
                row.payload.encode("utf-8"),
                json.loads(row.headers_json or "{}"),
            )
            for row in pending
        ]
        published = 0
        for outbox_id, routing_key, body, headers in snapshots:
            if not isinstance(headers, dict):
                headers = {}
            await self._publish_message(body, routing_key, headers)
            await self._repository.mark_outbox_published(outbox_id)
            published += 1
        if published:
            logger.info("Drained pricer outbox count=%s", published)
        return published

    async def _publish_message(
        self,
        body: bytes,
        routing_key: str,
        headers: dict[str, Any],
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
            if isinstance(confirmation, (Basic.Nack, Basic.Reject)):
                METRICS.inc("autopulse_publish_nack_total", routing_key=routing_key)
                raise PublishError(f"Outbox publish NACKed key={routing_key}")
        except DeliveryError as err:
            METRICS.inc(
                "autopulse_publish_unroutable_total",
                routing_key=routing_key,
            )
            raise PublishError(
                f"Unroutable outbox message for key={routing_key}"
            ) from err
        METRICS.inc("autopulse_publish_ok_total", routing_key=routing_key)
