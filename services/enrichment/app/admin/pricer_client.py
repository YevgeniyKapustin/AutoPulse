"""HTTP client for pricer admin endpoints."""

from __future__ import annotations

import logging
from types import TracebackType
from typing import Any, Self

import httpx

from autopulse_shared.schemas.pricing import PricingResult

logger = logging.getLogger(__name__)


class HttpPricerAdminClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_sec: float = 2.0,
        username: str | None = None,
        password: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._owns_http = http_client is None
        auth: tuple[str, str] | None = None
        if password:
            auth = (username or "autopulse", password)
        self._http = http_client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout_sec,
            auth=auth,
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

    async def overview(self) -> dict[str, Any] | None:
        try:
            response = await self._http.get("/api/v1/admin/overview")
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else None
        except Exception as exc:
            logger.warning("Pricer admin overview unavailable: %s", exc)
            return None

    async def get_pricing(self, external_id: str) -> PricingResult | None:
        try:
            response = await self._http.get(f"/api/v1/pricing/{external_id}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return PricingResult.model_validate(response.json())
        except Exception as exc:
            logger.warning(
                "Pricer pricing lookup failed external_id=%s: %s",
                external_id,
                exc,
            )
            return None
