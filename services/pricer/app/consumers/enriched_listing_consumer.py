from __future__ import annotations

import logging
from typing import Any

from services.pricer.app.core.config import Settings
from services.pricer.app.services.pricing_service import PricingService

logger = logging.getLogger(__name__)


class EnrichedListingConsumer:
    """Consumes car.enriched.success and runs margin rule engine."""

    def __init__(self, settings: Settings, pricing: PricingService) -> None:
        self._settings = settings
        self._pricing = pricing
        self._connection: Any = None

    async def start(self) -> None:
        # TODO(week-2): aio_pika bind to routing_key_enriched_success
        logger.info(
            "EnrichedListingConsumer started (stub). key=%s",
            self._settings.routing_key_enriched_success,
        )

    async def stop(self) -> None:
        logger.info("EnrichedListingConsumer stopped")

    async def handle_message(self, body: bytes) -> None:
        raise NotImplementedError("Implement in week-2 pricer worker")
