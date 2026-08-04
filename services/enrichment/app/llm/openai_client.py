"""OpenAI Chat Completions client for listing option extraction."""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from autopulse_shared.schemas.listing import ListingOptions, RawListing
from services.enrichment.app.core.config import Settings
from services.enrichment.app.llm.prompts import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
)

_NETWORK_ERRORS = (httpx.TransportError, TimeoutError, httpx.TimeoutException)
_OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, _NETWORK_ERRORS):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return False


class OpenAiOptionsClient:
    """HTTP transport + request/response mapping for OpenAI options."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http_client
        self._max_attempts = max(1, settings.llm_max_retries)

    async def extract(self, listing: RawListing) -> ListingOptions:
        async for attempt in AsyncRetrying(
            reraise=True,
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
            retry=retry_if_exception(_is_retryable),
        ):
            with attempt:
                return await self._extract_once(listing)
        raise AssertionError("unreachable")  # pragma: no cover

    async def _extract_once(self, listing: RawListing) -> ListingOptions:
        headers, body = self._build_request(listing)
        response = await self._http.post(
            _OPENAI_CHAT_URL,
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        return self._parse_response(response)

    def _build_request(
        self,
        listing: RawListing,
    ) -> tuple[dict[str, str], dict[str, Any]]:
        prompt = USER_PROMPT_TEMPLATE.format(
            title=listing.title or "",
            description=listing.description or "",
        )
        headers = {
            "Authorization": (
                f"Bearer {self._settings.llm_api_key.get_secret_value()}"
            ),
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "model": self._settings.llm_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        return headers, body

    def _parse_response(self, response: httpx.Response) -> ListingOptions:
        content = response.json()["choices"][0]["message"]["content"]
        return ListingOptions.model_validate_json(content)
