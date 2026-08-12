"""Built-in sample fixture loading."""

import pytest
from services.crawler.app.adapters import AdapterRegistry
from services.crawler.app.core.exceptions import UnknownSourceError
from services.crawler.app.samples import list_sample_sources, load_sample_payload


def test_sample_sources_match_fixtures() -> None:
    assert list_sample_sources() == ["copart", "iaai"]


def test_copart_sample_normalizes() -> None:
    payload = load_sample_payload("copart")
    listing = AdapterRegistry().get("copart").to_raw_listing(payload)
    assert listing.external_id == "copart-12345678"
    assert listing.make == "BMW"


def test_iaai_sample_normalizes() -> None:
    payload = load_sample_payload("iaai")
    listing = AdapterRegistry().get("iaai").to_raw_listing(payload)
    assert listing.external_id == "iaai-98765432"
    assert listing.make == "Toyota"


def test_unknown_sample_source() -> None:
    with pytest.raises(UnknownSourceError):
        load_sample_payload("manual")
