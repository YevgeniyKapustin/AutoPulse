"""Manual / already-normalized RawListing JSON."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from services.crawler.app.core.exceptions import AdapterError

from autopulse_shared.schemas.listing import ListingSource, RawListing


class ManualAdapter:
    """Accept a RawListing-shaped payload (curl / fixtures)."""

    @property
    def source(self) -> ListingSource:
        return ListingSource.MANUAL

    def to_raw_listing(self, payload: dict[str, Any]) -> RawListing:
        data = dict(payload)
        if "source" not in data:
            data["source"] = ListingSource.MANUAL.value
        try:
            listing = RawListing.model_validate(data)
        except ValidationError as exc:
            raise AdapterError(str(exc)) from exc
        if listing.source == ListingSource.OTHER:
            return listing.model_copy(update={"source": ListingSource.MANUAL})
        return listing
