"""Liveness and readiness probes for pricer."""

from __future__ import annotations

from typing import Literal, TypedDict

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from services.pricer.app.bootstrap.container import PricerRuntime
from services.pricer.app.bootstrap.readiness import check_readiness

router = APIRouter(tags=["health"])


class LivenessResponse(TypedDict):
    status: Literal["ok"]
    service: Literal["pricer"]


class ReadinessResponse(TypedDict):
    status: Literal["ok", "unavailable"]
    service: Literal["pricer"]
    checks: dict[str, str]


@router.get("/health/live")
async def liveness() -> LivenessResponse:
    """Liveness probe: process is up (restart-worthy if this fails)."""
    return {"status": "ok", "service": "pricer"}


@router.get(
    "/health/ready",
    response_model=None,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "MySQL or RabbitMQ unavailable",
        }
    },
)
async def readiness(request: Request) -> ReadinessResponse | JSONResponse:
    """Readiness probe: MySQL (+ RabbitMQ when consumer is running)."""
    runtime: PricerRuntime = request.app.state.runtime
    ready, checks = await check_readiness(runtime)
    body: ReadinessResponse = {
        "status": "ok" if ready else "unavailable",
        "service": "pricer",
        "checks": checks,
    }
    if not ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=body,
        )
    return body
