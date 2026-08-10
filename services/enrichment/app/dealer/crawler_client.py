"""HTTP client for crawler sample ingest."""

from __future__ import annotations

import logging
from types import TracebackType
from typing import Any, Self

import httpx

logger = logging.getLogger(__name__)


class CrawlerSampleError(RuntimeError):
    """Crawler sample ingest failed."""


class HttpCrawlerClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_sec: float = 5.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout_sec,
        )

    async def aclose(self) -> None:
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

    async def list_samples(self) -> list[str]:
        try:
            response = await self._http.get("/api/v1/ingest/samples")
            response.raise_for_status()
            payload = response.json()
            sources = payload.get("sources") if isinstance(payload, dict) else None
            if isinstance(sources, list):
                return [str(item) for item in sources]
        except Exception as exc:
            logger.warning("Crawler sample list unavailable: %s", exc)
        return []

    async def ingest_sample(
        self,
        source: str,
        *,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        headers = {}
        if request_id:
            headers["X-Request-ID"] = request_id
        try:
            response = await self._http.post(
                f"/api/v1/ingest/samples/{source}",
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise CrawlerSampleError(f"Crawler unreachable: {exc}") from exc
        if response.status_code >= 400:
            detail = _error_detail(response)
            raise CrawlerSampleError(detail)
        payload = response.json()
        if not isinstance(payload, dict):
            raise CrawlerSampleError("Unexpected crawler response")
        return payload


def _error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except Exception:
        return f"Crawler HTTP {response.status_code}"
    if isinstance(body, dict) and body.get("detail"):
        return str(body["detail"])
    return f"Crawler HTTP {response.status_code}"
