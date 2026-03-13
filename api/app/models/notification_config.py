"""
Notification Config model for deploy and health event alerts.

Each site can have multiple notification channels configured.
Notifications fire on configurable events.

Supported types:
  - webhook:  POST to a URL with event JSON payload
  - email:    Send email to an address
  - slack:    Post to a Slack incoming webhook URL

Supported events:
  - deploy_started, deploy_succeeded, deploy_failed
  - health_degraded, health_recovered
  - rollback_triggered
  - scan_failed
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class NotificationConfig(Base):
    __tablename__ = "notification_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Channel ──────────────────────────────────────────────
    type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # "webhook", "email", "slack"
    target: Mapped[str] = mapped_column(
        String(1024), nullable=False
    )  # URL, email address, or Slack webhook URL
    name: Mapped[str | None] = mapped_column(
        String(255)
    )  # Human-readable label, e.g., "Ops Slack Channel"

    # ── Events to fire on ────────────────────────────────────
    # ["deploy_succeeded", "deploy_failed", "health_degraded"]
    events: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # ── Lifecycle ────────────────────────────────────────────
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Relationships ────────────────────────────────────────
    site = relationship("Site", back_populates="notification_configs")
