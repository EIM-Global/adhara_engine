"""
API Token CRUD endpoints.

Tokens provide programmatic access for CI/CD, mobile apps, and service accounts.
Each token is scoped to specific resources and permissions.

Token format: ae_live_<32 random chars>
  - Only the SHA-256 hash is stored in the database
  - The plain token is returned ONCE on creation
  - Token prefix (first 12 chars) is stored for display in lists

Endpoints:
  GET    /api/v1/tokens          — list user's tokens
  POST   /api/v1/tokens          — create new token (returns plain token)
  DELETE /api/v1/tokens/{id}     — revoke a token
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import require_auth
from app.core.database import get_db
from app.models.api_token import APIToken
from app.schemas.api_token import (
    APITokenCreate,
    APITokenCreateResponse,
    APITokenResponse,
)

router = APIRouter(tags=["tokens"])


@router.get("/api/v1/tokens", response_model=list[APITokenResponse])
async def list_tokens(
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """List all API tokens for the current user."""
    user_id = user["sub"]
    return (
        db.query(APIToken)
        .filter(APIToken.user_id == user_id)
        .order_by(APIToken.created_at.desc())
        .all()
    )


@router.post(
    "/api/v1/tokens",
    response_model=APITokenCreateResponse,
    status_code=201,
)
async def create_token(
    data: APITokenCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Create a new API token.

    The plain token is returned ONCE in the response. Store it securely —
    it cannot be retrieved again.
    """
    user_id = user["sub"]

    # Generate the token
    raw_token = f"ae_live_{secrets.token_urlsafe(32)}"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    token_prefix = raw_token[:16]

    # Convert scopes to serializable format
    scopes = [scope.model_dump() for scope in data.scopes]

    api_token = APIToken(
        user_id=user_id,
        name=data.name,
        token_hash=token_hash,
        token_prefix=token_prefix,
        scopes=scopes,
        expires_at=data.expires_at,
    )
    db.add(api_token)
    db.commit()
    db.refresh(api_token)

    return APITokenCreateResponse(
        id=api_token.id,
        name=api_token.name,
        token=raw_token,
        token_prefix=token_prefix,
        scopes=api_token.scopes,
        created_at=api_token.created_at,
        expires_at=api_token.expires_at,
    )


@router.delete("/api/v1/tokens/{token_id}", status_code=200)
async def revoke_token(
    token_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Revoke an API token. Takes effect immediately."""
    user_id = user["sub"]

    api_token = (
        db.query(APIToken)
        .filter(APIToken.id == token_id, APIToken.user_id == user_id)
        .first()
    )
    if not api_token:
        raise HTTPException(status_code=404, detail="Token not found")

    if api_token.revoked:
        raise HTTPException(status_code=409, detail="Token already revoked")

    api_token.revoked = True
    api_token.revoked_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "status": "revoked",
        "token_id": str(token_id),
        "token_name": api_token.name,
    }
