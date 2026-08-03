"""SQLAlchemy ORM models for pricing persistence."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PricingResultRow(Base):
    __tablename__ = "pricing_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    bid_price: Mapped[float] = mapped_column(Float)
    recommended_dealer_bid: Mapped[float] = mapped_column(Float)
    estimated_turnover_days: Mapped[int] = mapped_column(Integer)
    target_margin_pct: Mapped[float] = mapped_column(Float)
    price_low: Mapped[float] = mapped_column(Float)
    price_high: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    model_version: Mapped[str] = mapped_column(String(64), default="rules-v0")
    meta_json: Mapped[str] = mapped_column(Text, default="{}")
    priced_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )
