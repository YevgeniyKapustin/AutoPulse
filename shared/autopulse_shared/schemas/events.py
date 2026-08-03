from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from autopulse_shared.schemas.listing import EnrichedListing, RawListing


class EventType(StrEnum):
    RAW_CREATED = "car.raw.created"
    ENRICHED_SUCCESS = "car.enriched.success"
    ENRICHMENT_FAILED = "car.enrichment.failed"


class BaseEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: EventType
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    request_id: str | None = None
    retry_count: int = 0


class RawListingEvent(BaseEvent):
    event_type: Literal[EventType.RAW_CREATED] = EventType.RAW_CREATED
    listing: RawListing


class ListingEnrichedEvent(BaseEvent):
    event_type: Literal[EventType.ENRICHED_SUCCESS] = EventType.ENRICHED_SUCCESS
    listing: EnrichedListing


class EnrichmentFailedEvent(BaseEvent):
    event_type: Literal[EventType.ENRICHMENT_FAILED] = EventType.ENRICHMENT_FAILED
    external_id: str
    error: str
    stage: str | None = None
