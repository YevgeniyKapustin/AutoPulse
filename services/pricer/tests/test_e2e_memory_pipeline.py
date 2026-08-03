"""In-memory end-to-end: enrich then price."""

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


class FakePublisher:
    def __init__(self) -> None:
        self.raw: list[object] = []
        self.enriched: list[object] = []
        self.failed: list[object] = []

    async def publish_raw(self, event: object) -> None:
        self.raw.append(event)

    async def publish_enriched(self, event: object) -> None:
        self.enriched.append(event)

    async def publish_failed(self, event: object) -> None:
        self.failed.append(event)


class QuietCv(CvService):
    def _detect_sync(self, listing: RawListing) -> list:
        return []


@pytest.mark.asyncio
async def test_raw_to_enriched_to_priced() -> None:
    enrichment_settings = EnrichmentSettings(llm_api_key="")
    listing_repo = InMemoryListingRepository()
    publisher = FakePublisher()
    orchestrator = EnrichmentOrchestrator(
        repository=listing_repo,
        llm=LlmService(enrichment_settings, breaker=CircuitBreaker()),
        cv=QuietCv(),
        publisher=publisher,
    )
    raw = RawListing(
        external_id="e2e-1",
        description="M-Sport, panorama, one owner",
        asking_price=18_500,
    )
    enriched = await orchestrator.enrich(raw, event_id="evt-e2e")
    assert enriched.is_fully_enriched
    assert len(publisher.enriched) == 1

    pricer = PricingService(
        PricerSettings(default_target_margin_pct=12.0),
        InMemoryPricingRepository(),
    )
    priced = await pricer.price(enriched)
    assert priced.external_id == "e2e-1"
    assert priced.recommended_dealer_bid > 0
    assert priced.estimated_turnover_days >= 21
