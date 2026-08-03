"""RabbitMQ consumer for car.raw.created — ack only after full aggregation."""

from __future__ import annotations

import logging
from typing import Any

from services.enrichment.app.core.config import Settings

logger = logging.getLogger(__name__)


class RawListingConsumer:
    """Skeleton consumer. Wire aio_pika in week-1 implementation."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._connection: Any = None
        self._channel: Any = None

    async def start(self) -> None:
        # TODO(week-1): connect via aio_pika, declare topic exchange,
        # queue with DLQ, bind routing_key_raw_created, start consume loop.
        logger.info(
            "RawListingConsumer started (stub). exchange=%s key=%s",
            self._settings.rabbitmq_exchange,
            self._settings.routing_key_raw_created,
        )

    async def stop(self) -> None:
        logger.info("RawListingConsumer stopped")

    async def handle_message(self, body: bytes) -> None:
        """Parse RawListingEvent, run enrichment, ack on aggregation complete."""
        raise NotImplementedError("Implement in week-1 enrichment worker")
