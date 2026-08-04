import pytest
from services.enrichment.app.core.circuit_breaker import CircuitBreaker
from services.enrichment.app.core.config import Settings
from services.enrichment.app.repositories.memory import InMemoryListingRepository
from services.enrichment.app.cv import CvService
from services.enrichment.app.enrichment.orchestrator import (
    EnrichmentOrchestrator,
)
from services.enrichment.app.llm import LlmService

from autopulse_shared.schemas.events import ListingEnrichedEvent, RawListingEvent
from autopulse_shared.schemas.listing import EnrichedListing, RawListing


class FakePublisher:
    def __init__(self) -> None:
        self.raw: list[RawListingEvent] = []
        self.enriched: list[ListingEnrichedEvent] = []

    async def publish_raw(self, event: RawListingEvent) -> None:
        self.raw.append(event)

    async def publish_enriched(self, event: ListingEnrichedEvent) -> None:
        self.enriched.append(event)

    async def publish_failed(self, event: object) -> None:
        return None


class QuietCv(CvService):
    async def detect_defects(self, listing: RawListing) -> list:
        return []


@pytest.mark.asyncio
async def test_enrich_marks_llm_and_cv_done() -> None:
    settings = Settings(llm_api_key="")
    repo = InMemoryListingRepository()
    publisher = FakePublisher()
    orchestrator = EnrichmentOrchestrator(
        repository=repo,
        llm=LlmService(settings, breaker=CircuitBreaker()),
        cv=QuietCv(),
        publisher=publisher,
    )
    listing = RawListing(
        external_id="car-42",
        description="AMG package, Harman Kardon",
        asking_price=20000,
    )
    result = await orchestrator.enrich(listing, event_id="evt-1")
    assert result.llm_done is True
    assert result.cv_done is True
    assert result.is_fully_enriched
    assert "AMG" in result.options.packages
    stored = await repo.get("car-42")
    assert isinstance(stored, EnrichedListing)
    assert stored.is_fully_enriched
    assert len(publisher.enriched) == 1


@pytest.mark.asyncio
async def test_enqueue_publishes_raw_event() -> None:
    settings = Settings(llm_api_key="")
    repo = InMemoryListingRepository()
    publisher = FakePublisher()
    orchestrator = EnrichmentOrchestrator(
        repository=repo,
        llm=LlmService(settings, breaker=CircuitBreaker()),
        cv=QuietCv(),
        publisher=publisher,
    )
    listing = RawListing(external_id="car-99", description="test")
    event_id = await orchestrator.enqueue_raw(listing, request_id="req-1")
    assert event_id
    assert len(publisher.raw) == 1
    await repo.get("car-99")
