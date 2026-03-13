"""
Abstract base class for build drivers.

Build drivers are responsible for taking source code and producing a
Docker image. They are decoupled from deployment — a build driver doesn't
know where the image will be deployed.

The pipeline orchestrator calls:
  1. driver.clone(request)   — get source code
  2. driver.scan(request)    — static analysis (optional)
  3. driver.build(request)   — produce Docker image
  4. driver.push(request)    — push to registry (optional)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class BuildRequest:
    """Input to a build driver."""

    site_id: str
    site_slug: str
    tenant_slug: str
    workspace_slug: str

    # Source
    source_type: str  # "git_repo", "docker_image", "docker_registry", "upload"
    source_url: str | None = None
    git_ref: str | None = None  # "refs/heads/main"
    commit_sha: str | None = None

    # Git credentials (for private repos)
    git_token_username: str | None = None
    git_token: str | None = None

    # Build config
    dockerfile_path: str = "Dockerfile"
    build_command: str | None = None
    build_env: dict[str, str] = field(default_factory=dict)

    # Scan config
    scan_enabled: bool = False
    scan_fail_on: str = "critical"  # "critical", "high", "medium", "low"

    # Registry (for push stage)
    registry_url: str | None = None  # e.g., "localhost:5000"

    # Logging callback — called with (stage_name, log_line) for real-time logs
    log_callback: Callable[[str, str], None] | None = None


@dataclass
class BuildResult:
    """Output from a build driver."""

    success: bool
    image_tag: str | None = None  # "ae-mysite:latest" or "registry/ae-mysite:sha-abc123"
    image_digest: str | None = None  # "sha256:..."
    error: str | None = None

    # Per-stage logs
    clone_logs: str = ""
    scan_logs: str = ""
    build_logs: str = ""
    push_logs: str = ""

    # Scan results
    scan_passed: bool | None = None  # None = not scanned
    scan_findings: dict | None = None  # structured scan output

    # Timing
    clone_duration_ms: int | None = None
    scan_duration_ms: int | None = None
    build_duration_ms: int | None = None
    push_duration_ms: int | None = None


class BuildDriver(ABC):
    """Abstract interface for build drivers.

    Each driver implements the four build stages. The pipeline orchestrator
    calls them in sequence: clone -> scan -> build -> push.

    Drivers that don't support a stage (e.g., scan) should return a
    successful result with the stage skipped.
    """

    @abstractmethod
    async def clone(self, request: BuildRequest) -> BuildResult:
        """Clone or fetch source code. Returns result with clone_logs populated.

        For git_repo: clone the repository to a temp directory.
        For docker_image: no-op (image already exists).
        For docker_registry: no-op (will pull in build stage).
        For upload: download from MinIO.
        """
        ...

    @abstractmethod
    async def scan(self, request: BuildRequest, clone_dir: str | None) -> BuildResult:
        """Run static analysis on source code.

        Returns result with scan_logs and scan_findings populated.
        If scan_enabled is False, returns success with scan_passed=None.
        """
        ...

    @abstractmethod
    async def build(self, request: BuildRequest, clone_dir: str | None) -> BuildResult:
        """Build a Docker image from source.

        Returns result with image_tag and build_logs populated.
        """
        ...

    @abstractmethod
    async def push(self, request: BuildRequest, image_tag: str) -> BuildResult:
        """Push built image to a registry.

        Returns result with image_tag (registry-qualified) populated.
        If no registry is configured, returns the local image tag.
        """
        ...
