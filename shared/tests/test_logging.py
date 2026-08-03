"""Unit tests for shared structlog JSON setup."""

from __future__ import annotations

import json
import logging
from io import StringIO

from autopulse_shared.logging import (
    bind_trace_context,
    clear_contextvars,
    setup_logging,
)


def test_setup_logging_emits_json_with_trace_id() -> None:
    setup_logging(level="INFO", service="enrichment", environment="test")
    root = logging.getLogger()
    buffer = StringIO()
    assert root.handlers
    handler = root.handlers[0]
    formatter = handler.formatter
    assert formatter is not None
    capture = logging.StreamHandler(buffer)
    capture.setFormatter(formatter)
    capture.setLevel(logging.INFO)
    root.addHandler(capture)

    clear_contextvars()
    bind_trace_context(trace_id="trace-abc", request_id="trace-abc")
    try:
        logging.getLogger("test.logger").info(
            "hello_world",
            extra={"event_id": "evt-1"},
        )
    finally:
        clear_contextvars()
        root.removeHandler(capture)

    line = buffer.getvalue().strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["event"] == "hello_world"
    assert payload["service"] == "enrichment"
    assert payload["environment"] == "test"
    assert payload["trace_id"] == "trace-abc"
    assert payload["event_id"] == "evt-1"
    assert "timestamp" in payload
    assert str(payload["level"]).lower() == "info"
