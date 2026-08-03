"""Shared structlog setup with stdlib bridge (JSON → stdout)."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from typing import Any

import structlog
from structlog.types import EventDict, Processor


def _add_service_fields(
    service: str,
    environment: str,
) -> Processor:
    def processor(
        _logger: logging.Logger,
        _method_name: str,
        event_dict: EventDict,
    ) -> EventDict:
        event_dict.setdefault("service", service)
        event_dict.setdefault("environment", environment)
        return event_dict

    return processor


def _normalize_trace_id(
    _logger: logging.Logger,
    _method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Promote request_id to trace_id when trace_id is absent."""
    if "trace_id" not in event_dict and event_dict.get("request_id"):
        event_dict["trace_id"] = event_dict["request_id"]
    return event_dict


def setup_logging(
    *,
    level: str = "INFO",
    service: str,
    environment: str = "local",
) -> None:
    """Configure structlog + root stdlib logger for JSON stdout."""
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.ExtraAdder(),
        _normalize_trace_id,
        _add_service_fields(service, environment),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Keep uvicorn access noise under control; still JSON-formatted.
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)


def get_logger(name: str | None = None) -> Any:
    """Return a bound structlog logger (stdlib-backed)."""
    return structlog.get_logger(name)


def bind_trace_context(
    *,
    trace_id: str | None = None,
    event_id: str | None = None,
    external_id: str | None = None,
    request_id: str | None = None,
) -> None:
    """Bind correlation fields for the current logging context."""
    payload: dict[str, str] = {}
    resolved_trace = trace_id or request_id
    if resolved_trace:
        payload["trace_id"] = resolved_trace
    if request_id:
        payload["request_id"] = request_id
    if event_id:
        payload["event_id"] = event_id
    if external_id:
        payload["external_id"] = external_id
    if payload:
        structlog.contextvars.bind_contextvars(**payload)


clear_contextvars: Callable[[], None] = structlog.contextvars.clear_contextvars
