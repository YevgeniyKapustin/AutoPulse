"""Admin aggregation service for the ops dashboard."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime

from autopulse_shared.schemas.listing import RawListing
from services.enrichment.app.admin.ports import (
    ListingAdminStore,
    PricerAdminClient,
    QueueDepthProbe,
    RawReEnricher,
    StatusCountStore,
)
from services.enrichment.app.admin.queue_alerts import QueueKind, classify_depth
from services.enrichment.app.admin.schemas import (
    AdminOverview,
    ListingAdminPage,
    ListingAdminRow,
    ListingStatusFilter,
    MessagingCounts,
    PipelineDetail,
    QueueAlertSummary,
    QueueDepthCard,
    QueueDepths,
    ReadinessSnapshot,
    ReEnrichAccepted,
)
from services.enrichment.app.core.config import Settings
from services.enrichment.app.core.exceptions import ListingNotFoundError

ReadinessProbe = Callable[[], Awaitable[tuple[bool, dict[str, str]]]]


class AdminService:
    def __init__(
        self,
        *,
        settings: Settings,
        listings: ListingAdminStore,
        inbox: StatusCountStore,
        outbox: StatusCountStore,
        queues: QueueDepthProbe,
        pricer: PricerAdminClient,
        re_enricher: RawReEnricher,
        readiness_probe: ReadinessProbe | None = None,
    ) -> None:
        self._settings = settings
        self._listings = listings
        self._inbox = inbox
        self._outbox = outbox
        self._queues = queues
        self._pricer = pricer
        self._re_enricher = re_enricher
        self._readiness_probe = readiness_probe

    async def overview(self) -> AdminOverview:
        settings = self._settings
        queue_names = [
            settings.enrichment_queue_name,
            settings.enrichment_retry_queue_name,
            settings.enrichment_dlq_name,
            settings.pricer_queue_name,
            settings.pricer_retry_queue_name,
            settings.pricer_dlq_name,
        ]
        depths = await self._queues.depths(queue_names)
        enrichment_ready = False
        enrichment_checks: dict[str, str] = {}
        if self._readiness_probe is not None:
            enrichment_ready, enrichment_checks = await self._readiness_probe()
        pricer_overview = await self._pricer.overview()
        pricer_ready: bool | None = None
        if isinstance(pricer_overview, dict):
            ready_raw = pricer_overview.get("ready")
            if isinstance(ready_raw, bool):
                pricer_ready = ready_raw
        queues = QueueDepths(
            enrichment_raw=depths.get(settings.enrichment_queue_name),
            enrichment_retry=depths.get(settings.enrichment_retry_queue_name),
            enrichment_dlq=depths.get(settings.enrichment_dlq_name),
            pricer_work=depths.get(settings.pricer_queue_name),
            pricer_retry=depths.get(settings.pricer_retry_queue_name),
            pricer_dlq=depths.get(settings.pricer_dlq_name),
        )
        return AdminOverview(
            listings_total=await self._listings.count_listings(),
            listings_enriched=await self._listings.count_fully_enriched(),
            listings_partial=await self._listings.count_partial(),
            messaging=MessagingCounts(
                inbox=await self._inbox.count_by_status(),
                outbox=await self._outbox.count_by_status(),
            ),
            queues=queues,
            queue_alerts=self._queue_alerts(queues),
            readiness=ReadinessSnapshot(
                enrichment_ready=enrichment_ready,
                enrichment_checks=enrichment_checks,
                pricer_ready=pricer_ready,
            ),
            pricer=pricer_overview,
            metrics_enrichment_url=settings.metrics_scrape_url,
            metrics_pricer_url=settings.pricer_metrics_scrape_url,
        )

    def _queue_alerts(self, queues: QueueDepths) -> QueueAlertSummary:
        settings = self._settings
        specs: tuple[tuple[str, str, QueueKind], ...] = (
            ("enrichment_raw", settings.enrichment_queue_name, "work"),
            ("enrichment_retry", settings.enrichment_retry_queue_name, "retry"),
            ("enrichment_dlq", settings.enrichment_dlq_name, "dlq"),
            ("pricer_work", settings.pricer_queue_name, "work"),
            ("pricer_retry", settings.pricer_retry_queue_name, "retry"),
            ("pricer_dlq", settings.pricer_dlq_name, "dlq"),
        )
        cards: list[QueueDepthCard] = []
        bad_count = 0
        warn_count = 0
        for key, label, kind in specs:
            depth = getattr(queues, key)
            level = classify_depth(
                depth,
                kind=kind,
                work_warn_depth=settings.admin_queue_warn_depth,
                dlq_warn_depth=settings.admin_dlq_warn_depth,
            )
            if level == "bad":
                bad_count += 1
            elif level == "warn":
                warn_count += 1
            cards.append(
                QueueDepthCard(key=key, label=label, depth=depth, level=level)
            )
        return QueueAlertSummary(
            cards=cards,
            bad_count=bad_count,
            warn_count=warn_count,
            work_warn_depth=settings.admin_queue_warn_depth,
            dlq_warn_depth=settings.admin_dlq_warn_depth,
        )

    async def list_listings(
        self,
        *,
        limit: int = 20,
        before_updated_at: datetime | None = None,
        status: ListingStatusFilter | None = None,
    ) -> ListingAdminPage:
        page = await self._listings.list_recent(
            limit=limit,
            before_updated_at=before_updated_at,
            status=status,
        )
        items = [
            ListingAdminRow(
                external_id=item.listing.external_id,
                source=str(item.listing.source),
                title=item.listing.title,
                llm_done=item.listing.llm_done,
                cv_done=item.listing.cv_done,
                asking_price=item.listing.asking_price,
                updated_at=item.updated_at,
            )
            for item in page
        ]
        next_cursor = items[-1].updated_at if items else None
        return ListingAdminPage(items=items, next_cursor=next_cursor)

    async def pipeline(self, external_id: str) -> PipelineDetail:
        listing = await self._listings.get(external_id)
        pricing = await self._pricer.get_pricing(external_id)
        return PipelineDetail(listing=listing, pricing=pricing)

    async def re_enrich(
        self,
        external_id: str,
        *,
        request_id: str | None = None,
    ) -> ReEnrichAccepted:
        listing = await self._listings.get_optional(external_id)
        if listing is None:
            raise ListingNotFoundError(external_id)
        raw = RawListing.model_validate(listing.model_dump())
        event_id = await self._re_enricher.enqueue_raw(raw, request_id=request_id)
        return ReEnrichAccepted(event_id=event_id, external_id=external_id)
