import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SiteCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str | None = Field(None, max_length=255, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    source_type: Literal["git_repo", "docker_image", "docker_registry", "upload"]
    source_url: str | None = None
    dockerfile_path: str | None = "Dockerfile"
    build_command: str | None = None
    container_port: int = 3000
    deploy_target: Literal["local", "cloud_run", "aws_ecs", "azure_container", "kubernetes"] = "local"
    deploy_region: str | None = None
    health_check_path: str = "/api/health"
    # Git config (for git_repo source type)
    git_provider: str | None = None
    git_branch: str | None = None
    auto_deploy: bool = False


class SiteUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    slug: str | None = Field(None, max_length=255, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    source_type: Literal["git_repo", "docker_image", "docker_registry", "upload"] | None = None
    source_url: str | None = None
    dockerfile_path: str | None = None
    build_command: str | None = None
    container_port: int | None = None
    host_port: int | None = None
    deploy_target: str | None = None
    deploy_region: str | None = None
    health_check_path: str | None = None
    # Pipeline config
    build_driver: str | None = None
    scan_enabled: bool | None = None
    scan_fail_on: Literal["critical", "high", "medium", "low"] | None = None
    # Git config
    git_provider: str | None = None
    git_branch: str | None = None
    auto_deploy: bool | None = None
    # Health
    health_auto_remediate: bool | None = None


class SiteResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    slug: str
    source_type: str
    source_url: str | None
    dockerfile_path: str | None
    build_command: str | None
    container_port: int
    host_port: int | None
    deploy_target: str
    deploy_region: str | None
    custom_domains: list | None
    health_check_path: str
    status: str
    current_deployment_id: uuid.UUID | None
    created_at: datetime
    # Pipeline config
    build_driver: str | None = None
    scan_enabled: bool = False
    scan_fail_on: str | None = None
    # Git config
    git_provider: str | None = None
    git_branch: str | None = None
    auto_deploy: bool = False
    # Health
    health_auto_remediate: bool = False
    health_status: str | None = None
    health_failure_count: int = 0
    last_health_check: datetime | None = None

    model_config = {"from_attributes": True}


class SiteDetailResponse(SiteResponse):
    runtime_env: dict | None
    build_env: dict | None


class EnvVarSet(BaseModel):
    key: str = Field(..., min_length=1, max_length=255)
    value: str
    scope: Literal["runtime", "build"] = "runtime"


class EnvVarBulkSet(BaseModel):
    vars: list[EnvVarSet]


class EnvVarResponse(BaseModel):
    runtime_env: dict
    build_env: dict
    warning: str | None = None


class PortUpdate(BaseModel):
    container_port: int | None = None
    host_port: int | None = None
