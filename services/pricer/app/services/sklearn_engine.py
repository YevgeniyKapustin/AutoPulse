"""Sklearn Ridge pricing engine behind the PricingEngine protocol."""

from __future__ import annotations

import logging

import numpy as np
from sklearn.linear_model import Ridge

from autopulse_shared.schemas.listing import (
    DefectInfo,
    EnrichedListing,
    ListingOptions,
)
from autopulse_shared.schemas.pricing import PricingResult
from services.pricer.app.core.config import Settings
from services.pricer.app.services.margin_rules import MarginRuleEngine

logger = logging.getLogger(__name__)


class SklearnPricingEngine:
    """Fits a tiny Ridge model on synthetic rule-engine labels at startup."""

    model_version = "sklearn-ridge-v0"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._rules = MarginRuleEngine(settings)
        self._model = Ridge(alpha=1.0)
        self._fit_synthetic()

    def _fit_synthetic(self) -> None:
        samples: list[EnrichedListing] = []
        targets: list[float] = []
        rng = np.random.default_rng(42)
        for i in range(80):
            ask = float(rng.integers(5_000, 40_000))
            defects = [
                DefectInfo(label="dent", confidence=0.7)
                for _ in range(int(rng.integers(0, 4)))
            ]
            features = [f"f{j}" for j in range(int(rng.integers(0, 6)))]
            listing = EnrichedListing(
                external_id=f"synth-{i}",
                asking_price=ask,
                year=int(rng.integers(2012, 2024)),
                mileage_km=int(rng.integers(10_000, 180_000)),
                options=ListingOptions(features=features),
                defects=defects,
                llm_done=True,
                cv_done=True,
            )
            label = self._rules.evaluate(listing).recommended_dealer_bid
            samples.append(listing)
            targets.append(label)
        matrix = np.vstack([self._features(item) for item in samples])
        self._model.fit(matrix, np.asarray(targets))
        logger.info("SklearnPricingEngine fitted on %s synthetic rows", len(samples))

    def evaluate(self, listing: EnrichedListing) -> PricingResult:
        ask = listing.asking_price or 0.0
        predicted = float(
            self._model.predict(self._features(listing).reshape(1, -1))[0]
        )
        recommended = max(0.0, round(predicted, 2))
        margin = 0.0 if ask <= 0 else round((1.0 - recommended / ask) * 100, 2)
        turnover = self._settings.default_turnover_days + (3 * len(listing.defects))
        return PricingResult(
            external_id=listing.external_id,
            bid_price=ask,
            recommended_dealer_bid=recommended,
            estimated_turnover_days=turnover,
            target_margin_pct=margin,
            price_low=round(recommended * 0.95, 2),
            price_high=round(recommended * 1.05, 2),
            currency=listing.currency,
            model_version=self.model_version,
            meta={"engine": "sklearn", "features": self._features(listing).tolist()},
        )

    @staticmethod
    def _features(listing: EnrichedListing) -> np.ndarray:
        return np.asarray(
            [
                float(listing.asking_price or 0.0),
                float(listing.year or 0),
                float(listing.mileage_km or 0),
                float(len(listing.defects)),
                float(len(listing.options.features)),
                float(len(listing.options.packages)),
            ],
            dtype=float,
        )
