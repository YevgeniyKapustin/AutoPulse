"""Serialize domain events into AMQP body + headers."""

from __future__ import annotations

from dataclasses import dataclass

from autopulse_shared.schemas.events import BaseEvent


@dataclass(frozen=True, slots=True)
class SerializedEvent:
    body: bytes
    headers: dict[str, str]


def serialize_event(event: BaseEvent) -> SerializedEvent:
    """Dump event JSON and extract low-cardinality AMQP headers."""
    headers: dict[str, str] = {
        "event_type": str(event.event_type),
        "schema_version": event.schema_version,
        "event_id": event.event_id,
    }
    if event.request_id:
        headers["x-request-id"] = event.request_id
    return SerializedEvent(
        body=event.model_dump_json().encode("utf-8"),
        headers=headers,
    )
