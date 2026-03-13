import uuid
from datetime import datetime

from pydantic import BaseModel


class DeploymentResponse(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    version: int
    source_ref: str | None
    image_tag: str | None
    container_port: int | None
    host_port: int | None
    status: str
    build_logs: str | None
    deploy_logs: str | None
    created_at: datetime
    deployed_at: datetime | None
    deployed_by: str | None

    model_config = {"from_attributes": True}
