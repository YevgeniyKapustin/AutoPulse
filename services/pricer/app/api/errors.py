"""Domain exception → HTTP response mapping for the pricer API."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from services.pricer.app.core.exceptions import PricingNotFoundError


def register_exception_handlers(application: FastAPI) -> None:
    """Map pricer domain errors to HTTP status codes."""

    @application.exception_handler(PricingNotFoundError)
    async def pricing_not_found_handler(
        _request: Request,
        exc: PricingNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )
