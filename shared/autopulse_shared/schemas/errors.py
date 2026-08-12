"""Shared HTTP error payloads for OpenAPI / handlers."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """FastAPI-compatible error body (``{"detail": "..."}``)."""

    detail: str = Field(..., description="Human-readable error message")
