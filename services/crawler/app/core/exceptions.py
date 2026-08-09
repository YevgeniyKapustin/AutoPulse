"""Crawler exception types."""

from __future__ import annotations


class AdapterError(ValueError):
    """Source payload could not be normalized to RawListing."""


class UnknownSourceError(KeyError):
    """No adapter registered for the requested source."""
