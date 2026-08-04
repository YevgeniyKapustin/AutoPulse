"""LLM option extraction with retries and circuit breaker."""

from __future__ import annotations

from types import TracebackType
from typing import Self

import httpx
from pydantic import ValidationError

from autopulse_shared.schemas.listing import ListingOptions, RawListing
from services.enrichment.app.core.circuit_breaker import CircuitBreaker
from services.enrichment.app.core.config import Settings
from services.enrichment.app.core.exceptions import EnrichmentError
from services.enrichment.app.llm.heuristic import HeuristicOptionsExtractor
from services.enrichment.app.llm.openai_client import OpenAiOptionsClient

_NETWORK_ERRORS = (httpx.HTTPError, TimeoutError)
_PARSE_ERRORS = (
    KeyError,
    IndexError,
    TypeError,
    ValueError,
    ValidationError,
)


class LlmService:
    def __init__(
        self,
        settings: Settings,
        breaker: CircuitBreaker | None = None,
        http_client: httpx.AsyncClient | None = None,
        heuristic: HeuristicOptionsExtractor | None = None,
        openai_client: OpenAiOptionsClient | None = None,
    ) -> None:
        self._settings = settings
        self._breaker = breaker or CircuitBreaker(
            failure_threshold=settings.llm_max_retries + 2,
            recovery_timeout_sec=30.0,
            name="llm",
        )
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient(
            timeout=settings.llm_timeout_sec,
        )
        self._heuristic = heuristic or HeuristicOptionsExtractor()
        self._openai = openai_client or OpenAiOptionsClient(
            settings,
            self._http,
        )

    async def aclose(self) -> None:
        """Close the owned HTTP client (no-op if client was injected)."""
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

    async def extract_options(self, listing: RawListing) -> ListingOptions:
        # Local heuristic is not an external dependency — skip the breaker.
        if not self._settings.llm_api_key.get_secret_value():
            return self._heuristic.extract(listing)

        await self._breaker.before_call()
        try:
            options = await self._openai.extract(listing)
        except _NETWORK_ERRORS as exc:
            await self._breaker.record_failure()
            raise EnrichmentError(
                f"LLM API network error: {exc}",
                stage="llm",
            ) from exc
        except _PARSE_ERRORS as exc:
            # Transport succeeded; do not punish the circuit for bad payloads.
            await self._breaker.record_success()
            raise EnrichmentError(
                f"LLM parsing error: {exc}",
                stage="llm",
            ) from exc
        except Exception as exc:
            await self._breaker.record_failure()
            raise EnrichmentError(str(exc), stage="llm") from exc
        else:
            await self._breaker.record_success()
            return options
