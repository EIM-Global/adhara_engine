"""
API Token model for scoped service accounts.

Supports CI/CD pipelines, mobile apps, and programmatic access.
Tokens are scoped to specific resources and permissions, and can
be revoked instantly.

Token format: ae_live_<random_32_chars>
  - "ae_" prefix distinguishes from Zitadel JWTs in auth middleware
  - Only the SHA-256 hash is stored; plain token shown once at creation
  - token_prefix stores first 12 chars for identification in lists

Authentication flow:
  1. Request arrives with Authorization: Bearer ae_live_...
  2. Auth middleware detects "ae_" prefix
  3. Hash the token, look up in api_tokens table
  4. Check not revoked, not expired
  5. Use scopes to authorize the request
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class APIToken(Base):
    __tablename__ = "api_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Owner ────────────────────────────────────────────────
    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )  # Zitadel user ID
    name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # "CI Deploy Token", "Mobile App"

    # ── Token (hashed) ───────────────────────────────────────
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )  # SHA-256 hex digest
    token_prefix: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # "ae_live_abc..." for display

    # ── Scope ────────────────────────────────────────────────
    # List of scoped permissions, e.g.:
    # [
    #   {"resource_type": "workspace", "resource_id": "uuid",
    #    "permissions": ["site:deploy", "site:restart"]},
    #   {"resource_type": "site", "resource_id": "uuid",
    #    "permissions": ["site:view", "site:logs"]}
    # ]
    scopes: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # ── Lifecycle ────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
