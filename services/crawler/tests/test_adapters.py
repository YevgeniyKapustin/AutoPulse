"""Unit tests for crawler source adapters."""

from pathlib import Path

import pytest
from services.crawler.app.adapters import AdapterRegistry
from services.crawler.app.adapters.copart import CopartAdapter
from services.crawler.app.adapters.iaai import IaaiAdapter
from services.crawler.app.adapters.manual import ManualAdapter
from services.crawler.app.core.exceptions import AdapterError, UnknownSourceError
from services.crawler.app.service import IngestService

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_copart_adapter_normalizes_fixture() -> None:
    import json

    payload = json.loads((_FIXTURES / "copart_lot.json").read_text(encoding="utf-8"))
    listing = CopartAdapter().to_raw_listing(payload)
    assert listing.external_id == "copart-12345678"
    assert listing.source.value == "copart"
    assert listing.make == "BMW"
    assert listing.mileage_km == 72002  # 44740 mi → km
    assert listing.asking_price == 18500
    assert listing.raw_payload["lotNumber"] == "12345678"


def test_iaai_adapter_normalizes_fixture() -> None:
    import json

    payload = json.loads((_FIXTURES / "iaai_stock.json").read_text(encoding="utf-8"))
    listing = IaaiAdapter().to_raw_listing(payload)
    assert listing.external_id == "iaai-98765432"
    assert listing.source.value == "iaai"
    assert listing.mileage_km == 91000
    assert listing.asking_price == 9200


def test_manual_adapter_accepts_raw_listing_shape() -> None:
    listing = ManualAdapter().to_raw_listing(
        {
            "external_id": "manual-1",
            "title": "Manual car",
            "currency": "USD",
        }
    )
    assert listing.external_id == "manual-1"
    assert listing.source.value == "manual"


def test_copart_missing_lot_raises() -> None:
    with pytest.raises(AdapterError):
        CopartAdapter().to_raw_listing({"make": "BMW"})


def test_registry_unknown_source() -> None:
    with pytest.raises(UnknownSourceError):
        AdapterRegistry().get("cargurus")


@pytest.mark.asyncio
async def test_ingest_service_publishes_normalized_listing() -> None:
    published: list[str] = []

    class _Pub:
        async def publish(self, listing, *, request_id=None) -> str:
            published.append(listing.external_id)
            return "evt-1"

        async def aclose(self) -> None:
            return None

    service = IngestService(registry=AdapterRegistry(), publisher=_Pub())
    result = await service.ingest(
        "copart",
        {
            "lotNumber": "42",
            "year": 2020,
            "make": "Ford",
            "model": "Focus",
        },
    )
    assert result.external_id == "copart-42"
    assert result.event_id == "evt-1"
    assert published == ["copart-42"]
