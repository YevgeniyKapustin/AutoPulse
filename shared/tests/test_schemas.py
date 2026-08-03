from autopulse_shared.schemas.listing import ListingOptions, RawListing


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
