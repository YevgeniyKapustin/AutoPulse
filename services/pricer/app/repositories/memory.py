"""In-memory pricing repository for unit tests."""

from __future__ import annotations

from autopulse_shared.schemas.pricing import PricingResult
from services.pricer.app.core.exceptions import PricingNotFoundError


class InMemoryPricingRepository:
    def __init__(self) -> None:
        self._items: dict[str, PricingResult] = {}

    async def save(self, result: PricingResult) -> None:
        self._items[result.external_id] = result.model_copy(deep=True)

    async def get(self, external_id: str) -> PricingResult:
        if external_id not in self._items:
            raise PricingNotFoundError(external_id)
        return self._items[external_id].model_copy(deep=True)
