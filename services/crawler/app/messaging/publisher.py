"""Publish normalized listings to enrichment HTTP ingress."""

from __future__ import annotations

import logging
from types import TracebackType
from typing import Any, Self

import httpx

from autopulse_shared.schemas.listing import RawListing

logger = logging.getLogger(__name__)


class EnrichmentHttpPublisher:
    """POST RawListing to enrichment ``/api/v1/listings``."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_sec: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout_sec,
        )

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def publish(
        self,
        listing: RawListing,
        *,
        request_id: str | None = None,
    ) -> str:
        headers: dict[str, str] = {}
        if request_id:
            headers["X-Request-ID"] = request_id
        response = await self._http.post(
            "/api/v1/listings",
            json=listing.model_dump(mode="json"),
            headers=headers,
        )
        response.raise_for_status()
        payload: Any = response.json()
        event_id = payload.get("event_id") if isinstance(payload, dict) else None
        if not isinstance(event_id, str) or not event_id:
            raise RuntimeError(
                f"enrichment ingest response missing event_id: {payload}"
            )
        logger.info(
            "Ingested %s via enrichment event_id=%s",
            listing.external_id,
            event_id,
        )
        return event_id
