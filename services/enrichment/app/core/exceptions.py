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
        retryable: bool = True,
    ) -> None:
        self.stage: EnrichmentStage | None = stage
        self.retryable: bool = retryable
        super().__init__(message)


class MalformedMessageError(ValueError):
    """Payload cannot be parsed into a domain event (poison message)."""


class PermanentEnrichmentError(EnrichmentError):
    """Non-retryable enrichment failure (bad input / client 4xx)."""

    def __init__(
        self,
        message: str,
        *,
        stage: EnrichmentStage | None = None,
    ) -> None:
        super().__init__(message, stage=stage, retryable=False)
