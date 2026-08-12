"""Unit tests for orchestrator resume and re-enrich policy."""

from __future__ import annotations

import pytest
from services.enrichment.app.enrichment.orchestrator import EnrichmentOrchestrator
from services.enrichment.app.repositories.memory import InMemoryListingRepository

from autopulse_shared.schemas.events import ListingEnrichedEvent, RawListingEvent
from autopulse_shared.schemas.listing import (
    EnrichedListing,
    ListingOptions,
    RawListing,
)


class FakePublisher:
    def __init__(self) -> None:
        self.raw: list[RawListingEvent] = []
        self.enriched: list[ListingEnrichedEvent] = []
        self.failed: list[object] = []

    async def publish_raw(self, event: RawListingEvent) -> None:
        self.raw.append(event)

    async def publish_enriched(self, event: ListingEnrichedEvent) -> None:
        self.enriched.append(event)

    async def publish_failed(self, event: object) -> None:
        self.failed.append(event)


class QuietCv:
    def __init__(self) -> None:
        self.calls = 0

    async def detect_defects(self, listing: RawListing) -> list[object]:
        self.calls += 1
        return []

    async def aclose(self) -> None:
        return None


class HeuristicLlm:
    def __init__(self) -> None:
        self.calls = 0

    async def extract_options(self, listing: RawListing) -> ListingOptions:
        self.calls += 1
        return ListingOptions(packages=["AMG"], features=["harman_kardon"])

    async def aclose(self) -> None:
        return None


class FlakyCv:
    def __init__(self) -> None:
        self.calls = 0

    async def detect_defects(self, listing: RawListing) -> list[object]:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("cv down")
        return []

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_enrich_marks_llm_and_cv_done() -> None:
    repo = InMemoryListingRepository()
    publisher = FakePublisher()
    llm = HeuristicLlm()
    orchestrator = EnrichmentOrchestrator(
        repository=repo,
        llm=llm,
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
    repo = InMemoryListingRepository()
    publisher = FakePublisher()
    orchestrator = EnrichmentOrchestrator(
        repository=repo,
        llm=HeuristicLlm(),
        cv=QuietCv(),
        publisher=publisher,
    )
    listing = RawListing(external_id="car-99", description="test")
    event_id = await orchestrator.enqueue_raw(listing, request_id="req-1")
    assert event_id
    assert len(publisher.raw) == 1
    await repo.get("car-99")


@pytest.mark.asyncio
async def test_partial_stage_persists_when_peer_fails() -> None:
    repo = InMemoryListingRepository()
    publisher = FakePublisher()
    llm = HeuristicLlm()
    cv = FlakyCv()
    orchestrator = EnrichmentOrchestrator(
        repository=repo,
        llm=llm,
        cv=cv,
        publisher=publisher,
    )
    listing = RawListing(external_id="car-partial", description="AMG")

    with pytest.raises(RuntimeError, match="cv down"):
        await orchestrator.enrich(listing, event_id="evt-partial")

    stored = await repo.get("car-partial")
    assert stored.llm_done is True
    assert stored.cv_done is False
    assert llm.calls == 1

    result = await orchestrator.enrich(listing, event_id="evt-partial-2")
    assert result.is_fully_enriched
    assert llm.calls == 1  # resumed; LLM not re-run
    assert cv.calls == 2
    assert len(publisher.enriched) == 1


@pytest.mark.asyncio
async def test_unchanged_fully_enriched_skips_stages() -> None:
    repo = InMemoryListingRepository()
    publisher = FakePublisher()
    llm = HeuristicLlm()
    cv = QuietCv()
    orchestrator = EnrichmentOrchestrator(
        repository=repo,
        llm=llm,
        cv=cv,
        publisher=publisher,
    )
    listing = RawListing(external_id="car-same", description="AMG")
    await orchestrator.enrich(listing, event_id="evt-a")
    await orchestrator.enrich(listing, event_id="evt-b")

    assert llm.calls == 1
    assert cv.calls == 1
    assert len(publisher.enriched) == 2


@pytest.mark.asyncio
async def test_changed_payload_re_enriches() -> None:
    repo = InMemoryListingRepository()
    publisher = FakePublisher()
    llm = HeuristicLlm()
    cv = QuietCv()
    orchestrator = EnrichmentOrchestrator(
        repository=repo,
        llm=llm,
        cv=cv,
        publisher=publisher,
    )
    await orchestrator.enrich(
        RawListing(external_id="car-chg", description="AMG"),
        event_id="evt-1",
    )
    await orchestrator.enrich(
        RawListing(external_id="car-chg", description="AMG, panorama"),
        event_id="evt-2",
    )

    assert llm.calls == 2
    assert cv.calls == 2
    assert len(publisher.enriched) == 2
