"""Service logging — delegates to shared structlog setup."""

from __future__ import annotations

from autopulse_shared.logging import LogLevel
from autopulse_shared.logging import setup_logging as _setup_logging


def setup_logging(
    level: LogLevel | str = "INFO",
    *,
    service: str = "enrichment",
    environment: str = "local",
) -> None:
    """Configure JSON logging for the enrichment process."""
    _setup_logging(level=level, service=service, environment=environment)
