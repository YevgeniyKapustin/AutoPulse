"""Composition and process bootstrap for pricer entrypoints."""

from services.pricer.app.bootstrap.container import (
    PricerRuntime,
    build_runtime,
    shutdown_runtime,
    start_consumer,
)
from services.pricer.app.bootstrap.process import (
    assert_uvicorn_run_mode,
    attach_messaging_for_mode,
    drain_runtime_then_stop_metrics,
    start_metrics_server,
)
from services.pricer.app.bootstrap.readiness import check_readiness

__all__ = [
    "PricerRuntime",
    "assert_uvicorn_run_mode",
    "attach_messaging_for_mode",
    "build_runtime",
    "check_readiness",
    "drain_runtime_then_stop_metrics",
    "shutdown_runtime",
    "start_consumer",
    "start_metrics_server",
]
