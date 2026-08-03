from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from autopulse_shared.schemas.listing import EnrichedListing, RawListing


class EventType(StrEnum):
    RAW_CREATED = "car.raw.created"
    ENRICHED_SUCCESS = "car.enriched.success"
    ENRICHMENT_FAILED = "car.enrichment.failed"


class BaseEvent(BaseModel):
    event_id: str
    event_type: EventType
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    request_id: str | None = None
    retry_count: int = 0


class RawListingEvent(BaseEvent):
    event_type: EventType = EventType.RAW_CREATED
    listing: RawListing


class ListingEnrichedEvent(BaseEvent):
    event_type: EventType = EventType.ENRICHED_SUCCESS
    listing: EnrichedListing


class EnrichmentFailedEvent(BaseEvent):
    event_type: EventType = EventType.ENRICHMENT_FAILED
    external_id: str
    error: str
    stage: str | None = None
