"""
Platform admin endpoints.

Endpoints:
  GET  /api/v1/platform/build-drivers   — list available build drivers
  GET  /api/v1/platform/scan-drivers    — list available scan drivers
  GET  /api/v1/platform/config          — get platform configuration
  PATCH /api/v1/platform/config         — update platform configuration
"""

import asyncio
import os

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import require_auth
from app.core.authorize import authorize
from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import Permission
from app.services.build_drivers import DRIVERS as BUILD_DRIVERS, DEFAULT_DRIVER
from app.services.scan_drivers import SCANNERS, DEFAULT_SCANNER

router = APIRouter(tags=["platform"])


# ── Driver metadata ─────────────────────────────────────────────

DRIVER_META: dict[str, dict] = {
    "local_docker": {
        "description": "Builds images using the local Docker daemon (docker build). Default driver — works out of the box.",
        "required_env": [],
        "setup_hint": "Requires Docker to be running on the host.",
    },
    "local_buildkit": {
        "description": "Uses Docker BuildKit for advanced layer caching and multi-stage builds (docker buildx build).",
        "required_env": [],
        "setup_hint": "Requires Docker 18.09+ with buildx plugin. Run: docker buildx create --use",
    },
    "gcp_cloud_build": {
        "description": "Offloads builds to Google Cloud Build. Source is uploaded to GCS, built remotely, and pushed to Artifact Registry.",
        "required_env": ["GCP_PROJECT_ID", "GCP_REGION", "GCP_BUILD_STAGING_BUCKET", "GOOGLE_APPLICATION_CREDENTIALS"],
        "setup_hint": "Set env vars and mount a GCP service account JSON. Requires google-cloud-build and google-cloud-storage packages.",
    },
    "aws_codebuild": {
        "description": "Offloads builds to AWS CodeBuild. Source is uploaded to S3, built remotely, and pushed to ECR.",
        "required_env": ["AWS_REGION", "AWS_CODEBUILD_PROJECT", "AWS_ECR_REGISTRY", "AWS_BUILD_BUCKET"],
        "setup_hint": "Set env vars and configure AWS credentials (IAM role or access keys). Requires boto3 package.",
    },
}

SCAN_DRIVER_META: dict[str, dict] = {
    "semgrep": {
        "description": "Static analysis using Semgrep. Scans source code for security issues, bugs, and anti-patterns.",
        "required_env": [],
        "setup_hint": "Requires semgrep CLI to be installed. Run: pip install semgrep",
    },
}


async def _check_docker() -> bool:
    """Check if Docker daemon is accessible via the Docker SDK (socket)."""
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


async def _check_buildx() -> bool:
    """Check if Docker buildx is available via the Docker SDK.

    BuildKit is available if Docker API >= 1.39 and the server supports it.
    Since we can't easily check the buildx plugin from inside a container,
    we check that Docker is reachable and has a recent enough API version.
    """
    try:
        import docker
        client = docker.from_env()
        version = client.version()
        api_version = version.get("ApiVersion", "0.0")
        major, minor = api_version.split(".")[:2]
        # BuildKit requires API 1.39+
        return int(major) >= 1 and int(minor) >= 39
    except Exception:
        return False


