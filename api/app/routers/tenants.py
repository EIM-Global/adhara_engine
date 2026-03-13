"""
Tenant CRUD endpoints with RBAC authorization.

Tenant operations require:
  - Create: TENANT_CREATE (platform-level)
  - View/List: TENANT_VIEW
  - Update: TENANT_UPDATE
  - Delete: TENANT_DELETE
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
from app.schemas.tenant import TenantCreate, TenantResponse, TenantUpdate

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])


@router.post("", response_model=TenantResponse, status_code=201)
async def create_tenant(
    data: TenantCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    await authorize(user, Permission.TENANT_CREATE, "platform", None, db)

    slug = data.slug or slugify(data.name)
    existing = db.query(Tenant).filter(Tenant.slug == slug).first()
    if existing:
        raise HTTPException(
            status_code=409, detail=f"Tenant with slug '{slug}' already exists"
        )

    tenant = Tenant(
        name=data.name,
        slug=slug,
        plan=data.plan,
        owner_email=data.owner_email,
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


@router.get("", response_model=list[TenantResponse])
async def list_tenants(
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    await authorize(user, Permission.TENANT_VIEW, "platform", None, db)
    return db.query(Tenant).order_by(Tenant.created_at.desc()).all()


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    await authorize(user, Permission.TENANT_VIEW, "tenant", tenant_id, db)
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: uuid.UUID,
    data: TenantUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    await authorize(user, Permission.TENANT_UPDATE, "tenant", tenant_id, db)
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(tenant, field, value)

    db.commit()
    db.refresh(tenant)
    return tenant


@router.delete("/{tenant_id}", status_code=204)
async def delete_tenant(
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    await authorize(user, Permission.TENANT_DELETE, "tenant", tenant_id, db)
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    db.delete(tenant)
    db.commit()
