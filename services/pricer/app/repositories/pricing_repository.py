"""SQLAlchemy async repository for pricing results + inbox/outbox."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
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


class PricingRepository:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings or Settings()

    async def try_claim_event(self, event_id: str) -> bool:
        async with self._session_factory() as session:
            session.add(
                ProcessedEventRow(
                    event_id=event_id,
                    processed_at=datetime.now(UTC).replace(tzinfo=None),
                )
            )
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                return False
            return True

    async def save(self, result: PricingResult, *, event_id: str | None = None) -> None:
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
                            "x-request-id": completed.request_id,
                        }
                    ),
                    created_at=datetime.now(UTC).replace(tzinfo=None),
                )
            )
            await session.commit()

    async def list_pending_outbox(self, limit: int = 50) -> list[OutboxMessageRow]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(OutboxMessageRow)
                .where(OutboxMessageRow.published_at.is_(None))
                .order_by(OutboxMessageRow.id)
                .limit(limit)
            )
            return list(rows)

    async def mark_outbox_published(self, outbox_id: int) -> None:
        async with self._session_factory() as session:
            row = await session.get(OutboxMessageRow, outbox_id)
            if row is None:
                return
            row.published_at = datetime.now(UTC).replace(tzinfo=None)
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

    @staticmethod
    def _to_row_values(result: PricingResult) -> dict[str, object]:
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
