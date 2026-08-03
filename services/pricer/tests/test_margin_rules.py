from autopulse_shared.schemas.listing import EnrichedListing, ListingSource
from services.pricer.app.core.config import Settings
from services.pricer.app.services.margin_rules import MarginRuleEngine


def test_margin_rule_applies_defect_penalty() -> None:
    settings = Settings(default_target_margin_pct=10.0, default_turnover_days=14)
    engine = MarginRuleEngine(settings)
    listing = EnrichedListing(
        external_id="car-1",
        source=ListingSource.MANUAL,
        asking_price=10_000,
        currency="USD",
    )
    result = engine.evaluate(listing)
    assert result.recommended_dealer_bid == 9000.0
    assert result.estimated_turnover_days == 14
