from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class ListingSource(StrEnum):
    COPART = "copart"
    IAAI = "iaai"
    MANUAL = "manual"
    OTHER = "other"


class ListingOptions(BaseModel):
    """Options extracted from description / CV."""

    packages: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    owner_count: int | None = None
    notes: str | None = None


class DefectInfo(BaseModel):
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    image_url: HttpUrl | None = None
    bbox: list[float] | None = None


class RawListing(BaseModel):
    external_id: str
    source: ListingSource = ListingSource.OTHER
    url: HttpUrl | None = None
    title: str | None = None
    description: str | None = None
    make: str | None = None
    model: str | None = None
    year: int | None = None
    mileage_km: int | None = None
    asking_price: float | None = None
    currency: str = "USD"
    image_urls: list[HttpUrl] = Field(default_factory=list)
    raw_payload: dict[str, object] = Field(default_factory=dict)
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EnrichedListing(RawListing):
    """Raw listing plus enrichment outputs.

    Nullable base fields (make/model/year/…) stay nullable: enrichment may
    fill them later, but incomplete auction payloads remain valid.
    """

    options: ListingOptions = Field(default_factory=ListingOptions)
    defects: list[DefectInfo] = Field(default_factory=list)
    enrichment_version: str = "0.1.0"
    enriched_at: datetime | None = None
    llm_done: bool = False
    cv_done: bool = False

    @property
    def is_fully_enriched(self) -> bool:
        return self.llm_done and self.cv_done
