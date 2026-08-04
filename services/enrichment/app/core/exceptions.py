"""Enrichment-domain exceptions."""

from __future__ import annotations

from typing import Literal

EnrichmentStage = Literal["llm", "cv", "publish", "aggregate"]


class ListingNotFoundError(LookupError):
    def __init__(self, external_id: str) -> None:
        self.external_id: str = external_id
        super().__init__(f"Listing not found: {external_id}")


class EnrichmentError(RuntimeError):
    """Raised when enrichment aggregation fails."""

    def __init__(
        self,
        message: str,
        *,
        stage: EnrichmentStage | None = None,
    ) -> None:
        self.stage: EnrichmentStage | None = stage
        super().__init__(message)
