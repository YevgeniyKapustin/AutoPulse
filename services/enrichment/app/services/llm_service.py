"""LLM option extraction with retries and circuit breaker."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from autopulse_shared.schemas.listing import ListingOptions, RawListing
from services.enrichment.app.core.circuit_breaker import CircuitBreaker
from services.enrichment.app.core.config import Settings
from services.enrichment.app.core.exceptions import EnrichmentError

logger = logging.getLogger(__name__)

_PACKAGE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("M-Sport", re.compile(r"\bm[-\s]?sport\b", re.I)),
    ("AMG", re.compile(r"\bamg\b", re.I)),
    ("S-Line", re.compile(r"\bs[-\s]?line\b", re.I)),
]

_FEATURE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("panorama", re.compile(r"panorama|панорама", re.I)),
    ("harman_kardon", re.compile(r"harman|харман", re.I)),
    ("heated_seats", re.compile(r"heated seats|подогрев сидений", re.I)),
    ("leather", re.compile(r"leather|кожа", re.I)),
]

_OWNER_PATTERN = re.compile(
    r"(one owner|single owner|один владелец|1 владелец)",
    re.I,
)


class LlmService:
    def __init__(
        self,
        settings: Settings,
        breaker: CircuitBreaker | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._breaker = breaker or CircuitBreaker(
            failure_threshold=settings.llm_max_retries + 2,
            recovery_timeout_sec=30.0,
        )
        self._http = http_client

    async def extract_options(self, listing: RawListing) -> ListingOptions:
        self._breaker.before_call()
        try:
            if self._settings.llm_api_key:
                options = await self._extract_via_api(listing)
            else:
                options = self._extract_heuristic(listing)
            self._breaker.record_success()
            return options
        except Exception as exc:
            self._breaker.record_failure()
            raise EnrichmentError(str(exc), stage="llm") from exc

    def _extract_heuristic(self, listing: RawListing) -> ListingOptions:
        text = " ".join(
            part
            for part in (listing.title, listing.description)
            if part
        )
        packages = [name for name, pat in _PACKAGE_PATTERNS if pat.search(text)]
        features = [name for name, pat in _FEATURE_PATTERNS if pat.search(text)]
        tags: list[str] = ["heuristic"]
        owner_count = 1 if _OWNER_PATTERN.search(text) else None
        if owner_count == 1:
            tags.append("one_owner")
        return ListingOptions(
            packages=packages,
            features=features,
            tags=tags,
            owner_count=owner_count,
            notes="heuristic extractor (no LLM_API_KEY)",
        )

    async def _extract_via_api(self, listing: RawListing) -> ListingOptions:
        return await self._call_openai_with_retry(listing)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type((httpx.HTTPError, TimeoutError)),
    )
    async def _call_openai_with_retry(self, listing: RawListing) -> ListingOptions:
        prompt = (
            "Extract car options as JSON with keys packages, features, tags, "
            "owner_count, notes from this listing text:\n"
            f"title: {listing.title}\ndescription: {listing.description}"
        )
        headers = {
            "Authorization": f"Bearer {self._settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "model": self._settings.llm_model,
            "messages": [
                {
                    "role": "system",
                    "content": "Return only valid JSON for ListingOptions.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        client = self._http or httpx.AsyncClient(
            timeout=self._settings.llm_timeout_sec
        )
        owns_client = self._http is None
        try:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return ListingOptions.model_validate_json(content)
        finally:
            if owns_client:
                await client.aclose()
