"""JSON admin/ops API for enrichment."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from services.enrichment.app.admin.schemas import (
    AdminOverview,
    ListingAdminPage,
    ListingStatusFilter,
    PipelineDetail,
    ReEnrichAccepted,
)
from services.enrichment.app.admin.service import AdminService
from services.enrichment.app.core.ui_auth import require_ui_auth

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_ui_auth)],
)

LimitQuery = Annotated[int, Query(ge=1, le=100)]
CursorQuery = Annotated[datetime | None, Query()]
StatusQuery = Annotated[ListingStatusFilter | None, Query(alias="status")]


def _require_admin(request: Request) -> AdminService:
    admin: AdminService | None = getattr(request.app.state, "admin", None)
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin API is disabled",
        )
    return admin


@router.get("/overview", response_model=AdminOverview)
async def admin_overview(request: Request) -> AdminOverview:
    return await _require_admin(request).overview()


@router.get("/listings", response_model=ListingAdminPage)
async def admin_listings(
    request: Request,
    limit: LimitQuery = 20,
    cursor: CursorQuery = None,
    status_filter: StatusQuery = None,
) -> ListingAdminPage:
    return await _require_admin(request).list_listings(
        limit=limit,
        before_updated_at=cursor,
        status=status_filter,
    )


@router.get("/pipeline/{external_id}", response_model=PipelineDetail)
async def admin_pipeline(external_id: str, request: Request) -> PipelineDetail:
    return await _require_admin(request).pipeline(external_id)


@router.post(
    "/listings/{external_id}/re-enrich",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ReEnrichAccepted,
)
async def admin_re_enrich(
    external_id: str,
    request: Request,
) -> ReEnrichAccepted:
    request_id: str | None = getattr(request.state, "request_id", None)
    return await _require_admin(request).re_enrich(
        external_id,
        request_id=request_id,
    )
