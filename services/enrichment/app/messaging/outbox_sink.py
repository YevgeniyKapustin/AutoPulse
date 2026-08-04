"""Outbox-backed event sink: durable write then confirmed publish."""

from __future__ import annotations

import logging
from typing import Protocol

from autopulse_shared.schemas.events import (
    BaseEvent,
    EnrichmentFailedEvent,
    ListingEnrichedEvent,
    RawListingEvent,
)
from services.enrichment.app.messaging.event_message import serialize_event
from services.enrichment.app.messaging.routes import PublishRoutes
from services.enrichment.app.repositories.messaging_store import OutboxPendingDoc

logger = logging.getLogger(__name__)


class OutboxStore(Protocol):
    async def enqueue(
        self,
        routing_key: str,
        body: bytes,
        headers: dict[str, str],
    ) -> str: ...

    async def claim_pending(self, limit: int = 50) -> list[OutboxPendingDoc]: ...

    async def mark_published(self, outbox_id: str) -> None: ...

    async def release_claim(self, outbox_id: str) -> None: ...


class RawBodyPublisher(Protocol):
    async def publish_raw_body(
        self,
        body: bytes,
        routing_key: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> None: ...


class OutboxEventSink:
    def __init__(
        self,
        routes: PublishRoutes,
        outbox: OutboxStore,
        publisher: RawBodyPublisher,
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
        """Claim pending outbox rows and publish (multi-replica safe).

        Per-row publish failures release that claim and continue the
        batch so other rows are not stuck in ``processing``.
        """
        pending = await self._outbox.claim_pending(limit=limit)
        published = 0
        for doc in pending:
            outbox_id = str(doc["_id"])
            try:
                await self._publish_claimed(doc)
                await self._outbox.mark_published(outbox_id)
                published += 1
            except Exception:
                logger.exception(
                    "Outbox publish failed outbox_id=%s; releasing claim",
                    outbox_id,
                )
                await self._outbox.release_claim(outbox_id)
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
        # Durable write already succeeded; broker hiccups must not fail
        # the
        # business path — a later drain / replica will republish.
        try:
            await self.drain()
        except Exception:
            logger.exception(
                "Outbox drain-after-enqueue failed routing_key=%s",
                routing_key,
            )

    async def _publish_claimed(self, doc: OutboxPendingDoc) -> None:
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
