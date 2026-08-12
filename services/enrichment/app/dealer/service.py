"""Dealer pipeline: submit listing and read enrichment + pricing."""

from __future__ import annotations

from dataclasses import dataclass

from autopulse_shared.schemas.listing import EnrichedListing, RawListing
from autopulse_shared.schemas.pricing import PricingResult
from services.enrichment.app.admin.ports import PricerAdminClient
from services.enrichment.app.core.exceptions import ListingNotFoundError
from services.enrichment.app.dealer.crawler_client import (
    CrawlerSampleError,
    HttpCrawlerClient,
)
from services.enrichment.app.enrichment.ports import (
    ListingReader,
    RawListingIngestor,
)


@dataclass(frozen=True, slots=True)
class DealerSubmitResult:
    event_id: str
    external_id: str


@dataclass(frozen=True, slots=True)
class DealerPipelineView:
    listing: EnrichedListing | None
    pricing: PricingResult | None
    enriching: bool
    priced: bool


class DealerService:
    def __init__(
        self,
        *,
        ingestor: RawListingIngestor,
        listings: ListingReader,
        pricer: PricerAdminClient,
        crawler: HttpCrawlerClient | None = None,
    ) -> None:
        self._ingestor = ingestor
        self._listings = listings
        self._pricer = pricer
        self._crawler = crawler

    async def submit(
        self,
        listing: RawListing,
        *,
        request_id: str | None = None,
    ) -> DealerSubmitResult:
        event_id = await self._ingestor.enqueue_raw(listing, request_id=request_id)
        return DealerSubmitResult(
            event_id=event_id,
            external_id=listing.external_id,
        )

    async def sample_sources(self) -> list[str]:
        if self._crawler is None:
            return []
        return await self._crawler.list_samples()

    async def submit_sample(
        self,
        source: str,
        *,
        request_id: str | None = None,
    ) -> DealerSubmitResult:
        if self._crawler is None:
            raise CrawlerSampleError("Crawler client is not configured")
        payload = await self._crawler.ingest_sample(source, request_id=request_id)
        external_id = payload.get("external_id")
        event_id = payload.get("event_id")
        if not external_id or not event_id:
            raise CrawlerSampleError("Crawler sample response missing ids")
        return DealerSubmitResult(
            event_id=str(event_id),
            external_id=str(external_id),
        )

    async def pipeline(self, external_id: str) -> DealerPipelineView:
        listing: EnrichedListing | None
        try:
            listing = await self._listings.get_state(external_id)
        except ListingNotFoundError:
            listing = None
        pricing = await self._pricer.get_pricing(external_id)
        enriching = listing is not None and not listing.is_fully_enriched
        priced = pricing is not None
        return DealerPipelineView(
            listing=listing,
            pricing=pricing,
            enriching=enriching,
            priced=priced,
        )
