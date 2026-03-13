"""
Preview Environment model — ephemeral deployments for pull/merge requests.

A PreviewEnvironment is a temporary site deployment created when a PR is
opened, and automatically cleaned up when the PR is merged or closed.

Lifecycle:
  1. PR opened/updated -> create/update preview environment
  2. PR merged/closed -> destroy preview environment
  3. TTL expiry -> auto-cleanup stale previews
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PreviewEnvironment(Base):
    __tablename__ = "preview_environments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Parent site (the "main" site this PR is against) ──────
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── PR identification ─────────────────────────────────────
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    pr_title: Mapped[str | None] = mapped_column(String(512))
    pr_author: Mapped[str | None] = mapped_column(String(255))
    pr_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    pr_url: Mapped[str | None] = mapped_column(String(1024))
    git_provider: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # "github", "gitlab"

    # ── Build state ───────────────────────────────────────────
    commit_sha: Mapped[str | None] = mapped_column(String(64))
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="SET NULL")
    )

    # ── Deployment state ──────────────────────────────────────
    # pending -> building -> running -> destroyed
    status: Mapped[str] = mapped_column(
        String(32), default="pending", index=True
    )
    container_id: Mapped[str | None] = mapped_column(String(255))
    host_port: Mapped[int | None] = mapped_column(Integer)
    preview_url: Mapped[str | None] = mapped_column(String(1024))
    image_tag: Mapped[str | None] = mapped_column(String(512))

    # ── Lifecycle ─────────────────────────────────────────────
    ttl_hours: Mapped[int] = mapped_column(
        Integer, default=72
    )  # Auto-destroy after N hours
    pr_state: Mapped[str] = mapped_column(
        String(32), default="open"
    )  # "open", "merged", "closed"
    destroy_reason: Mapped[str | None] = mapped_column(
        String(64)
    )  # "pr_merged", "pr_closed", "ttl_expired", "manual"

    # ── Timestamps ────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    destroyed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    # ── Relationships ─────────────────────────────────────────
    site = relationship("Site", backref="preview_environments")
    pipeline_run = relationship("PipelineRun", foreign_keys=[pipeline_run_id])
