"""SQLAlchemy async repository for pricing results."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from autopulse_shared.schemas.pricing import PricingResult
from services.pricer.app.core.exceptions import PricingNotFoundError
from services.pricer.app.models.pricing import PricingResultRow


class PricingRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, result: PricingResult) -> None:
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
