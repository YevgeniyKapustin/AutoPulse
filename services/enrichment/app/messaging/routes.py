"""Routing-key map for enrichment domain events."""

from __future__ import annotations

from dataclasses import dataclass

from autopulse_shared.schemas.events import BaseEvent, EventType


@dataclass(frozen=True, slots=True)
class PublishRoutes:
    raw_created: str
    enriched_success: str
    enrichment_failed: str

    def for_event(self, event: BaseEvent) -> str:
        mapping = {
            EventType.RAW_CREATED: self.raw_created,
            EventType.ENRICHED_SUCCESS: self.enriched_success,
            EventType.ENRICHMENT_FAILED: self.enrichment_failed,
        }
        try:
            return mapping[EventType(event.event_type)]
        except KeyError as exc:
            raise ValueError(
                f"No routing key configured for event_type={event.event_type}"
            ) from exc
