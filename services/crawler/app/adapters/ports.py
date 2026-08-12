"""Adapter and publisher ports."""

from __future__ import annotations

from typing import Any, Protocol

from autopulse_shared.schemas.listing import ListingSource, RawListing


class SourceAdapter(Protocol):
    """Normalize a vendor-shaped payload into a RawListing."""

    @property
    def source(self) -> ListingSource: ...

    def to_raw_listing(self, payload: dict[str, Any]) -> RawListing: ...


class ListingPublisher(Protocol):
    """Push a normalized listing into enrichment ingress."""

    async def publish(
        self,
        listing: RawListing,
        *,
        request_id: str | None = None,
    ) -> str: ...

    async def aclose(self) -> None: ...
