import pytest
from services.pricer.app.core.config import Settings
from services.pricer.app.repositories.memory import InMemoryPricingRepository
from services.pricer.app.services.engine_factory import build_pricing_engine
from services.pricer.app.services.pricing_service import PricingService

from autopulse_shared.schemas.listing import EnrichedListing, ListingSource


def test_factory_defaults_to_rules() -> None:
    engine = build_pricing_engine(Settings(pricing_engine="rules"))
    listing = EnrichedListing(
        external_id="r1",
        source=ListingSource.MANUAL,
        asking_price=10_000,
    )
    result = engine.evaluate(listing)
    assert result.model_version == "rules-v0"
    assert result.recommended_dealer_bid == 8800.0


def test_sklearn_engine_returns_positive_bid() -> None:
    engine = build_pricing_engine(Settings(pricing_engine="sklearn"))
    listing = EnrichedListing(
        external_id="s1",
        source=ListingSource.MANUAL,
        asking_price=18_500,
        year=2019,
        mileage_km=70_000,
        llm_done=True,
        cv_done=True,
    )
    result = engine.evaluate(listing)
    assert result.model_version.startswith("sklearn")
    assert result.recommended_dealer_bid > 0
    assert result.price_low <= result.recommended_dealer_bid <= result.price_high


@pytest.mark.asyncio
async def test_pricing_service_with_sklearn_engine() -> None:
    settings = Settings(pricing_engine="sklearn")
    service = PricingService(
        InMemoryPricingRepository(),
        build_pricing_engine(settings),
    )
    listing = EnrichedListing(
        external_id="s2",
        source=ListingSource.MANUAL,
        asking_price=12_000,
        year=2018,
        mileage_km=90_000,
    )
    stored = await service.price(listing)
    assert stored.external_id == "s2"
    assert (await service.get_result("s2")).recommended_dealer_bid > 0
