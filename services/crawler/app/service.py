"""Ingest orchestration: adapter normalize → enrichment publish."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.crawler.app.adapters import AdapterRegistry
from services.crawler.app.adapters.ports import ListingPublisher


@dataclass(frozen=True, slots=True)
class IngestResult:
    source: str
    external_id: str
    event_id: str


class IngestService:
    def __init__(
        self,
        *,
        registry: AdapterRegistry,
        publisher: ListingPublisher,
    ) -> None:
        self._registry = registry
        self._publisher = publisher

    def list_sources(self) -> list[str]:
        return self._registry.names()

    async def ingest(
        self,
        source: str,
        payload: dict[str, Any],
        *,
        request_id: str | None = None,
    ) -> IngestResult:
        adapter = self._registry.get(source)
        listing = adapter.to_raw_listing(payload)
        event_id = await self._publisher.publish(listing, request_id=request_id)
        return IngestResult(
            source=adapter.source.value,
            external_id=listing.external_id,
            event_id=event_id,
        )
