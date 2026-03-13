"""
Pipeline models for the Adhara Engine build pipeline.

PipelineRun represents a single execution of the build pipeline
(clone -> scan -> build -> push -> deploy). Each run contains
ordered PipelineStage records tracking individual stage progress.

A PipelineRun is triggered by:
  - Manual deploy (POST /api/v1/sites/{id}/deploy)
  - Git webhook (GitHub or GitLab push event)
  - Polling (background job detects new commits)
  - Rollback (re-deploy a previous image)

The pipeline creates a Deployment record on successful completion.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
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

    # ── What triggered this pipeline ─────────────────────────
    trigger: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # "manual", "webhook", "polling", "rollback"
    git_provider: Mapped[str | None] = mapped_column(
        String(32)
    )  # "github", "gitlab"
    git_ref: Mapped[str | None] = mapped_column(String(255))  # "refs/heads/main"
    commit_sha: Mapped[str | None] = mapped_column(String(64))
    commit_message: Mapped[str | None] = mapped_column(Text)
    commit_author: Mapped[str | None] = mapped_column(String(255))

    # ── Pipeline state ───────────────────────────────────────
    # pending -> running -> succeeded / failed / cancelled
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)

    # ── Build configuration used ─────────────────────────────
    build_driver: Mapped[str | None] = mapped_column(
        String(64)
    )  # "local_docker", "remote_buildkit", "gcp_cloud_build"

    # ── Result ───────────────────────────────────────────────
    image_ref: Mapped[str | None] = mapped_column(
        String(512)
    )  # registry.example.com/app@sha256:...
    deployment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deployments.id", ondelete="SET NULL")
    )

    # ── Timing ───────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── Who triggered it ─────────────────────────────────────
    triggered_by: Mapped[str | None] = mapped_column(
        String(255)
    )  # user_id or "webhook" or "poller"

    # ── Relationships ────────────────────────────────────────
    stages: Mapped[list["PipelineStage"]] = relationship(
        back_populates="pipeline_run",
        cascade="all, delete-orphan",
        order_by="PipelineStage.order",
    )
    site = relationship("Site", back_populates="pipeline_runs")
    deployment = relationship("Deployment", foreign_keys=[deployment_id])


class PipelineStage(Base):
    __tablename__ = "pipeline_stages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Stage identity ───────────────────────────────────────
    name: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # "clone", "scan", "build", "push", "deploy"
    order: Mapped[int] = mapped_column(Integer, nullable=False)  # 0, 1, 2, 3, 4

    # ── Stage state ──────────────────────────────────────────
    # pending -> running -> passed / failed / skipped
    status: Mapped[str] = mapped_column(String(32), default="pending")

    # ── Timing ───────────────────────────────────────────────
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    # ── Output ───────────────────────────────────────────────
    logs: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)

    # ── Stage-specific data (scan results, image tag, etc.) ──
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, default=dict
    )

    # ── Relationships ────────────────────────────────────────
    pipeline_run: Mapped["PipelineRun"] = relationship(back_populates="stages")
