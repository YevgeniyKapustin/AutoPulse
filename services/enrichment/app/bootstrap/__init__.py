"""Composition and process bootstrap for enrichment entrypoints."""

from services.enrichment.app.bootstrap.container import (
    EnrichmentRuntime,
    attach_publisher,
    build_runtime,
    shutdown_runtime,
    start_consumer,
)
from services.enrichment.app.bootstrap.process import (
    assert_uvicorn_run_mode,
    attach_messaging_for_mode,
    drain_runtime_then_stop_metrics,
    start_metrics_server,
)
from services.enrichment.app.bootstrap.readiness import check_readiness

__all__ = [
    "EnrichmentRuntime",
    "assert_uvicorn_run_mode",
    "attach_messaging_for_mode",
    "attach_publisher",
    "build_runtime",
    "check_readiness",
    "drain_runtime_then_stop_metrics",
    "shutdown_runtime",
    "start_consumer",
    "start_metrics_server",
]
