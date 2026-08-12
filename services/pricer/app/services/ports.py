"""Ports for pricing use-cases and messaging adapters."""

from __future__ import annotations

from typing import Protocol, TypedDict

from autopulse_shared.schemas.listing import EnrichedListing
from autopulse_shared.schemas.pricing import PricingResult


class OutboxPending(TypedDict):
    id: int
    routing_key: str
    payload: bytes
    headers: dict[str, str]


class PricingStore(Protocol):
    async def save(
        self,
        result: PricingResult,
        *,
        event_id: str | None = None,
        request_id: str | None = None,
    ) -> None: ...

    async def get(self, external_id: str) -> PricingResult: ...


class InboxStore(Protocol):
    async def try_claim(
        self,
        event_id: str,
        *,
        reclaim_processing: bool = False,
    ) -> bool: ...

    async def mark_completed(self, event_id: str) -> None: ...

    async def release_claim(self, event_id: str) -> None: ...


class OutboxStore(Protocol):
    async def claim_pending(self, limit: int = 50) -> list[OutboxPending]: ...

    async def mark_published(self, outbox_id: int) -> None: ...

    async def release_outbox_claim(self, outbox_id: int) -> None: ...


class PricingCommand(Protocol):
    async def price(
        self,
        listing: EnrichedListing,
        *,
        event_id: str | None = None,
        request_id: str | None = None,
    ) -> PricingResult: ...

    def evaluate(self, listing: EnrichedListing) -> PricingResult: ...

    async def get_result(self, external_id: str) -> PricingResult: ...
