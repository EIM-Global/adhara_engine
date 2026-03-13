"""Abstract base class for deployment targets."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class DeployConfig:
    """Configuration passed to a deploy target."""
    site_id: str
    site_slug: str
    tenant_slug: str
    workspace_slug: str
    image_tag: str | None = None
    source_type: str = "docker_image"
    source_url: str | None = None
    dockerfile_path: str = "Dockerfile"
    build_command: str | None = None
    container_port: int = 3000
    host_port: int | None = None
    runtime_env: dict | None = None
    build_env: dict | None = None
    health_check_path: str = "/api/health"
    custom_domains: list[str] | None = None


@dataclass
class DeployResult:
    """Result returned after a deployment."""
    success: bool
    container_id: str | None = None
    image_tag: str | None = None
    host_port: int | None = None
    container_port: int | None = None
    error: str | None = None
    logs: str | None = None


class DeployTarget(ABC):
    """Abstract interface for deployment targets.

    Implementations: LocalDeployTarget (Docker), future CloudRunDeployTarget,
    KubernetesDeployTarget, etc.
    """

    @abstractmethod
    async def deploy(self, config: DeployConfig) -> DeployResult:
        """Build/pull image and start container."""
        ...

    @abstractmethod
    async def stop(self, container_name: str) -> None:
        """Stop a running container gracefully."""
        ...

    @abstractmethod
    async def restart(self, container_name: str) -> None:
        """Restart a container."""
        ...

    @abstractmethod
    async def logs(self, container_name: str, follow: bool = False, tail: int = 100) -> AsyncIterator[str]:
        """Stream container logs."""
        ...

    @abstractmethod
    async def status(self, container_name: str) -> dict:
        """Get container status."""
        ...

    @abstractmethod
    async def set_env(self, container_name: str, env: dict) -> None:
        """Update runtime env vars and restart."""
        ...

    @abstractmethod
    async def remove(self, container_name: str) -> None:
        """Remove a stopped container."""
        ...
