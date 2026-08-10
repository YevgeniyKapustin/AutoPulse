"""Unit tests for enrichment admin service."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from services.enrichment.app.admin.schemas import QueueDepths
from services.enrichment.app.admin.service import AdminService
from services.enrichment.app.core.config import Settings
from services.enrichment.app.core.exceptions import ListingNotFoundError
from services.enrichment.app.repositories.memory import InMemoryListingRepository

from autopulse_shared.schemas.listing import EnrichedListing, RawListing
from autopulse_shared.schemas.pricing import PricingResult


class _StatusCounts:
    def __init__(self, counts: dict[str, int]) -> None:
        self._counts = counts

    async def count_by_status(self) -> dict[str, int]:
        return dict(self._counts)


class _QueueProbe:
    def __init__(self, depths: dict[str, int | None]) -> None:
        self._depths = depths

    async def depths(self, queue_names: list[str]) -> dict[str, int | None]:
        return {name: self._depths.get(name) for name in queue_names}


class _PricerClient:
    def __init__(
        self,
        *,
        overview: dict[str, object] | None = None,
        pricing: PricingResult | None = None,
    ) -> None:
        self._overview = overview
        self._pricing = pricing

    async def overview(self) -> dict[str, object] | None:
        return self._overview

    async def get_pricing(self, external_id: str) -> PricingResult | None:
        if self._pricing is None or self._pricing.external_id != external_id:
            return None
        return self._pricing


class _ReEnricher:
    def __init__(self) -> None:
        self.calls: list[tuple[RawListing, str | None]] = []

    async def enqueue_raw(
        self,
        listing: RawListing,
        request_id: str | None = None,
    ) -> str:
        self.calls.append((listing, request_id))
        return "evt-re"


@pytest.mark.asyncio
async def test_overview_partial_when_pricer_unreachable() -> None:
    listings = InMemoryListingRepository()
    await listings.upsert(
        EnrichedListing(external_id="c1", llm_done=True, cv_done=True)
    )
    await listings.upsert(EnrichedListing(external_id="c2"))
    settings = Settings(
        enrichment_queue_name="enrichment.raw",
        enrichment_retry_queue_name="enrichment.retry",
        enrichment_dlq_name="enrichment.dlq",
        pricer_queue_name="pricer.enriched",
        pricer_retry_queue_name="pricer.retry",
        pricer_dlq_name="pricer.dlq",
    )

    async def readiness() -> tuple[bool, dict[str, str]]:
        return True, {"mongodb": "ok", "rabbitmq": "ok"}

    admin = AdminService(
        settings=settings,
        listings=listings,
        inbox=_StatusCounts({"completed": 2, "processing": 0}),
        outbox=_StatusCounts({"pending": 1, "published": 3}),
        queues=_QueueProbe({"enrichment.raw": 4, "enrichment.dlq": 0}),
        pricer=_PricerClient(overview=None),
        re_enricher=_ReEnricher(),
        readiness_probe=readiness,
    )
    overview = await admin.overview()
    assert overview.listings_total == 2
    assert overview.listings_enriched == 1
    assert overview.listings_partial == 1
    assert overview.queues == QueueDepths(
        enrichment_raw=4,
        enrichment_retry=None,
        enrichment_dlq=0,
        pricer_work=None,
        pricer_retry=None,
        pricer_dlq=None,
    )
    assert overview.queue_alerts.bad_count == 0
    levels = {card.key: card.level for card in overview.queue_alerts.cards}
    assert levels["enrichment_raw"] == "ok"
    assert levels["enrichment_dlq"] == "ok"
    assert levels["enrichment_retry"] == "unknown"
    assert overview.pricer is None
    assert overview.readiness.pricer_ready is None


@pytest.mark.asyncio
async def test_overview_marks_dlq_bad() -> None:
    settings = Settings(
        enrichment_queue_name="enrichment.raw",
        enrichment_retry_queue_name="enrichment.retry",
        enrichment_dlq_name="enrichment.dlq",
        pricer_queue_name="pricer.enriched",
        pricer_retry_queue_name="pricer.retry",
        pricer_dlq_name="pricer.dlq",
        admin_dlq_warn_depth=0,
        admin_queue_warn_depth=100,
    )
    admin = AdminService(
        settings=settings,
        listings=InMemoryListingRepository(),
        inbox=_StatusCounts({}),
        outbox=_StatusCounts({}),
        queues=_QueueProbe({"enrichment.dlq": 2, "enrichment.raw": 150}),
        pricer=_PricerClient(overview=None),
        re_enricher=_ReEnricher(),
    )
    overview = await admin.overview()
    levels = {card.key: card.level for card in overview.queue_alerts.cards}
    assert levels["enrichment_dlq"] == "bad"
    assert levels["enrichment_raw"] == "bad"
    assert overview.queue_alerts.bad_count >= 2


@pytest.mark.asyncio
async def test_re_enrich_enqueues_existing_listing() -> None:
    listings = InMemoryListingRepository()
    await listings.upsert(EnrichedListing(external_id="car-1", description="AMG"))
    re_enricher = _ReEnricher()
    admin = AdminService(
        settings=Settings(),
        listings=listings,
        inbox=_StatusCounts({}),
        outbox=_StatusCounts({}),
        queues=_QueueProbe({}),
        pricer=_PricerClient(),
        re_enricher=re_enricher,
    )
    accepted = await admin.re_enrich("car-1", request_id="req-1")
    assert accepted.event_id == "evt-re"
    assert re_enricher.calls[0][0].external_id == "car-1"
    assert re_enricher.calls[0][1] == "req-1"


@pytest.mark.asyncio
async def test_re_enrich_missing_listing() -> None:
    admin = AdminService(
        settings=Settings(),
        listings=InMemoryListingRepository(),
        inbox=_StatusCounts({}),
        outbox=_StatusCounts({}),
        queues=_QueueProbe({}),
        pricer=_PricerClient(),
        re_enricher=_ReEnricher(),
    )
    with pytest.raises(ListingNotFoundError):
        await admin.re_enrich("missing")


@pytest.mark.asyncio
async def test_pipeline_includes_optional_pricing() -> None:
    listings = InMemoryListingRepository()
    await listings.upsert(EnrichedListing(external_id="car-9", llm_done=True))
    priced = PricingResult(
        external_id="car-9",
        bid_price=1000,
        recommended_dealer_bid=880,
        estimated_turnover_days=21,
        target_margin_pct=12,
        price_low=800,
        price_high=950,
        priced_at=datetime.now(UTC),
    )
    admin = AdminService(
        settings=Settings(),
        listings=listings,
        inbox=_StatusCounts({}),
        outbox=_StatusCounts({}),
        queues=_QueueProbe({}),
        pricer=_PricerClient(pricing=priced),
        re_enricher=_ReEnricher(),
    )
    detail = await admin.pipeline("car-9")
    assert detail.listing.external_id == "car-9"
    assert detail.pricing is not None
    assert detail.pricing.recommended_dealer_bid == 880
