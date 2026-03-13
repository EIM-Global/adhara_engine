"""
Notification configuration CRUD endpoints.

Endpoints:
  GET    /api/v1/sites/{id}/notifications       — list notification configs
  POST   /api/v1/sites/{id}/notifications       — create notification config
  PATCH  /api/v1/notifications/{id}             — update notification config
  DELETE /api/v1/notifications/{id}             — delete notification config
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
from app.models.notification_config import NotificationConfig
from app.models.site import Site

router = APIRouter(tags=["notifications"])


class NotificationCreate(BaseModel):
    type: str = Field(..., pattern=r"^(webhook|email|slack)$")
    target: str = Field(..., min_length=1, max_length=1024)
    name: str | None = Field(None, max_length=255)
    events: list[str] = Field(
        default=["deploy_succeeded", "deploy_failed", "health_alert"]
    )
    enabled: bool = True


class NotificationUpdate(BaseModel):
    name: str | None = None
    target: str | None = None
    events: list[str] | None = None
    enabled: bool | None = None


class NotificationResponse(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    type: str
    target: str
    name: str | None
    events: list | dict
    enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get(
    "/api/v1/sites/{site_id}/notifications",
    response_model=list[NotificationResponse],
)
async def list_notifications(
    site_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """List notification configs for a site."""
    await authorize(user, Permission.SITE_NOTIFICATIONS, "site", site_id, db)
    return (
        db.query(NotificationConfig)
        .filter(NotificationConfig.site_id == site_id)
        .order_by(NotificationConfig.created_at.desc())
        .all()
    )


@router.post(
    "/api/v1/sites/{site_id}/notifications",
    response_model=NotificationResponse,
    status_code=201,
)
async def create_notification(
    site_id: uuid.UUID,
    data: NotificationCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Add a notification channel to a site."""
    await authorize(user, Permission.SITE_NOTIFICATIONS, "site", site_id, db)

    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    # Validate webhook URL if type is webhook or slack
    if data.type in ("webhook", "slack"):
        from app.services.notifications import validate_webhook_url
        try:
            validate_webhook_url(data.target)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    config = NotificationConfig(
        site_id=site.id,
        type=data.type,
        target=data.target,
        name=data.name,
        events=data.events,
        enabled=data.enabled,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@router.patch(
    "/api/v1/notifications/{notification_id}",
    response_model=NotificationResponse,
)
async def update_notification(
    notification_id: uuid.UUID,
    data: NotificationUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Update a notification config."""
    config = (
        db.query(NotificationConfig)
        .filter(NotificationConfig.id == notification_id)
        .first()
    )
    if not config:
        raise HTTPException(status_code=404, detail="Notification config not found")

    await authorize(user, Permission.SITE_NOTIFICATIONS, "site", config.site_id, db)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(config, field, value)

    db.commit()
    db.refresh(config)
    return config


@router.delete("/api/v1/notifications/{notification_id}", status_code=204)
async def delete_notification(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Remove a notification config."""
    config = (
        db.query(NotificationConfig)
        .filter(NotificationConfig.id == notification_id)
        .first()
    )
    if not config:
        raise HTTPException(status_code=404, detail="Notification config not found")

    await authorize(user, Permission.SITE_NOTIFICATIONS, "site", config.site_id, db)

    db.delete(config)
    db.commit()
