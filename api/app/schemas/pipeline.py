"""Pydantic schemas for pipeline API responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class PipelineStageResponse(BaseModel):
    """Response for a single pipeline stage."""

    id: uuid.UUID
    name: str  # "clone", "scan", "build", "push", "deploy"
    order: int
    status: str  # "pending", "running", "passed", "failed", "skipped"
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    logs: str | None
    error: str | None

    model_config = {"from_attributes": True}


class PipelineRunResponse(BaseModel):
    """Response for a pipeline run."""

    id: uuid.UUID
    site_id: uuid.UUID
    tenant_id: uuid.UUID
    trigger: str  # "manual", "webhook", "polling", "rollback"
    git_provider: str | None
    git_ref: str | None
    commit_sha: str | None
    commit_message: str | None
    commit_author: str | None
    status: str  # "pending", "running", "succeeded", "failed", "cancelled"
    build_driver: str | None
    image_ref: str | None
    deployment_id: uuid.UUID | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    triggered_by: str | None
    stages: list[PipelineStageResponse] = []

    model_config = {"from_attributes": True}


class PipelineRunSummary(BaseModel):
    """Lightweight summary for pipeline list views."""

    id: uuid.UUID
    trigger: str
    status: str
    commit_sha: str | None
    build_driver: str | None
    created_at: datetime
    finished_at: datetime | None
    triggered_by: str | None

    model_config = {"from_attributes": True}


class DeployRequest(BaseModel):
    """Request body for triggering a deploy."""

    git_ref: str | None = None  # Override branch to build
    commit_sha: str | None = None  # Specific commit
    build_driver: str | None = None  # Override build driver

    # When True, run synchronously (legacy behavior)
    synchronous: bool = False
