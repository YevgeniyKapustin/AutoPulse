"""Server-rendered ops dashboard (Jinja + HTMX)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from services.enrichment.app.admin.service import AdminService

_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "admin" / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter(tags=["admin-ui"])


def _require_admin(request: Request) -> AdminService:
    if not getattr(request.app.state.settings, "admin_ui_enabled", False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin UI is disabled",
        )
    admin: AdminService | None = getattr(request.app.state, "admin", None)
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin UI is disabled",
        )
    return admin


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request) -> HTMLResponse:
    admin = _require_admin(request)
    overview = await admin.overview()
    listings = await admin.list_listings(limit=25)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "overview": overview,
            "listings": listings.items,
        },
    )


@router.get("/admin/listings/{external_id}", response_class=HTMLResponse)
async def admin_listing_detail(
    external_id: str,
    request: Request,
) -> HTMLResponse:
    admin = _require_admin(request)
    detail = await admin.pipeline(external_id)
    return templates.TemplateResponse(
        request,
        "listing_detail.html",
        {
            "detail": detail,
            "external_id": external_id,
        },
    )
