"""IAAI-shaped stock payload → RawListing."""

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


class IaaiAdapter:
    """Normalize IAAI-like stock JSON (not live scrape)."""

    @property
    def source(self) -> ListingSource:
        return ListingSource.IAAI

    def to_raw_listing(self, payload: dict[str, Any]) -> RawListing:
        stock = require_str(payload, "stockNumber", "stock_number", "stock")
        external_id = f"iaai-{stock}"
        mileage = _mileage_km(payload)
        currency = optional_str(payload, "currency", "currencyCode") or "USD"
        title = optional_str(payload, "title", "vehicleTitle")
        if title is None:
            year = optional_int(payload, "year")
            make = optional_str(payload, "make")
            model = optional_str(payload, "model")
            bits = [str(year) if year else None, make, model]
            title = " ".join(b for b in bits if b) or None
        return RawListing(
            external_id=external_id,
            source=ListingSource.IAAI,
            url=parse_url(optional_str(payload, "vehicleUrl", "url", "href")),
            title=title,
            description=optional_str(payload, "description", "notes"),
            make=optional_str(payload, "make"),
            model=optional_str(payload, "model"),
            year=optional_int(payload, "year"),
            mileage_km=mileage,
            asking_price=optional_float(
                payload,
                "preBidPrice",
                "buyNowPrice",
                "asking_price",
                "highBid",
            ),
            currency=currency,
            image_urls=parse_urls(
                payload.get("images")
                or payload.get("imageUrls")
                or payload.get("image_urls")
                or []
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
