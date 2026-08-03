"""Enrichment-domain exceptions."""


class ListingNotFoundError(LookupError):
    def __init__(self, external_id: str) -> None:
        self.external_id = external_id
        super().__init__(f"Listing not found: {external_id}")


class EnrichmentError(RuntimeError):
    """Raised when enrichment aggregation fails."""

    def __init__(self, message: str, *, stage: str | None = None) -> None:
        self.stage = stage
        super().__init__(message)
