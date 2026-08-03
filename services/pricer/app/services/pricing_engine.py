"""Pricing engine protocol shared by rules and ML backends."""

from __future__ import annotations

from typing import Protocol

from autopulse_shared.schemas.listing import EnrichedListing
from autopulse_shared.schemas.pricing import PricingResult


class PricingEngine(Protocol):
    def evaluate(self, listing: EnrichedListing) -> PricingResult: ...
