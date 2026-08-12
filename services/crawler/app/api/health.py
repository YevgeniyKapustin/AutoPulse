"""Crawler process health endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", response_model=None)
async def ready() -> dict[str, str] | JSONResponse:
    # Crawler is ready when the process is up; enrichment reachability
    # is checked on each ingest call.
    return {"status": "ready"}
