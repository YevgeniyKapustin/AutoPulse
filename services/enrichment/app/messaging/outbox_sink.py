"""Outbox-backed event sink: durable write then confirmed publish."""

from __future__ import annotations

import logging
from typing import Any, Protocol

from autopulse_shared.schemas.events import (
    BaseEvent,
    EnrichmentFailedEvent,
    ListingEnrichedEvent,
    RawListingEvent,
)
from services.enrichment.app.messaging.event_message import serialize_event
from services.enrichment.app.messaging.publisher import EventPublisher
from services.enrichment.app.messaging.routes import PublishRoutes
from services.enrichment.app.repositories.messaging_store import OutboxRepository

logger = logging.getLogger(__name__)


class OutboxStore(Protocol):
    async def enqueue(
        self, routing_key: str, body: bytes, headers: dict[str, object]
    ) -> str: ...

    async def list_pending(self, limit: int = 50) -> list[dict[str, Any]]: ...

    async def mark_published(self, outbox_id: str) -> None: ...


class OutboxEventSink:
    def __init__(
        self,
        routes: PublishRoutes,
        outbox: OutboxRepository,
        publisher: EventPublisher,
    ) -> None:
        self._routes = routes
        self._outbox = outbox
        self._publisher = publisher

    async def publish_raw(self, event: RawListingEvent) -> None:
        await self._enqueue_and_drain(event, self._routes.raw_created)

    async def publish_enriched(self, event: ListingEnrichedEvent) -> None:
        await self._enqueue_and_drain(event, self._routes.enriched_success)

    async def publish_failed(self, event: EnrichmentFailedEvent) -> None:
        await self._enqueue_and_drain(event, self._routes.enrichment_failed)

    async def drain(self, limit: int = 50) -> int:
        pending = await self._outbox.list_pending(limit=limit)
        published = 0
        for doc in pending:
            body = doc["body"]
            if isinstance(body, str):
                body = body.encode("utf-8")
            elif not isinstance(body, (bytes, bytearray)):
                body = bytes(body)
            raw_headers = doc.get("headers") or {}
            headers = {
                str(key): str(value)
                for key, value in dict(raw_headers).items()
                if value is not None
            }
            await self._publisher.publish_raw_body(
                body,
                str(doc["routing_key"]),
                headers=headers,
            )
            await self._outbox.mark_published(str(doc["_id"]))
            published += 1
        if published:
            logger.info("Drained enrichment outbox count=%s", published)
        return published

    async def _enqueue_and_drain(self, event: BaseEvent, routing_key: str) -> None:
        payload = serialize_event(event)
        await self._outbox.enqueue(
            routing_key,
            payload.body,
            dict(payload.headers),
        )
        await self.drain()
