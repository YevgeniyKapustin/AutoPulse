"""In-memory pricing repository for unit tests."""

from __future__ import annotations

from autopulse_shared.schemas.pricing import PricingResult
from services.pricer.app.core.exceptions import PricingNotFoundError


class InMemoryPricingRepository:
    def __init__(self) -> None:
        self._items: dict[str, PricingResult] = {}
        self._claimed: set[str] = set()
        self.outbox: list[tuple[str, str]] = []

    async def try_claim_event(self, event_id: str) -> bool:
        if event_id in self._claimed:
            return False
        self._claimed.add(event_id)
        return True

    async def save(self, result: PricingResult, *, event_id: str | None = None) -> None:
        self._items[result.external_id] = result.model_copy(deep=True)
        self.outbox.append((event_id or result.external_id, result.external_id))

    async def get(self, external_id: str) -> PricingResult:
        if external_id not in self._items:
            raise PricingNotFoundError(external_id)
        return self._items[external_id].model_copy(deep=True)
