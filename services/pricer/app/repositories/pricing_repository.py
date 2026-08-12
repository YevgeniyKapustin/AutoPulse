"""SQLAlchemy async repository for pricing results + inbox/outbox."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Final, TypedDict

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from autopulse_shared.schemas.events import PricingCompletedEvent
from autopulse_shared.schemas.pricing import PricingResult
from services.pricer.app.core.config import Settings
from services.pricer.app.core.exceptions import PricingNotFoundError
from services.pricer.app.models.pricing import (
    OutboxMessageRow,
    PricingResultRow,
    ProcessedEventRow,
)
from services.pricer.app.services.ports import OutboxPending

_CLAIM_STALE_AFTER: Final[timedelta] = timedelta(minutes=5)


class PricingRowValues(TypedDict):
    external_id: str
    bid_price: float
    recommended_dealer_bid: float
    estimated_turnover_days: int
    target_margin_pct: float
    price_low: float
    price_high: float
    currency: str
    model_version: str
    meta_json: str
    priced_at: datetime


class PricingRepository:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings

    async def try_claim(
        self,
        event_id: str,
        *,
        reclaim_processing: bool = False,
    ) -> bool:
        """Acquire processing claim; false if completed/leased."""
        now = datetime.now(UTC).replace(tzinfo=None)
        async with self._session_factory() as session:
            session.add(
                ProcessedEventRow(
                    event_id=event_id,
                    status="processing",
                    claimed_at=now,
                    completed_at=None,
                )
            )
            try:
                await session.commit()
                return True
            except IntegrityError:
                await session.rollback()

            stale_before = now - _CLAIM_STALE_AFTER
            if reclaim_processing:
                clause = ProcessedEventRow.status == "processing"
            else:
                clause = (ProcessedEventRow.status == "processing") & (
                    ProcessedEventRow.claimed_at < stale_before
                )
            result = await session.execute(
                update(ProcessedEventRow)
                .where(ProcessedEventRow.event_id == event_id)
                .where(clause)
                .values(status="processing", claimed_at=now, completed_at=None)
            )
            await session.commit()
            return int(getattr(result, "rowcount", 0) or 0) > 0

    async def mark_completed(self, event_id: str) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        async with self._session_factory() as session:
            row = await session.get(ProcessedEventRow, event_id)
            if row is None:
                session.add(
                    ProcessedEventRow(
                        event_id=event_id,
                        status="completed",
                        claimed_at=None,
                        completed_at=now,
                    )
                )
            else:
                row.status = "completed"
                row.claimed_at = None
                row.completed_at = now
            await session.commit()

    async def release_claim(self, event_id: str) -> None:
        async with self._session_factory() as session:
            row = await session.get(ProcessedEventRow, event_id)
            if row is not None and row.status == "processing":
                await session.delete(row)
                await session.commit()

    async def save(
        self,
        result: PricingResult,
        *,
        event_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(PricingResultRow).where(
                    PricingResultRow.external_id == result.external_id
                )
            )
            payload = self._to_row_values(result)
            if row is None:
                session.add(PricingResultRow(**payload))
            else:
                for key, value in payload.items():
                    setattr(row, key, value)

            completed = PricingCompletedEvent(
                event_id=event_id or result.external_id,
                result=result,
                request_id=request_id,
            )
            session.add(
                OutboxMessageRow(
                    routing_key=self._settings.routing_key_priced_success,
                    payload=completed.model_dump_json(),
                    headers_json=json.dumps(
                        {
                            "event_type": completed.event_type,
                            "schema_version": completed.schema_version,
                            "event_id": completed.event_id,
                            "x-request-id": completed.request_id or "",
                        }
                    ),
                    created_at=datetime.now(UTC).replace(tzinfo=None),
                    status="pending",
                    claimed_at=None,
                )
            )
            await session.commit()

    async def claim_pending(self, limit: int = 50) -> list[OutboxPending]:
        """Atomically claim pending/stale outbox rows (SKIP LOCKED)."""
        now = datetime.now(UTC).replace(tzinfo=None)
        stale_before = now - _CLAIM_STALE_AFTER
        claimed: list[OutboxPending] = []
        async with self._session_factory() as session:
            for _ in range(limit):
                row = await session.scalar(
                    select(OutboxMessageRow)
                    .where(
                        or_(
                            OutboxMessageRow.status == "pending",
                            (
                                (OutboxMessageRow.status == "processing")
                                & (OutboxMessageRow.claimed_at < stale_before)
                            ),
                        )
                    )
                    .order_by(OutboxMessageRow.id)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
                if row is None:
                    break
                row.status = "processing"
                row.claimed_at = now
                headers_raw = json.loads(row.headers_json or "{}")
                headers = (
                    {
                        str(key): str(value)
                        for key, value in headers_raw.items()
                        if value is not None
                    }
                    if isinstance(headers_raw, dict)
                    else {}
                )
                claimed.append(
                    {
                        "id": row.id,
                        "routing_key": row.routing_key,
                        "payload": row.payload.encode("utf-8"),
                        "headers": headers,
                    }
                )
            await session.commit()
        return claimed

    async def mark_published(self, outbox_id: int) -> None:
        async with self._session_factory() as session:
            row = await session.get(OutboxMessageRow, outbox_id)
            if row is None:
                return
            row.status = "published"
            row.published_at = datetime.now(UTC).replace(tzinfo=None)
            row.claimed_at = None
            await session.commit()

    async def release_outbox_claim(self, outbox_id: int) -> None:
        """Return a failed outbox publish attempt to pending."""
        async with self._session_factory() as session:
            row = await session.get(OutboxMessageRow, outbox_id)
            if row is not None and row.status == "processing":
                row.status = "pending"
                row.claimed_at = None
                await session.commit()

    async def get(self, external_id: str) -> PricingResult:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(PricingResultRow).where(
                    PricingResultRow.external_id == external_id
                )
            )
            if row is None:
                raise PricingNotFoundError(external_id)
            return self._to_schema(row)

    async def count_results(self) -> int:
        async with self._session_factory() as session:
            total = await session.scalar(
                select(func.count()).select_from(PricingResultRow)
            )
            return int(total or 0)

    async def list_recent(
        self,
        *,
        limit: int = 20,
        before_priced_at: datetime | None = None,
    ) -> list[PricingResult]:
        async with self._session_factory() as session:
            stmt = select(PricingResultRow).order_by(PricingResultRow.priced_at.desc())
            if before_priced_at is not None:
                cursor = before_priced_at
                if cursor.tzinfo is not None:
                    cursor = cursor.astimezone(UTC).replace(tzinfo=None)
                stmt = stmt.where(PricingResultRow.priced_at < cursor)
            stmt = stmt.limit(max(1, min(limit, 100)))
            rows = (await session.scalars(stmt)).all()
            return [self._to_schema(row) for row in rows]

    async def count_inbox_by_status(self) -> dict[str, int]:
        async with self._session_factory() as session:
            rows = await session.execute(
                select(ProcessedEventRow.status, func.count()).group_by(
                    ProcessedEventRow.status
                )
            )
            counts: dict[str, int] = {"processing": 0, "completed": 0}
            for status, count in rows.all():
                counts[str(status or "unknown")] = int(count)
            return counts

    async def count_outbox_by_status(self) -> dict[str, int]:
        async with self._session_factory() as session:
            rows = await session.execute(
                select(OutboxMessageRow.status, func.count()).group_by(
                    OutboxMessageRow.status
                )
            )
            counts: dict[str, int] = {
                "pending": 0,
                "processing": 0,
                "published": 0,
            }
            for status, count in rows.all():
                counts[str(status or "unknown")] = int(count)
            return counts

    @staticmethod
    def _to_row_values(result: PricingResult) -> PricingRowValues:
        priced_at = result.priced_at
        if priced_at.tzinfo is not None:
            priced_at = priced_at.astimezone(UTC).replace(tzinfo=None)
        return {
            "external_id": result.external_id,
            "bid_price": result.bid_price,
            "recommended_dealer_bid": result.recommended_dealer_bid,
            "estimated_turnover_days": result.estimated_turnover_days,
            "target_margin_pct": result.target_margin_pct,
            "price_low": result.price_low,
            "price_high": result.price_high,
            "currency": result.currency,
            "model_version": result.model_version,
            "meta_json": json.dumps(result.meta),
            "priced_at": priced_at or datetime.now(UTC).replace(tzinfo=None),
        }

    @staticmethod
    def _to_schema(row: PricingResultRow) -> PricingResult:
        meta: dict[str, object]
        try:
            loaded = json.loads(row.meta_json or "{}")
            meta = loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            meta = {}
        priced_at = row.priced_at
        if priced_at.tzinfo is None:
            priced_at = priced_at.replace(tzinfo=UTC)
        return PricingResult(
            external_id=row.external_id,
            bid_price=row.bid_price,
            recommended_dealer_bid=row.recommended_dealer_bid,
            estimated_turnover_days=row.estimated_turnover_days,
            target_margin_pct=row.target_margin_pct,
            price_low=row.price_low,
            price_high=row.price_high,
            currency=row.currency,
            model_version=row.model_version,
            priced_at=priced_at,
            meta=meta,
        )
