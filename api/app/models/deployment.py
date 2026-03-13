import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Deployment(Base):
    __tablename__ = "deployments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(255))
    image_tag: Mapped[str | None] = mapped_column(String(512))
    container_port: Mapped[int | None] = mapped_column(Integer)
    host_port: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        Enum(
            "queued", "building", "pushing", "deploying", "live",
            "failed", "rolled_back",
            name="deployment_status",
        ),
        default="queued",
    )
    build_logs: Mapped[str | None] = mapped_column(Text)
    deploy_logs: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deployed_by: Mapped[str | None] = mapped_column(String(255))

    site = relationship("Site", back_populates="deployments")
