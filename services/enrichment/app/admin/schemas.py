"""Admin overview DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from autopulse_shared.schemas.listing import EnrichedListing
from autopulse_shared.schemas.pricing import PricingResult

ListingStatusFilter = Literal["enriched", "partial"]
QueueAlertLevel = Literal["ok", "warn", "bad", "unknown"]


class QueueDepths(BaseModel):
    enrichment_raw: int | None = None
    enrichment_retry: int | None = None
    enrichment_dlq: int | None = None
    pricer_work: int | None = None
    pricer_retry: int | None = None
    pricer_dlq: int | None = None


class QueueDepthCard(BaseModel):
    key: str
    label: str
    depth: int | None = None
    level: QueueAlertLevel = "unknown"


class QueueAlertSummary(BaseModel):
    cards: list[QueueDepthCard] = Field(default_factory=list)
    bad_count: int = 0
    warn_count: int = 0
    work_warn_depth: int
    dlq_warn_depth: int


class MessagingCounts(BaseModel):
    inbox: dict[str, int] = Field(default_factory=dict)
    outbox: dict[str, int] = Field(default_factory=dict)


class ReadinessSnapshot(BaseModel):
    enrichment_ready: bool
    enrichment_checks: dict[str, str] = Field(default_factory=dict)
    pricer_ready: bool | None = None


class AdminOverview(BaseModel):
    listings_total: int
    listings_enriched: int
    listings_partial: int
    messaging: MessagingCounts
    queues: QueueDepths
    queue_alerts: QueueAlertSummary
    readiness: ReadinessSnapshot
    pricer: dict[str, object] | None = None
    metrics_enrichment_url: str
    metrics_pricer_url: str


class ListingAdminRow(BaseModel):
    external_id: str
    source: str
    title: str | None = None
    llm_done: bool
    cv_done: bool
    asking_price: float | None = None
    updated_at: datetime | None = None


class ListingAdminPage(BaseModel):
    items: list[ListingAdminRow]
    next_cursor: datetime | None = None


class PipelineDetail(BaseModel):
    listing: EnrichedListing
    pricing: PricingResult | None = None


class ReEnrichAccepted(BaseModel):
    status: Literal["accepted"] = "accepted"
    event_id: str
    external_id: str
