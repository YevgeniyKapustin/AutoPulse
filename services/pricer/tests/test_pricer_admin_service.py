"""Unit tests for pricer admin overview."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from services.pricer.app.admin.service import PricerAdminService
from services.pricer.app.repositories.memory import InMemoryPricingRepository

from autopulse_shared.schemas.pricing import PricingResult


@pytest.mark.asyncio
async def test_pricer_admin_overview_and_list() -> None:
    repo = InMemoryPricingRepository()
    await repo.save(
        PricingResult(
            external_id="p1",
            bid_price=1000,
            recommended_dealer_bid=880,
            estimated_turnover_days=20,
            target_margin_pct=12,
            price_low=800,
            price_high=950,
            priced_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )
    await repo.mark_completed("evt-1")

    async def readiness() -> tuple[bool, dict[str, str]]:
        return True, {"mysql": "ok"}

    admin = PricerAdminService(repo, readiness_probe=readiness)
    overview = await admin.overview()
    assert overview.ready is True
    assert overview.priced_total == 1
    assert overview.inbox["completed"] == 1
    assert overview.outbox["pending"] == 1

    page = await admin.list_pricing(limit=10)
    assert len(page.items) == 1
    assert page.items[0].external_id == "p1"
