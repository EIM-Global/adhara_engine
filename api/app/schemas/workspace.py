import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str | None = Field(None, max_length=255, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    adhara_api_url: str | None = None
    adhara_api_key: str | None = None


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    adhara_api_url: str | None = None
    adhara_api_key: str | None = None


class WorkspaceResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    slug: str
    adhara_api_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
