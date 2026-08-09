"""Shared helpers for source adapters."""

from __future__ import annotations

from typing import Any

from pydantic import HttpUrl, TypeAdapter
from services.crawler.app.core.exceptions import AdapterError

_URL = TypeAdapter(HttpUrl)


def require_str(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    raise AdapterError(f"missing required string field (tried {keys})")


def optional_str(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def optional_int(payload: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = payload.get(key)
        if value is None or value == "":
            continue
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise AdapterError(f"invalid int for {key!r}: {value!r}") from exc
    return None


def optional_float(payload: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = payload.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise AdapterError(f"invalid float for {key!r}: {value!r}") from exc
    return None


def parse_url(value: str | None) -> HttpUrl | None:
    if not value:
        return None
    try:
        return _URL.validate_python(value)
    except Exception as exc:
        raise AdapterError(f"invalid url: {value!r}") from exc


def parse_urls(values: Any) -> list[HttpUrl]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise AdapterError("image urls must be a list")
    out: list[HttpUrl] = []
    for item in values:
        url = parse_url(str(item))
        if url is not None:
            out.append(url)
    return out


def miles_to_km(miles: float) -> int:
    return int(round(miles * 1.60934))
