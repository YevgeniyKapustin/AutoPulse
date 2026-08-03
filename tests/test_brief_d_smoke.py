"""In-process smoke: fixture → enrich → price (no Docker)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autopulse_shared.schemas.listing import RawListing
from services.enrichment.app.core.circuit_breaker import CircuitBreaker
from services.enrichment.app.core.config import Settings as EnrichmentSettings
from services.enrichment.app.repositories.memory import InMemoryListingRepository
from services.enrichment.app.services.cv_service import CvService
from services.enrichment.app.services.enrichment_orchestrator import (
    EnrichmentOrchestrator,
)
from services.enrichment.app.services.llm_service import LlmService
from services.pricer.app.core.config import Settings as PricerSettings
from services.pricer.app.repositories.memory import InMemoryPricingRepository
from services.pricer.app.services.pricing_service import PricingService

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "docs" / "fixtures" / "raw_listing_sample.json"


class FakePublisher:
    def __init__(self) -> None:
        self.enriched: list[object] = []

    async def publish_raw(self, event: object) -> None:
        return None

    async def publish_enriched(self, event: object) -> None:
        self.enriched.append(event)

    async def publish_failed(self, event: object) -> None:
        return None


class QuietCv(CvService):
    def _detect_sync(self, listing: RawListing) -> list:
        return []


@pytest.mark.asyncio
async def test_brief_d_fixture_enrich_then_price() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw = RawListing.model_validate(payload)
    orchestrator = EnrichmentOrchestrator(
        repository=InMemoryListingRepository(),
        llm=LlmService(EnrichmentSettings(llm_api_key=""), CircuitBreaker()),
        cv=QuietCv(),
        publisher=FakePublisher(),
    )
    enriched = await orchestrator.enrich(raw, event_id="smoke-1")
    assert enriched.is_fully_enriched
    assert "M-Sport" in enriched.options.packages

    priced = await PricingService(
        PricerSettings(),
        InMemoryPricingRepository(),
    ).price(enriched)
    assert priced.external_id == raw.external_id
    assert priced.recommended_dealer_bid > 0
