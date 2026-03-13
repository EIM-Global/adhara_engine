"""
Build drivers for Adhara Engine.

A build driver handles the BUILD phase of the pipeline — taking source code
and producing a Docker image. The DEPLOY phase is handled separately by
DeployTarget implementations.

Available drivers:
  - local_docker: Builds using the local Docker daemon (docker build)
  - local_buildkit: BuildKit with advanced caching (docker buildx build)
  - gcp_cloud_build: Google Cloud Build (requires google-cloud-build SDK)
  - aws_codebuild: AWS CodeBuild (requires boto3 SDK)
"""

from app.services.build_drivers.base import BuildDriver, BuildRequest, BuildResult
from app.services.build_drivers.local_docker import LocalDockerBuilder
from app.services.build_drivers.local_buildkit import LocalBuildKitBuilder
from app.services.build_drivers.gcp_cloud_build import GCPCloudBuildDriver
from app.services.build_drivers.aws_codebuild import AWSCodeBuildDriver

# Registry of available build drivers
DRIVERS: dict[str, type[BuildDriver]] = {
    "local_docker": LocalDockerBuilder,
    "local_buildkit": LocalBuildKitBuilder,
    "gcp_cloud_build": GCPCloudBuildDriver,
    "aws_codebuild": AWSCodeBuildDriver,
}

# Default when site.build_driver is None
DEFAULT_DRIVER = "local_docker"


def get_build_driver(driver_name: str | None = None) -> BuildDriver:
    """Get a build driver instance by name. Falls back to DEFAULT_DRIVER."""
    name = driver_name or DEFAULT_DRIVER
    cls = DRIVERS.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown build driver: {name}. Available: {list(DRIVERS.keys())}"
        )
    return cls()


__all__ = [
    "BuildDriver",
    "BuildRequest",
    "BuildResult",
    "LocalDockerBuilder",
    "LocalBuildKitBuilder",
    "GCPCloudBuildDriver",
    "AWSCodeBuildDriver",
    "get_build_driver",
    "DRIVERS",
    "DEFAULT_DRIVER",
]
