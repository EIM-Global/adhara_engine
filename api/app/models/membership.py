"""
Membership model for hierarchical RBAC.

Links a Zitadel user to a resource (platform, tenant, workspace, or site)
with a specific role. Authorization checks walk UP the hierarchy:
site -> workspace -> tenant -> platform, and the first matching membership
grants permissions.

Roles:
  Platform level: platform_admin, platform_viewer
  Tenant level:   tenant_owner, tenant_admin, tenant_member
  Workspace level: workspace_admin, workspace_deployer, workspace_viewer
  Site level:     site_admin, site_deployer, site_viewer

Revocation is instant because permissions are checked against this table
on every request (not cached in JWT claims).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Who ──────────────────────────────────────────────────
    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # Zitadel user ID (JWT "sub" claim)
    user_email: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # Denormalized for display/search

    # ── What resource ────────────────────────────────────────
    # resource_type: "platform", "tenant", "workspace", "site"
    # resource_id:   UUID of the resource, NULL for platform-level
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # ── What role ────────────────────────────────────────────
    role: Mapped[str] = mapped_column(String(64), nullable=False)

    # ── Metadata ─────────────────────────────────────────────
    granted_by: Mapped[str | None] = mapped_column(
        String(255)
    )  # user_id of granter
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )  # Optional expiry for temp access

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "resource_type",
            "resource_id",
            name="uq_membership_user_resource",
        ),
        Index("ix_membership_user_id", "user_id"),
        Index("ix_membership_resource", "resource_type", "resource_id"),
    )
