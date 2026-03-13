"""
Linked Service model for provisioning dependent infrastructure.

When a site needs a database, cache, or object storage, a LinkedService
record is created. The pipeline provisioning stage checks for required
services and creates Docker containers for any that don't exist.

Supported service types:
  - postgres:     PostgreSQL database container
  - redis:        Redis cache/queue container
  - minio_bucket: MinIO bucket (uses the shared MinIO instance)

Connection details are automatically injected into the site's
runtime environment variables (e.g., DATABASE_URL, REDIS_URL).

Lifecycle:
  - On site delete with delete_on_site_removal=True: remove container + volume
  - On site delete with delete_on_site_removal=False: warn about orphaned services
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class LinkedService(Base):
    __tablename__ = "linked_services"

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

    # ── Service identity ─────────────────────────────────────
    service_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # "postgres", "redis", "minio_bucket"
    name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # "my-app-db"

    # ── Container state ──────────────────────────────────────
    container_id: Mapped[str | None] = mapped_column(String(255))
    container_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(32), default="pending"
    )  # "pending", "provisioning", "running", "stopped", "error"

    # ── Connection details (injected as env vars) ────────────
    # e.g., {"DATABASE_URL": "postgresql://...", "PGHOST": "...", "PGPORT": "5432"}
    connection_env: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    # ── Service-specific configuration ───────────────────────
    # Postgres: {"version": "16", "storage_size": "1Gi"}
    # Redis:    {"maxmemory": "256mb"}
    # MinIO:    {"bucket_name": "my-app-assets"}
    config: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    # ── Lifecycle ────────────────────────────────────────────
    delete_on_site_removal: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # Safety default: keep data
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Relationships ────────────────────────────────────────
    site = relationship("Site", back_populates="linked_services")
