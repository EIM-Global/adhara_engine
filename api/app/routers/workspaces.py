"""
Workspace CRUD endpoints with RBAC authorization.

Workspace operations require:
  - Create: WORKSPACE_CREATE (on parent tenant)
  - View/List: WORKSPACE_VIEW
  - Update: WORKSPACE_UPDATE
  - Delete: WORKSPACE_DELETE
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import require_auth
from app.core.authorize import authorize
from app.core.database import get_db
from app.core.permissions import Permission
from app.core.slugify import slugify
from app.models.tenant import Tenant
from app.models.workspace import Workspace
from app.schemas.workspace import WorkspaceCreate, WorkspaceResponse, WorkspaceUpdate

router = APIRouter(tags=["workspaces"])


@router.post(
    "/api/v1/tenants/{tenant_id}/workspaces",
    response_model=WorkspaceResponse,
    status_code=201,
)
async def create_workspace(
    tenant_id: uuid.UUID,
    data: WorkspaceCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    await authorize(user, Permission.WORKSPACE_CREATE, "tenant", tenant_id, db)

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    slug = data.slug or slugify(data.name)
    existing = (
        db.query(Workspace)
        .filter(Workspace.tenant_id == tenant_id, Workspace.slug == slug)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Workspace with slug '{slug}' already exists in this tenant",
        )

    workspace = Workspace(
        tenant_id=tenant_id,
        name=data.name,
        slug=slug,
        adhara_api_url=data.adhara_api_url,
        adhara_api_key=data.adhara_api_key,
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


@router.get(
    "/api/v1/tenants/{tenant_id}/workspaces",
    response_model=list[WorkspaceResponse],
)
async def list_workspaces(
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    await authorize(user, Permission.WORKSPACE_VIEW, "tenant", tenant_id, db)
    return (
        db.query(Workspace)
        .filter(Workspace.tenant_id == tenant_id)
        .order_by(Workspace.created_at.desc())
        .all()
    )


@router.get("/api/v1/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    await authorize(user, Permission.WORKSPACE_VIEW, "workspace", workspace_id, db)
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


@router.patch("/api/v1/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: uuid.UUID,
    data: WorkspaceUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    await authorize(user, Permission.WORKSPACE_UPDATE, "workspace", workspace_id, db)
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(workspace, field, value)

    db.commit()
    db.refresh(workspace)
    return workspace


@router.delete("/api/v1/workspaces/{workspace_id}", status_code=204)
async def delete_workspace(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    await authorize(user, Permission.WORKSPACE_DELETE, "workspace", workspace_id, db)
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    db.delete(workspace)
    db.commit()
