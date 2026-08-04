import pytest
from services.enrichment.app.core.config import Settings
from services.enrichment.app.repositories.memory import InMemoryListingRepository
from services.enrichment.app.cv import CvService
from services.enrichment.app.enrichment.orchestrator import (
    EnrichmentOrchestrator,
)
from services.enrichment.app.llm import LlmService

from autopulse_shared.schemas.events import (
    EnrichmentFailedEvent,
    ListingEnrichedEvent,
    RawListingEvent,
)
from autopulse_shared.schemas.listing import ListingSource, RawListing


class FakePublisher:
    def __init__(self) -> None:
        self.raw: list[RawListingEvent] = []
        self.enriched: list[ListingEnrichedEvent] = []
        self.failed: list[EnrichmentFailedEvent] = []

    async def publish_raw(self, event: RawListingEvent) -> None:
        self.raw.append(event)

    async def publish_enriched(self, event: ListingEnrichedEvent) -> None:
        self.enriched.append(event)

    async def publish_failed(self, event: EnrichmentFailedEvent) -> None:
        self.failed.append(event)


@pytest.fixture
def settings() -> Settings:
    return Settings(llm_api_key="")


@pytest.mark.asyncio
async def test_llm_heuristic_extracts_options(settings: Settings) -> None:
    llm = LlmService(settings)
    listing = RawListing(
        external_id="car-1",
        source=ListingSource.MANUAL,
        title="BMW 320i",
        description="M-Sport package, panorama roof, one owner",
    )
    options = await llm.extract_options(listing)
    assert "M-Sport" in options.packages
    assert "panorama" in options.features
    assert options.owner_count == 1


@pytest.mark.asyncio
async def test_orchestrator_enriches_and_publishes(settings: Settings) -> None:
    repo = InMemoryListingRepository()
    publisher = FakePublisher()
    orchestrator = EnrichmentOrchestrator(
        repository=repo,
        llm=LlmService(settings),
        cv=CvService(),
        publisher=publisher,
    )
    listing = RawListing(
        external_id="car-2",
        source=ListingSource.MANUAL,
        description="Harman Kardon, leather",
        asking_price=12000,
    )
    result = await orchestrator.enrich(listing, event_id="evt-1")
    assert result.is_fully_enriched
    assert "harman_kardon" in result.options.features
    assert len(publisher.enriched) == 1
    stored = await repo.get("car-2")
    assert stored.llm_done and stored.cv_done


@pytest.mark.asyncio
async def test_enqueue_publishes_raw_event(settings: Settings) -> None:
    repo = InMemoryListingRepository()
    publisher = FakePublisher()
    orchestrator = EnrichmentOrchestrator(
        repository=repo,
        llm=LlmService(settings),
        cv=CvService(),
        publisher=publisher,
    )
    listing = RawListing(external_id="car-3", source=ListingSource.MANUAL)
    event_id = await orchestrator.enqueue_raw(listing, request_id="req-1")
    assert event_id
    assert len(publisher.raw) == 1
    assert publisher.raw[0].request_id == "req-1"


def test_cv_inspect_dark_image() -> None:
    from io import BytesIO

    from PIL import Image
    from pydantic import HttpUrl

    from services.enrichment.app.cv.analyzer import ImageAnalyzer

    buf = BytesIO()
    Image.new("RGB", (64, 64), color=(5, 5, 5)).save(buf, format="JPEG")
    defects = ImageAnalyzer().inspect(
        buf.getvalue(),
        HttpUrl("https://example.com/dark.jpg"),
    )
    assert any(d.label == "very_dark_image" for d in defects)
