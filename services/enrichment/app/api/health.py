"""Liveness and readiness probes for enrichment."""

from __future__ import annotations

from typing import Literal, TypedDict

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from services.enrichment.app.bootstrap.container import EnrichmentRuntime
from services.enrichment.app.bootstrap.readiness import check_readiness

router = APIRouter(tags=["health"])


class LivenessResponse(TypedDict):
    status: Literal["ok"]
    service: Literal["enrichment"]


class ReadinessResponse(TypedDict):
    status: Literal["ok", "unavailable"]
    service: Literal["enrichment"]
    checks: dict[str, str]


@router.get("/health/live")
async def liveness() -> LivenessResponse:
    """Liveness probe: process is up (restart-worthy if this fails)."""
    return {"status": "ok", "service": "enrichment"}


@router.get(
    "/health/ready",
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "MongoDB or RabbitMQ unavailable",
        }
    },
)
async def readiness(request: Request) -> ReadinessResponse | JSONResponse:
    """Readiness probe: MongoDB + RabbitMQ available for business traffic."""
    runtime: EnrichmentRuntime = request.app.state.runtime
    ready, checks = await check_readiness(runtime)
    body: ReadinessResponse = {
        "status": "ok" if ready else "unavailable",
        "service": "enrichment",
        "checks": checks,
    }
    if not ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=body,
        )
    return body
