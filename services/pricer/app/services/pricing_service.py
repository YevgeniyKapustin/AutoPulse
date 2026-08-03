"""Coordinates margin rules and pricing persistence."""

from __future__ import annotations

import logging
from typing import Protocol

from autopulse_shared.schemas.listing import EnrichedListing
from autopulse_shared.schemas.pricing import PricingResult
from services.pricer.app.core.config import Settings
from services.pricer.app.services.margin_rules import MarginRuleEngine

logger = logging.getLogger(__name__)


class PricingStore(Protocol):
    async def save(self, result: PricingResult) -> None: ...

    async def get(self, external_id: str) -> PricingResult: ...


class PricingService:
    def __init__(
        self,
        settings: Settings,
        repository: PricingStore,
        rules: MarginRuleEngine | None = None,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._rules = rules or MarginRuleEngine(settings)

    async def price(self, listing: EnrichedListing) -> PricingResult:
        result = self._rules.evaluate(listing)
        await self._repository.save(result)
        logger.info(
            "Priced %s bid=%.2f turnover=%s",
            result.external_id,
            result.recommended_dealer_bid,
            result.estimated_turnover_days,
        )
        return result

    async def get_result(self, external_id: str) -> PricingResult:
        return await self._repository.get(external_id)
