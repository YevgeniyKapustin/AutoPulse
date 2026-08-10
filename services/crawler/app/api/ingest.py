"""HTTP API for multi-source ingest."""

from __future__ import annotations

import json
from typing import Any, Literal, TypedDict

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from services.crawler.app.core.exceptions import AdapterError, UnknownSourceError
from services.crawler.app.samples import list_sample_sources, load_sample_payload
from services.crawler.app.service import IngestService

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestAccepted(TypedDict):
    status: Literal["accepted"]
    source: str
    external_id: str
    event_id: str


@router.get("/sources")
async def list_sources(request: Request) -> dict[str, list[str]]:
    ingest: IngestService = request.app.state.ingest
    return {"sources": ingest.list_sources()}


@router.get("/samples")
async def list_samples() -> dict[str, list[str]]:
    return {"sources": list_sample_sources()}


@router.post(
    "/samples/{source}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=None,
)
async def ingest_sample(
    source: str,
    request: Request,
) -> IngestAccepted | JSONResponse:
    """Normalize a built-in fixture through the matching adapter."""
    ingest: IngestService = request.app.state.ingest
    request_id: str | None = getattr(request.state, "request_id", None)
    try:
        payload = load_sample_payload(source)
        result = await ingest.ingest(source, payload, request_id=request_id)
    except UnknownSourceError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )
    except (AdapterError, FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)},
        )
    return {
        "status": "accepted",
        "source": result.source,
        "external_id": result.external_id,
        "event_id": result.event_id,
    }


@router.post(
    "/{source}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=None,
)
async def ingest_source(
    source: str,
    payload: dict[str, Any],
    request: Request,
) -> IngestAccepted | JSONResponse:
    ingest: IngestService = request.app.state.ingest
    request_id: str | None = getattr(request.state, "request_id", None)
    try:
        result = await ingest.ingest(source, payload, request_id=request_id)
    except UnknownSourceError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )
    except AdapterError as exc:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)},
        )
    return {
        "status": "accepted",
        "source": result.source,
        "external_id": result.external_id,
        "event_id": result.event_id,
    }
