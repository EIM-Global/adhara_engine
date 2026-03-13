"""Pydantic schemas for API token operations."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TokenScope(BaseModel):
    """A single scope entry for an API token."""

    resource_type: str  # "tenant", "workspace", "site"
    resource_id: str  # UUID as string
    permissions: list[str]  # ["site:deploy", "site:restart"]


class APITokenCreate(BaseModel):
    """Create an API token."""

    name: str = Field(..., min_length=1, max_length=255)
    scopes: list[TokenScope]
    expires_at: datetime | None = None


class APITokenResponse(BaseModel):
    """Response for an API token (without the actual token value)."""

    id: uuid.UUID
    name: str
    token_prefix: str
    scopes: list | dict
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked: bool

    model_config = {"from_attributes": True}


class APITokenCreateResponse(BaseModel):
    """Response when creating a new token — includes the plain token (shown once)."""

    id: uuid.UUID
    name: str
    token: str  # The actual token — only returned on create
    token_prefix: str
    scopes: list | dict
    created_at: datetime
    expires_at: datetime | None

    model_config = {"from_attributes": True}
