"""
Preview environment CRUD endpoints.

Endpoints:
  GET    /api/v1/sites/{id}/previews       — list preview environments
  GET    /api/v1/previews/{id}             — get preview details
  POST   /api/v1/sites/{id}/previews       — manually create a preview
  DELETE /api/v1/previews/{id}             — destroy a preview
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import require_auth
from app.core.authorize import authorize
from app.core.database import get_db
from app.core.permissions import Permission
from app.models.preview_environment import PreviewEnvironment
from app.models.site import Site
from app.services.preview_manager import create_or_update_preview, destroy_preview

router = APIRouter(tags=["previews"])


class PreviewCreate(BaseModel):
    pr_number: int = Field(..., gt=0)
    pr_branch: str = Field(..., min_length=1, max_length=255)
    commit_sha: str = Field(..., min_length=7, max_length=64)
    pr_title: str | None = Field(None, max_length=512)
    pr_author: str | None = Field(None, max_length=255)
    pr_url: str | None = Field(None, max_length=1024)
    git_provider: str = Field(..., pattern=r"^(github|gitlab)$")


class PreviewResponse(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    pr_number: int
    pr_title: str | None
    pr_author: str | None
    pr_branch: str
    pr_url: str | None
    git_provider: str
    commit_sha: str | None
    pipeline_run_id: uuid.UUID | None
    status: str
    host_port: int | None
    preview_url: str | None
    image_tag: str | None
    ttl_hours: int
    pr_state: str
    destroy_reason: str | None
    created_at: datetime
    updated_at: datetime | None
    destroyed_at: datetime | None

    model_config = {"from_attributes": True}


@router.get(
    "/api/v1/sites/{site_id}/previews",
    response_model=list[PreviewResponse],
)
async def list_previews(
    site_id: uuid.UUID,
    include_destroyed: bool = False,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """List preview environments for a site."""
    await authorize(user, Permission.SITE_VIEW, "site", site_id, db)

    query = db.query(PreviewEnvironment).filter(
        PreviewEnvironment.site_id == site_id,
    )
    if not include_destroyed:
        query = query.filter(PreviewEnvironment.status != "destroyed")

    return query.order_by(PreviewEnvironment.created_at.desc()).all()


@router.get(
    "/api/v1/previews/{preview_id}",
    response_model=PreviewResponse,
)
async def get_preview(
    preview_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get a preview environment by ID."""
    preview = (
        db.query(PreviewEnvironment)
        .filter(PreviewEnvironment.id == preview_id)
        .first()
    )
    if not preview:
        raise HTTPException(status_code=404, detail="Preview not found")

    await authorize(user, Permission.SITE_VIEW, "site", preview.site_id, db)
    return preview


@router.post(
    "/api/v1/sites/{site_id}/previews",
    response_model=PreviewResponse,
    status_code=202,
)
async def create_preview(
    site_id: uuid.UUID,
    data: PreviewCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Manually create a preview environment for a PR."""
    await authorize(user, Permission.SITE_DEPLOY, "site", site_id, db)

    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    preview = await create_or_update_preview(
        db=db,
        site=site,
        pr_number=data.pr_number,
        pr_branch=data.pr_branch,
        commit_sha=data.commit_sha,
        git_provider=data.git_provider,
        pr_title=data.pr_title,
        pr_author=data.pr_author,
        pr_url=data.pr_url,
    )

    return preview


@router.delete("/api/v1/previews/{preview_id}", status_code=204)
async def delete_preview(
    preview_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Destroy a preview environment."""
    preview = (
        db.query(PreviewEnvironment)
        .filter(PreviewEnvironment.id == preview_id)
        .first()
    )
    if not preview:
        raise HTTPException(status_code=404, detail="Preview not found")

    await authorize(user, Permission.SITE_DEPLOY, "site", preview.site_id, db)

    if preview.status == "destroyed":
        raise HTTPException(status_code=409, detail="Preview already destroyed")

    await destroy_preview(db, preview, reason="manual")
