"""Coordinates pricing engine evaluation and persistence."""

from __future__ import annotations

import logging
from typing import Protocol

from autopulse_shared.schemas.listing import EnrichedListing
from autopulse_shared.schemas.pricing import PricingResult
from services.pricer.app.core.config import Settings
from services.pricer.app.services.engine_factory import build_pricing_engine
from services.pricer.app.services.pricing_engine import PricingEngine

logger = logging.getLogger(__name__)


class PricingStore(Protocol):
    async def save(self, result: PricingResult) -> None: ...

    async def get(self, external_id: str) -> PricingResult: ...


class PricingService:
    def __init__(
        self,
        settings: Settings,
        repository: PricingStore,
        engine: PricingEngine | None = None,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._engine = engine or build_pricing_engine(settings)

    async def price(self, listing: EnrichedListing) -> PricingResult:
        result = self._engine.evaluate(listing)
        await self._repository.save(result)
        logger.info(
            "Priced %s bid=%.2f turnover=%s engine=%s",
            result.external_id,
            result.recommended_dealer_bid,
            result.estimated_turnover_days,
            result.model_version,
        )
        return result

    async def get_result(self, external_id: str) -> PricingResult:
        return await self._repository.get(external_id)
