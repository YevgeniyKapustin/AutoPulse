from datetime import UTC, datetime

from pydantic import BaseModel, Field


class PricingResult(BaseModel):
    external_id: str
    bid_price: float
    recommended_dealer_bid: float
    estimated_turnover_days: int
    target_margin_pct: float
    price_low: float
    price_high: float
    currency: str = "USD"
    model_version: str = "rules-v0"
    priced_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    meta: dict[str, object] = Field(default_factory=dict)
