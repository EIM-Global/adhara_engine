import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str | None = Field(None, max_length=255, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    plan: str = "free"
    owner_email: str = Field(..., max_length=255)


class TenantUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    plan: str | None = None
    owner_email: str | None = Field(None, max_length=255)


class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan: str
    owner_email: str
    created_at: datetime

    model_config = {"from_attributes": True}
