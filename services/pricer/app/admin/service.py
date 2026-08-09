"""Pricer admin overview for the enrichment ops hub."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, Field

from autopulse_shared.schemas.pricing import PricingResult

ReadinessProbe = Callable[[], Awaitable[tuple[bool, dict[str, str]]]]


class PricingAdminStore(Protocol):
    async def count_results(self) -> int: ...

    async def list_recent(
        self,
        *,
        limit: int = 20,
        before_priced_at: datetime | None = None,
    ) -> list[PricingResult]: ...

    async def count_inbox_by_status(self) -> dict[str, int]: ...

    async def count_outbox_by_status(self) -> dict[str, int]: ...


class PricerAdminOverview(BaseModel):
    ready: bool
    checks: dict[str, str] = Field(default_factory=dict)
    priced_total: int
    inbox: dict[str, int] = Field(default_factory=dict)
    outbox: dict[str, int] = Field(default_factory=dict)


class PricingAdminPage(BaseModel):
    items: list[PricingResult]
    next_cursor: datetime | None = None


class PricerAdminService:
    def __init__(
        self,
        repository: PricingAdminStore,
        *,
        readiness_probe: ReadinessProbe,
    ) -> None:
        self._repository = repository
        self._readiness_probe = readiness_probe

    async def overview(self) -> PricerAdminOverview:
        ready, checks = await self._readiness_probe()
        return PricerAdminOverview(
            ready=ready,
            checks=checks,
            priced_total=await self._repository.count_results(),
            inbox=await self._repository.count_inbox_by_status(),
            outbox=await self._repository.count_outbox_by_status(),
        )

    async def list_pricing(
        self,
        *,
        limit: int = 20,
        before_priced_at: datetime | None = None,
    ) -> PricingAdminPage:
        items = await self._repository.list_recent(
            limit=limit,
            before_priced_at=before_priced_at,
        )
        next_cursor = items[-1].priced_at if items else None
        return PricingAdminPage(items=items, next_cursor=next_cursor)
