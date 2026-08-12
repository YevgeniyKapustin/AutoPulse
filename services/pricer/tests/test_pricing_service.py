"""Unit tests for pricing service persistence."""

from __future__ import annotations

import pytest
from services.pricer.app.consumers.enriched_listing_consumer import (
    EnrichedListingConsumer,
)
from services.pricer.app.core.config import Settings
from services.pricer.app.core.exceptions import PricingNotFoundError
from services.pricer.app.repositories.memory import InMemoryPricingRepository
from services.pricer.app.services.engine_factory import build_pricing_engine
from services.pricer.app.services.pricing_service import PricingService

from autopulse_shared.schemas.events import ListingEnrichedEvent
from autopulse_shared.schemas.listing import EnrichedListing, ListingSource


def _service(
    repo: InMemoryPricingRepository | None = None,
) -> tuple[
    PricingService,
    InMemoryPricingRepository,
]:
    settings = Settings(default_target_margin_pct=10.0, default_turnover_days=14)
    repository = repo or InMemoryPricingRepository()
    return PricingService(repository, build_pricing_engine(settings)), repository


@pytest.mark.asyncio
async def test_pricing_service_persists_result() -> None:
    service, _repo = _service()
    listing = EnrichedListing(
        external_id="car-77",
        source=ListingSource.MANUAL,
        asking_price=10_000,
        llm_done=True,
        cv_done=True,
    )
    result = await service.price(listing)
    stored = await service.get_result("car-77")
    assert stored.recommended_dealer_bid == result.recommended_dealer_bid
    assert stored.estimated_turnover_days == 14


@pytest.mark.asyncio
async def test_evaluate_does_not_persist() -> None:
    service, repo = _service()
    listing = EnrichedListing(
        external_id="car-eval",
        source=ListingSource.MANUAL,
        asking_price=10_000,
        llm_done=True,
        cv_done=True,
    )
    result = service.evaluate(listing)
    assert result.recommended_dealer_bid > 0
    with pytest.raises(PricingNotFoundError):
        await repo.get("car-eval")


@pytest.mark.asyncio
async def test_consumer_handle_message_prices_listing() -> None:
    service, repo = _service()
    consumer = EnrichedListingConsumer(
        Settings(default_target_margin_pct=10.0),
        service,
        inbox=repo,
    )
    event = ListingEnrichedEvent(
        event_id="evt-9",
        listing=EnrichedListing(
            external_id="car-88",
            source=ListingSource.MANUAL,
            asking_price=20_000,
            llm_done=True,
            cv_done=True,
        ),
    )
    await consumer.handle_message(event.model_dump_json().encode("utf-8"))
    stored = await repo.get("car-88")
    assert stored.bid_price == 20_000
    assert repo._inbox["evt-9"] == "completed"