async def _check_semgrep() -> bool:
    """Check if semgrep is available."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "semgrep", "--version",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.communicate()
        return proc.returncode == 0
    except FileNotFoundError:
        return False


async def _get_driver_status(name: str) -> str:
    """Return 'ready', 'not_configured', or 'unavailable' for a build driver."""
    meta = DRIVER_META.get(name, {})
    required = meta.get("required_env", [])

    # Check required env vars first
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        return "not_configured"

    # Check runtime availability
    if name == "local_docker":
        return "ready" if await _check_docker() else "unavailable"
    if name == "local_buildkit":
        if not await _check_docker():
            return "unavailable"
        return "ready" if await _check_buildx() else "unavailable"
    if name in ("gcp_cloud_build", "aws_codebuild"):
        # If env vars are set, assume configured (can't cheaply check cloud auth)
        return "ready"

    return "not_configured"


async def _get_scan_driver_status(name: str) -> str:
    """Return status for a scan driver."""
    if name == "semgrep":
        return "ready" if await _check_semgrep() else "unavailable"
    return "not_configured"


# ── Models ──────────────────────────────────────────────────────

class EnvVarStatus(BaseModel):
    name: str
    is_set: bool


class DriverInfo(BaseModel):
    name: str
    is_default: bool
    description: str
    status: str  # ready | not_configured | unavailable
    required_env: list[EnvVarStatus]
    setup_hint: str


@router.get(
    "/api/v1/platform/build-drivers",
    response_model=list[DriverInfo],
)
async def list_build_drivers(user: dict = Depends(require_auth)):
    """List available build drivers with status and configuration info."""
    statuses = await asyncio.gather(
        *[_get_driver_status(name) for name in BUILD_DRIVERS]
    )

    results = []
    for (name, _cls), status in zip(BUILD_DRIVERS.items(), statuses):
        meta = DRIVER_META.get(name, {})
        results.append(DriverInfo(
            name=name,
            is_default=(name == DEFAULT_DRIVER),
            description=meta.get("description", ""),
            status=status,
            required_env=[
                EnvVarStatus(name=v, is_set=bool(os.environ.get(v)))
                for v in meta.get("required_env", [])
            ],
            setup_hint=meta.get("setup_hint", ""),
        ))
    return results


@router.get(
    "/api/v1/platform/scan-drivers",
    response_model=list[DriverInfo],
)
async def list_scan_drivers(user: dict = Depends(require_auth)):
    """List available scan drivers with status."""
    statuses = await asyncio.gather(
        *[_get_scan_driver_status(name) for name in SCANNERS]
    )

    results = []
    for (name, _cls), status in zip(SCANNERS.items(), statuses):
        meta = SCAN_DRIVER_META.get(name, {})
        results.append(DriverInfo(
            name=name,
            is_default=(name == DEFAULT_SCANNER),
            description=meta.get("description", ""),
            status=status,
            required_env=[
                EnvVarStatus(name=v, is_set=bool(os.environ.get(v)))
                for v in meta.get("required_env", [])
            ],
            setup_hint=meta.get("setup_hint", ""),
        ))
    return results


# ── Platform Config ──────────────────────────────────────────────────


class PlatformConfig(BaseModel):
    platform_domain: str
    engine_public_ip: str
    registry_host: str


class PlatformConfigUpdate(BaseModel):
    platform_domain: str | None = None
    engine_public_ip: str | None = None
    registry_host: str | None = None


def _resolve_registry_host() -> str:
    """Return the registry host for push/pull commands.

    If explicitly configured, use that. Otherwise derive from ADHARA_DOMAIN
    (HTTPS mode) or fall back to IP:5000 (HTTP mode).
    """
    if settings.registry_host:
        return settings.registry_host
    adhara_domain = os.environ.get("ADHARA_DOMAIN", "")
    if adhara_domain:
        return f"registry.{adhara_domain}"
    return f"{settings.engine_public_ip}:5000"


@router.get("/api/v1/platform/config", response_model=PlatformConfig)
async def get_platform_config(user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    """Get current platform configuration."""
    await authorize(user, Permission.PLATFORM_DASHBOARD, "platform", None, db)
    return PlatformConfig(
        platform_domain=settings.platform_domain,
        engine_public_ip=settings.engine_public_ip,
        registry_host=_resolve_registry_host(),
    )


@router.patch("/api/v1/platform/config", response_model=PlatformConfig)
async def update_platform_config(
    data: PlatformConfigUpdate,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Update platform configuration.

    Changes take effect immediately for new domain operations.
    Note: these are in-memory changes. To persist across restarts,
    update the .env file or environment variables.
    """
    await authorize(user, Permission.PLATFORM_SETTINGS, "platform", None, db)
    if data.platform_domain is not None:
        settings.platform_domain = data.platform_domain
    if data.engine_public_ip is not None:
        settings.engine_public_ip = data.engine_public_ip
    if data.registry_host is not None:
        settings.registry_host = data.registry_host

    return PlatformConfig(
        platform_domain=settings.platform_domain,
        engine_public_ip=settings.engine_public_ip,
        registry_host=_resolve_registry_host(),
    )
