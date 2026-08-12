"""Pricer-domain exceptions."""

from __future__ import annotations


class PricingNotFoundError(LookupError):
    def __init__(self, external_id: str) -> None:
        self.external_id = external_id
        super().__init__(f"Pricing result not found: {external_id}")


class PricingError(RuntimeError):
    """Raised when pricing fails."""

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        self.retryable = retryable
        super().__init__(message)


class PermanentPricingError(PricingError):
    def __init__(self, message: str) -> None:
        super().__init__(message, retryable=False)


class MalformedMessageError(ValueError):
    """Payload cannot be parsed into a domain event."""
