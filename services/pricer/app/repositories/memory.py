"""In-memory pricing repository for unit tests."""

from __future__ import annotations

from datetime import datetime

from autopulse_shared.schemas.pricing import PricingResult
from services.pricer.app.core.exceptions import PricingNotFoundError
from services.pricer.app.services.ports import OutboxPending


class InMemoryPricingRepository:
    def __init__(self) -> None:
        self._items: dict[str, PricingResult] = {}
        self._inbox: dict[str, str] = {}
        self._outbox: dict[int, OutboxPending] = {}
        self._processing: set[int] = set()
        self._published: set[int] = set()
        self._next_outbox_id = 1
        self.outbox: list[tuple[str, str]] = []

    async def try_claim(
        self,
        event_id: str,
        *,
        reclaim_processing: bool = False,
    ) -> bool:
        status = self._inbox.get(event_id)
        if status is None:
            self._inbox[event_id] = "processing"
            return True
        if status == "completed":
            return False
        return status == "processing" and reclaim_processing

    async def mark_completed(self, event_id: str) -> None:
        self._inbox[event_id] = "completed"

    async def release_claim(self, event_id: str) -> None:
        if self._inbox.get(event_id) == "processing":
            del self._inbox[event_id]

    async def save(
        self,
        result: PricingResult,
        *,
        event_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        self._items[result.external_id] = result.model_copy(deep=True)
        eid = event_id or result.external_id
        self.outbox.append((eid, result.external_id))
        outbox_id = self._next_outbox_id
        self._next_outbox_id += 1
        self._outbox[outbox_id] = {
            "id": outbox_id,
            "routing_key": "car.priced.success",
            "payload": b"{}",
            "headers": {
                "event_id": eid,
                "x-request-id": request_id or "",
            },
        }

    async def claim_pending(self, limit: int = 50) -> list[OutboxPending]:
        claimed: list[OutboxPending] = []
        for outbox_id, doc in sorted(self._outbox.items()):
            if outbox_id in self._published or outbox_id in self._processing:
                continue
            if len(claimed) >= limit:
                break
            self._processing.add(outbox_id)
            claimed.append(doc)
        return claimed

    async def mark_published(self, outbox_id: int) -> None:
        self._processing.discard(outbox_id)
        self._published.add(outbox_id)

    async def release_outbox_claim(self, outbox_id: int) -> None:
        self._processing.discard(outbox_id)

    async def get(self, external_id: str) -> PricingResult:
        if external_id not in self._items:
            raise PricingNotFoundError(external_id)
        return self._items[external_id].model_copy(deep=True)

    async def count_results(self) -> int:
        return len(self._items)

    async def list_recent(
        self,
        *,
        limit: int = 20,
        before_priced_at: datetime | None = None,
    ) -> list[PricingResult]:
        rows = sorted(
            self._items.values(),
            key=lambda item: item.priced_at,
            reverse=True,
        )
        items: list[PricingResult] = []
        for row in rows:
            if before_priced_at is not None and row.priced_at >= before_priced_at:
                continue
            items.append(row.model_copy(deep=True))
            if len(items) >= max(1, min(limit, 100)):
                break
        return items

    async def count_inbox_by_status(self) -> dict[str, int]:
        counts: dict[str, int] = {"processing": 0, "completed": 0}
        for status in self._inbox.values():
            counts[status] = counts.get(status, 0) + 1
        return counts

    async def count_outbox_by_status(self) -> dict[str, int]:
        counts = {"pending": 0, "processing": 0, "published": 0}
        for outbox_id in self._outbox:
            if outbox_id in self._published:
                counts["published"] += 1
            elif outbox_id in self._processing:
                counts["processing"] += 1
            else:
                counts["pending"] += 1
        return counts
