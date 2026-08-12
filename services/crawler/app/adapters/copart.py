"""Copart-shaped lot payload → RawListing."""

from __future__ import annotations

from typing import Any

from services.crawler.app.adapters.fields import (
    miles_to_km,
    optional_float,
    optional_int,
    optional_str,
    parse_url,
    parse_urls,
    require_str,
)
from services.crawler.app.core.exceptions import AdapterError

from autopulse_shared.schemas.listing import ListingSource, RawListing


class CopartAdapter:
    """Normalize Copart-like lot JSON (not live scrape)."""

    @property
    def source(self) -> ListingSource:
        return ListingSource.COPART

    def to_raw_listing(self, payload: dict[str, Any]) -> RawListing:
        lot = require_str(payload, "lotNumber", "lot_number", "lot")
        external_id = f"copart-{lot}"
        mileage = _mileage_km(payload)
        currency = optional_str(payload, "currencyCode", "currency") or "USD"
        title = optional_str(payload, "title", "lotTitle")
        if title is None:
            year = optional_int(payload, "year")
            make = optional_str(payload, "make")
            model = optional_str(payload, "model")
            bits = [str(year) if year else None, make, model]
            title = " ".join(b for b in bits if b) or None
        return RawListing(
            external_id=external_id,
            source=ListingSource.COPART,
            url=parse_url(optional_str(payload, "lotUrl", "url", "href")),
            title=title,
            description=optional_str(payload, "description", "damageDescription"),
            make=optional_str(payload, "make"),
            model=optional_str(payload, "model"),
            year=optional_int(payload, "year"),
            mileage_km=mileage,
            asking_price=optional_float(
                payload,
                "highBid",
                "buyNowPrice",
                "asking_price",
                "currentBid",
            ),
            currency=currency,
            image_urls=parse_urls(
                payload.get("imageUrls") or payload.get("image_urls") or []
            ),
            raw_payload=dict(payload),
        )


def _mileage_km(payload: dict[str, Any]) -> int | None:
    direct = optional_int(payload, "mileage_km", "odometerKm")
    if direct is not None:
        return direct
    odo = optional_float(payload, "odometer", "odometerReading")
    if odo is None:
        return None
    unit = (optional_str(payload, "odometerUnit", "odometer_unit") or "mi").lower()
    if unit in {"km", "kilometers", "kilometres"}:
        return int(round(odo))
    if unit in {"mi", "mile", "miles"}:
        return miles_to_km(odo)
    raise AdapterError(f"unknown odometer unit: {unit!r}")
