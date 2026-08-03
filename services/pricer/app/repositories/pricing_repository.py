"""SQLAlchemy async repository for pricing results (stub)."""

from __future__ import annotations

from autopulse_shared.schemas.pricing import PricingResult


class PricingRepository:
    async def save(self, result: PricingResult) -> None:
        # TODO(week-2): persist via SQLAlchemy async session to MySQL
        _ = result

    async def get(self, external_id: str) -> PricingResult:
        raise NotImplementedError(f"Pricing for {external_id} not stored yet")
