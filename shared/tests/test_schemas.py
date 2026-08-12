import json

import pytest
from pydantic import ValidationError

from autopulse_shared.schemas.events import (
    EventType,
    ListingEnrichedEvent,
    RawListingEvent,
)
from autopulse_shared.schemas.listing import (
    EnrichedListing,
    ListingOptions,
    ListingSource,
    RawListing,
)


def test_raw_listing_schema() -> None:
    listing = RawListing(
        external_id="ext-1",
        title="BMW 320i",
        description="M-Sport package, panorama roof",
        asking_price=18500,
    )
    assert listing.external_id == "ext-1"
    options = ListingOptions(packages=["M-Sport"], features=["panorama"])
    assert "M-Sport" in options.packages


def test_event_id_auto_generated() -> None:
    event = RawListingEvent(
        listing=RawListing(external_id="ext-2", source=ListingSource.MANUAL),
    )
    assert event.event_id
    assert event.event_type is EventType.RAW_CREATED


def test_event_type_literal_rejects_mismatch() -> None:
    listing = RawListing(external_id="ext-3", source=ListingSource.MANUAL)
    with pytest.raises(ValidationError):
        RawListingEvent.model_validate(
            {
                "event_type": EventType.ENRICHMENT_FAILED,
                "listing": listing.model_dump(mode="json"),
            }
        )


def test_http_url_serializes_as_string_in_json_mode() -> None:
    listing = EnrichedListing.model_validate(
        {
            "external_id": "ext-4",
            "source": ListingSource.COPART,
            "url": "https://example.com/lot/1",
            "image_urls": ["https://example.com/a.jpg"],
            "llm_done": True,
            "cv_done": True,
        }
    )
    event = ListingEnrichedEvent(listing=listing)
    payload = json.loads(event.model_dump_json())
    assert payload["listing"]["url"] == "https://example.com/lot/1"
    assert payload["listing"]["image_urls"] == ["https://example.com/a.jpg"]
    dumped = event.model_dump(mode="json")
    assert isinstance(dumped["listing"]["url"], str)
