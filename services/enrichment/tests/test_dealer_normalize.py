"""Dealer normalize unit tests."""

import pytest
from services.enrichment.app.dealer.normalize import (
    DealerSubmitError,
    listing_from_form,
    listing_from_json_text,
)


def test_form_builds_copart_listing() -> None:
    listing = listing_from_form(
        source="copart",
        external_ref="12345678",
        title="2019 BMW 320i",
        make="BMW",
        model="320i",
        year="2019",
        mileage_km="72000",
        asking_price="18500",
        image_urls_text="https://example.com/a.jpg\nhttps://example.com/b.jpg",
    )
    assert listing.external_id == "copart-12345678"
    assert listing.source.value == "copart"
    assert listing.asking_price == 18500
    assert len(listing.image_urls) == 2


def test_json_raw_listing_passthrough() -> None:
    listing = listing_from_json_text(
        """
        {
          "external_id": "manual-9",
          "source": "manual",
          "title": "Test",
          "currency": "USD"
        }
        """
    )
    assert listing.external_id == "manual-9"
    assert listing.title == "Test"


def test_json_vendor_copart_shape() -> None:
    listing = listing_from_json_text(
        '{"lotNumber":"55","make":"Ford","model":"Focus","year":2020}'
    )
    assert listing.external_id == "copart-55"
    assert listing.make == "Ford"


def test_form_requires_id() -> None:
    with pytest.raises(DealerSubmitError):
        listing_from_form(source="manual", external_ref="  ")
