"""
Site model — represents a single deployed web application.

A Site belongs to a Workspace (which belongs to a Tenant) and tracks:
  - Source configuration (git repo, Docker image, etc.)
  - Build configuration (Dockerfile path, build args, build driver)
  - Deploy configuration (target, ports, domains)
  - Git-follow settings (auto-deploy on push)
  - Health monitoring state
  - Blue-green deployment state
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # ── Source configuration ─────────────────────────────────
    source_type: Mapped[str] = mapped_column(
        Enum(
            "git_repo",
            "docker_image",
            "docker_registry",
            "upload",
            name="source_type",
        ),
        nullable=False,
    )
    source_url: Mapped[str | None] = mapped_column(String(1024))
    dockerfile_path: Mapped[str | None] = mapped_column(
        String(512), default="Dockerfile"
    )
    build_command: Mapped[str | None] = mapped_column(String(1024))

    # ── Container configuration ──────────────────────────────
    container_port: Mapped[int] = mapped_column(Integer, default=3000)
    host_port: Mapped[int | None] = mapped_column(Integer)

    # ── Deploy target ────────────────────────────────────────
    deploy_target: Mapped[str] = mapped_column(
        Enum(
            "local",
            "cloud_run",
            "aws_ecs",
            "azure_container",
            "kubernetes",
            name="deploy_target",
        ),
        default="local",
    )
    deploy_region: Mapped[str | None] = mapped_column(String(64))

    # ── Domains & routing ────────────────────────────────────
    custom_domains: Mapped[dict | None] = mapped_column(JSONB, default=list)

    # ── Environment variables ────────────────────────────────
    runtime_env: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    build_env: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    # ── Health check ─────────────────────────────────────────
    health_check_path: Mapped[str] = mapped_column(
        String(255), default="/api/health"
    )

    # ── Site status ──────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        Enum(
            "stopped",
            "building",
            "deploying",
            "running",
            "error",
            name="site_status",
        ),
        default="stopped",
    )
    current_deployment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True)
    )

    # ── Git-follow configuration (NEW) ───────────────────────
    git_provider: Mapped[str | None] = mapped_column(
        String(32)
    )  # "github", "gitlab"
    git_provider_url: Mapped[str | None] = mapped_column(
        String(1024)
    )  # "https://gitlab.company.com" for self-hosted
    git_branch: Mapped[str | None] = mapped_column(
        String(255), default="main"
    )  # Branch to watch
    auto_deploy: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # Enable git-follow
    webhook_secret: Mapped[str | None] = mapped_column(
        String(255)
    )  # Per-site webhook secret
    last_deployed_sha: Mapped[str | None] = mapped_column(
        String(64)
    )  # Dedup key

    # ── Git clone credentials (NEW) ──────────────────────────
    git_token_username: Mapped[str | None] = mapped_column(
        String(255)
    )  # Deploy token username
    git_token: Mapped[str | None] = mapped_column(
        String(512)
    )  # Deploy token (should be encrypted at rest)

    # ── Build driver override (NEW) ──────────────────────────
    # null = use global default from platform settings
    build_driver: Mapped[str | None] = mapped_column(
        String(64)
    )  # "local_docker", "local_buildkit", "remote_buildkit", etc.

    # ── Scan configuration (NEW) ─────────────────────────────
    scan_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    scan_fail_on: Mapped[str | None] = mapped_column(
        String(16), default="critical"
    )  # "critical", "high", "medium", "low"

    # ── Health monitoring state (NEW) ────────────────────────
    health_auto_remediate: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )  # Opt-in: auto-restart/rebuild/rollback on health failure
    health_failure_count: Mapped[int] = mapped_column(Integer, default=0)
    health_status: Mapped[str | None] = mapped_column(
        String(16), default="unknown"
    )  # "healthy", "degraded", "down", "unknown"
    last_health_check: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_healthy_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    # ── Blue-green deploy state (NEW) ────────────────────────
    active_container_id: Mapped[str | None] = mapped_column(
        String(255)
    )  # Currently serving traffic
    pending_container_id: Mapped[str | None] = mapped_column(
        String(255)
    )  # Green container during deploy

    # ── Timestamps ───────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Relationships ────────────────────────────────────────
    workspace = relationship("Workspace", back_populates="sites")
    deployments = relationship(
        "Deployment", back_populates="site", cascade="all, delete-orphan"
    )
    pipeline_runs = relationship(
        "PipelineRun", back_populates="site", cascade="all, delete-orphan"
    )
    linked_services = relationship(
        "LinkedService", back_populates="site", cascade="all, delete-orphan"
    )
    health_events = relationship(
        "HealthEvent", back_populates="site", cascade="all, delete-orphan"
    )
    notification_configs = relationship(
        "NotificationConfig", back_populates="site", cascade="all, delete-orphan"
    )
