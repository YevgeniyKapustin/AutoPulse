"""Domain exception → HTTP response mapping for the enrichment API."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from services.enrichment.app.core.exceptions import ListingNotFoundError


def register_exception_handlers(application: FastAPI) -> None:
    """Map enrichment domain errors to HTTP status codes."""

    @application.exception_handler(ListingNotFoundError)
    async def listing_not_found_handler(
        _request: Request,
        exc: ListingNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )
