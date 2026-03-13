"""
Linked service CRUD endpoints.

Endpoints:
  GET    /api/v1/sites/{id}/services          — list linked services
  POST   /api/v1/sites/{id}/services          — provision a linked service
  DELETE /api/v1/sites/{id}/services/{svc_id} — deprovision a linked service
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import require_auth
from app.core.authorize import authorize
from app.core.database import get_db
from app.core.permissions import Permission
from app.models.linked_service import LinkedService
from app.models.site import Site
from app.services.linked_services import deprovision_service, provision_service

router = APIRouter(tags=["linked-services"])


class LinkedServiceCreate(BaseModel):
    """Request to provision a linked service."""

    service_type: str = Field(..., pattern=r"^(postgres|redis|minio_bucket)$")
    name: str | None = None
    delete_on_site_removal: bool = False


class LinkedServiceResponse(BaseModel):
    """Response for a linked service."""

    id: uuid.UUID
    site_id: uuid.UUID
    service_type: str
    name: str
    container_name: str | None
    status: str
    connection_env: dict | None
    delete_on_site_removal: bool

    model_config = {"from_attributes": True}


@router.get(
    "/api/v1/sites/{site_id}/linked-services",
    response_model=list[LinkedServiceResponse],
)
async def list_linked_services(
    site_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """List all linked services for a site."""
    await authorize(user, Permission.SITE_SERVICES, "site", site_id, db)
    return (
        db.query(LinkedService)
        .filter(LinkedService.site_id == site_id)
        .order_by(LinkedService.created_at.desc())
        .all()
    )


@router.post(
    "/api/v1/sites/{site_id}/linked-services",
    response_model=LinkedServiceResponse,
    status_code=201,
)
async def create_linked_service(
    site_id: uuid.UUID,
    data: LinkedServiceCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Provision a linked service for a site."""
    await authorize(user, Permission.SITE_SERVICES, "site", site_id, db)

    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    # Check for duplicate service type
    existing = (
        db.query(LinkedService)
        .filter(
            LinkedService.site_id == site_id,
            LinkedService.service_type == data.service_type,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Site already has a {data.service_type} service",
        )

    # Create record
    name = data.name or f"{site.slug}-{data.service_type}"
    linked_service = LinkedService(
        site_id=site.id,
        tenant_id=site.tenant_id,
        service_type=data.service_type,
        name=name,
        status="pending",
        delete_on_site_removal=data.delete_on_site_removal,
    )
    db.add(linked_service)
    db.commit()
    db.refresh(linked_service)

    # Provision the container
    try:
        linked_service = await provision_service(db, linked_service, site)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to provision {data.service_type}: {e}",
        )

    return linked_service


@router.delete(
    "/api/v1/sites/{site_id}/linked-services/{service_id}",
    status_code=200,
)
async def delete_linked_service(
    site_id: uuid.UUID,
    service_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Deprovision and remove a linked service."""
    await authorize(user, Permission.SITE_SERVICES, "site", site_id, db)

    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    linked_service = (
        db.query(LinkedService)
        .filter(
            LinkedService.id == service_id,
            LinkedService.site_id == site_id,
        )
        .first()
    )
    if not linked_service:
        raise HTTPException(status_code=404, detail="Linked service not found")

    await deprovision_service(db, linked_service, site)
    return {
        "status": "removed",
        "service_type": linked_service.service_type,
        "name": linked_service.name,
    }
