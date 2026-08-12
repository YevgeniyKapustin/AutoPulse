"""Build RawListing from dealer form fields or pasted JSON."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import HttpUrl, TypeAdapter, ValidationError

from autopulse_shared.schemas.listing import ListingSource, RawListing

_URL = TypeAdapter(HttpUrl)
_SOURCE_ALIASES = {
    "copart": ListingSource.COPART,
    "iaai": ListingSource.IAAI,
    "manual": ListingSource.MANUAL,
    "other": ListingSource.OTHER,
}


class DealerSubmitError(ValueError):
    """Invalid dealer submit payload."""


def parse_source(raw: str) -> ListingSource:
    key = raw.strip().lower()
    try:
        return _SOURCE_ALIASES[key]
    except KeyError as exc:
        raise DealerSubmitError(
            f"unknown source {raw!r}; use copart, iaai, or manual"
        ) from exc


def listing_from_form(
    *,
    source: str,
    external_ref: str,
    title: str = "",
    description: str = "",
    make: str = "",
    model: str = "",
    year: str = "",
    mileage_km: str = "",
    asking_price: str = "",
    currency: str = "USD",
    url: str = "",
    image_urls_text: str = "",
) -> RawListing:
    src = parse_source(source)
    ref = external_ref.strip()
    if not ref:
        raise DealerSubmitError("lot / stock / id is required")
    external_id = _external_id(src, ref)
    year_i = _optional_int(year, "year")
    miles = _optional_int(mileage_km, "mileage_km")
    price = _optional_float(asking_price, "asking_price")
    images = _parse_image_lines(image_urls_text)
    title_clean = title.strip() or _default_title(year_i, make, model)
    return RawListing(
        external_id=external_id,
        source=src,
        url=_parse_url(url),
        title=title_clean or None,
        description=description.strip() or None,
        make=make.strip() or None,
        model=model.strip() or None,
        year=year_i,
        mileage_km=miles,
        asking_price=price,
        currency=(currency.strip() or "USD"),
        image_urls=images,
        raw_payload={
            "submitted_via": "dealer_form",
            "external_ref": ref,
        },
    )


def listing_from_json_text(raw: str, *, source_hint: str = "manual") -> RawListing:
    text = raw.strip()
    if not text:
        raise DealerSubmitError("JSON payload is empty")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DealerSubmitError(f"invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise DealerSubmitError("JSON root must be an object")
    try:
        return RawListing.model_validate(payload)
    except ValidationError:
        pass
    return _vendor_payload_to_listing(payload, source_hint=source_hint)


def _vendor_payload_to_listing(
    payload: dict[str, Any],
    *,
    source_hint: str,
) -> RawListing:
    if payload.get("lotNumber") or payload.get("lot_number") or payload.get("lot"):
        src = ListingSource.COPART
        ref = str(
            payload.get("lotNumber") or payload.get("lot_number") or payload.get("lot")
        ).strip()
    elif (
        payload.get("stockNumber")
        or payload.get("stock_number")
        or payload.get("stock")
    ):
        src = ListingSource.IAAI
        ref = str(
            payload.get("stockNumber")
            or payload.get("stock_number")
            or payload.get("stock")
        ).strip()
    else:
        src = parse_source(source_hint)
        ref = str(payload.get("external_id") or "").strip()
        if not ref:
            raise DealerSubmitError(
                "JSON is not RawListing and has no lotNumber/stockNumber"
            )
        if src == ListingSource.MANUAL:
            try:
                data = dict(payload)
                data.setdefault("source", ListingSource.MANUAL.value)
                return RawListing.model_validate(data)
            except ValidationError as exc:
                raise DealerSubmitError(str(exc)) from exc

    make = _as_str(payload.get("make"))
    model = _as_str(payload.get("model"))
    year = _optional_int(payload.get("year"), "year")
    title = _as_str(payload.get("title")) or _default_title(
        year, make or "", model or ""
    )
    images_raw = (
        payload.get("imageUrls")
        or payload.get("image_urls")
        or payload.get("images")
        or []
    )
    if not isinstance(images_raw, list):
        raise DealerSubmitError("image urls must be a list")
    price = None
    for key in (
        "highBid",
        "buyNowPrice",
        "preBidPrice",
        "asking_price",
        "currentBid",
    ):
        if key in payload and payload[key] not in (None, ""):
            price = _optional_float(payload[key], key)
            break
    mileage = None
    if payload.get("mileage_km") not in (None, ""):
        mileage = _optional_int(payload.get("mileage_km"), "mileage_km")
    elif payload.get("odometer") not in (None, ""):
        odo = _optional_float(payload.get("odometer"), "odometer")
        unit = (_as_str(payload.get("odometerUnit")) or "mi").lower()
        if odo is not None:
            mileage = (
                int(round(odo)) if unit.startswith("km") else int(round(odo * 1.60934))
            )
    return RawListing(
        external_id=_external_id(src, ref),
        source=src,
        url=_parse_url(
            _as_str(
                payload.get("lotUrl") or payload.get("vehicleUrl") or payload.get("url")
            )
            or ""
        ),
        title=title,
        description=_as_str(payload.get("description")) or None,
        make=make,
        model=model,
        year=year,
        mileage_km=mileage,
        asking_price=price,
        currency=_as_str(payload.get("currencyCode") or payload.get("currency"))
        or "USD",
        image_urls=[u for u in (_parse_url(str(x)) for x in images_raw) if u],
        raw_payload=dict(payload),
    )


def _external_id(source: ListingSource, ref: str) -> str:
    clean = re.sub(r"\s+", "", ref)
    if source == ListingSource.COPART:
        return clean if clean.startswith("copart-") else f"copart-{clean}"
    if source == ListingSource.IAAI:
        return clean if clean.startswith("iaai-") else f"iaai-{clean}"
    return clean


def _default_title(year: int | None, make: str, model: str) -> str | None:
    bits = [str(year) if year else None, make.strip() or None, model.strip() or None]
    text = " ".join(b for b in bits if b)
    return text or None


def _parse_image_lines(text: str) -> list[HttpUrl]:
    urls: list[HttpUrl] = []
    for line in text.replace(",", "\n").splitlines():
        item = line.strip()
        if not item:
            continue
        url = _parse_url(item)
        if url is not None:
            urls.append(url)
    return urls


def _parse_url(value: str) -> HttpUrl | None:
    text = value.strip()
    if not text:
        return None
    try:
        return _URL.validate_python(text)
    except Exception as exc:
        raise DealerSubmitError(f"invalid url: {text!r}") from exc


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any, field: str) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise DealerSubmitError(f"invalid {field}: {value!r}") from exc


def _optional_float(value: Any, field: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise DealerSubmitError(f"invalid {field}: {value!r}") from exc
