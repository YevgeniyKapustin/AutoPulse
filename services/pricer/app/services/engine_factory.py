"""Build the configured pricing engine (rules or sklearn)."""

from __future__ import annotations

from services.pricer.app.core.config import Settings
from services.pricer.app.services.margin_rules import MarginRuleEngine
from services.pricer.app.services.pricing_engine import PricingEngine


def build_pricing_engine(settings: Settings) -> PricingEngine:
    if settings.pricing_engine == "sklearn":
        from services.pricer.app.services.sklearn_engine import SklearnPricingEngine

        return SklearnPricingEngine(settings)
    return MarginRuleEngine(settings)
