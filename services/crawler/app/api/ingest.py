"""HTTP API for multi-source ingest."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from services.crawler.app.core.exceptions import AdapterError, UnknownSourceError
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


@router.post("/{source}", status_code=status.HTTP_202_ACCEPTED)
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
