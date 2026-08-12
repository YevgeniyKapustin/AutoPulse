"""Coordinates pricing engine evaluation and persistence."""

from __future__ import annotations

import logging

from autopulse_shared.schemas.listing import EnrichedListing
from autopulse_shared.schemas.pricing import PricingResult
from services.pricer.app.services.ports import PricingStore
from services.pricer.app.services.pricing_engine import PricingEngine

logger = logging.getLogger(__name__)


class PricingService:
    def __init__(
        self,
        repository: PricingStore,
        engine: PricingEngine,
    ) -> None:
        self._repository = repository
        self._engine = engine

    def evaluate(self, listing: EnrichedListing) -> PricingResult:
        """Pure evaluation — no persistence or outbox side effects."""
        return self._engine.evaluate(listing)

    async def price(
        self,
        listing: EnrichedListing,
        *,
        event_id: str | None = None,
        request_id: str | None = None,
    ) -> PricingResult:
        result = self.evaluate(listing)
        await self._repository.save(
            result,
            event_id=event_id,
            request_id=request_id,
        )
        logger.info(
            "Priced %s bid=%.2f turnover=%s engine=%s",
            result.external_id,
            result.recommended_dealer_bid,
            result.estimated_turnover_days,
            result.model_version,
            extra={"event_id": event_id, "external_id": result.external_id},
        )
        return result

    async def get_result(self, external_id: str) -> PricingResult:
        return await self._repository.get(external_id)
