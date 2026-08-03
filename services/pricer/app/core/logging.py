"""Service logging — delegates to shared structlog setup."""

from __future__ import annotations

from autopulse_shared.logging import setup_logging as _setup_logging


def setup_logging(
    level: str = "INFO",
    *,
    service: str = "pricer",
    environment: str = "local",
) -> None:
    _setup_logging(level=level, service=service, environment=environment)
