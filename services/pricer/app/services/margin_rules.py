"""Margin Rule Engine — deterministic baseline for week-2."""

from __future__ import annotations

from autopulse_shared.schemas.listing import EnrichedListing
from autopulse_shared.schemas.pricing import PricingResult
from services.pricer.app.core.config import Settings


class MarginRuleEngine:
    def __init__(self, settings: Settings) -> None:
        self._margin_pct = settings.default_target_margin_pct
        self._turnover_days = settings.default_turnover_days

    def evaluate(self, listing: EnrichedListing) -> PricingResult:
        ask = listing.asking_price or 0.0
        defect_penalty = min(0.15, 0.03 * len(listing.defects))
        option_bonus = min(0.08, 0.01 * len(listing.options.features))

        effective_margin = self._margin_pct / 100.0 + defect_penalty - option_bonus
        recommended = ask * (1.0 - effective_margin) if ask else 0.0
        price_low = recommended * 0.95
        price_high = recommended * 1.05
        turnover = self._turnover_days + (3 * len(listing.defects))

        return PricingResult(
            external_id=listing.external_id,
            bid_price=ask,
            recommended_dealer_bid=round(recommended, 2),
            estimated_turnover_days=turnover,
            target_margin_pct=round(effective_margin * 100, 2),
            price_low=round(price_low, 2),
            price_high=round(price_high, 2),
            currency=listing.currency,
            meta={
                "defect_penalty": defect_penalty,
                "option_bonus": option_bonus,
            },
        )
