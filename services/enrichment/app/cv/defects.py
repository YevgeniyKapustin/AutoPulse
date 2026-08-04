"""Shared DefectInfo constructors for CV fetch/analysis failures."""

from __future__ import annotations

from pydantic import HttpUrl

from autopulse_shared.schemas.listing import DefectInfo


def defect(label: str, confidence: float, url: HttpUrl) -> DefectInfo:
    return DefectInfo(label=label, confidence=confidence, image_url=url)


def image_fetch_failed(url: HttpUrl) -> DefectInfo:
    return defect("image_fetch_failed", 0.5, url)


def image_too_large(url: HttpUrl, *, confidence: float = 0.6) -> DefectInfo:
    return defect("image_too_large", confidence, url)


def image_unreadable(url: HttpUrl) -> DefectInfo:
    return defect("image_unreadable", 0.55, url)
