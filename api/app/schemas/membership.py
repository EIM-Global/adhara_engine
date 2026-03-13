"""Pydantic schemas for membership (RBAC) operations."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class MembershipCreate(BaseModel):
    """Add a member to a resource."""

    user_id: str = Field(..., min_length=1, max_length=255)
    user_email: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., min_length=1, max_length=64)
    expires_at: datetime | None = None


class MembershipUpdate(BaseModel):
    """Update a member's role or expiry."""

    role: str | None = Field(None, max_length=64)
    expires_at: datetime | None = None


class MembershipResponse(BaseModel):
    """Response for a membership record."""

    id: uuid.UUID
    user_id: str
    user_email: str
    resource_type: str
    resource_id: uuid.UUID | None
    role: str
    granted_by: str | None
    granted_at: datetime
    expires_at: datetime | None

    model_config = {"from_attributes": True}
