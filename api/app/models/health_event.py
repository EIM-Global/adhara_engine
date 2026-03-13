"""
Health Event model for tracking site health check history.

The health monitor (ARQ cron job) hits each running site's health
endpoint every 30 seconds. Results are logged as HealthEvent records
for audit trail and uptime calculation.

Auto-healing escalation ladder:
  Level 1 (3 consecutive failures):  Restart container
  Level 2 (6 consecutive failures):  Rebuild from last committed SHA
  Level 3 (9 consecutive failures):  Rollback to previous deployment
  Level 4 (12 consecutive failures): Alert owner, mark site "degraded"
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class HealthEvent(Base):
    __tablename__ = "health_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Check result ─────────────────────────────────────────
    check_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    status_code: Mapped[int | None] = mapped_column(
        Integer
    )  # HTTP status or null if timeout/connection error
    response_ms: Mapped[int | None] = mapped_column(Integer)
    healthy: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # ── Action taken ─────────────────────────────────────────
    action_taken: Mapped[str | None] = mapped_column(
        String(32)
    )  # "restart", "rebuild", "rollback", "alert", null if healthy

    # ── Relationships ────────────────────────────────────────
    site = relationship("Site", back_populates="health_events")
