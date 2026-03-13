"""Local Docker deployment target using Docker SDK for Python."""

import asyncio
import io
import logging
import tarfile
import tempfile
from pathlib import Path
from typing import AsyncIterator

import docker
from docker.errors import ContainerError, ImageNotFound, NotFound

from app.services.deploy_target import DeployConfig, DeployResult, DeployTarget

logger = logging.getLogger(__name__)

NETWORK_NAME = "adhara-engine-net"


def _container_name(config: DeployConfig) -> str:
    """Generate container name: ae-{tenant}-{workspace}-{site}."""
    return f"ae-{config.tenant_slug}-{config.workspace_slug}-{config.site_slug}"


def _build_runtime_env(config: DeployConfig) -> dict:
    """Merge runtime env vars with Adhara Web connection vars."""
    env = dict(config.runtime_env or {})
    return env


def _default_hostname(config: DeployConfig) -> str:
    """Generate default hostname: {site}.{workspace}.{tenant}.localhost."""
    return f"{config.site_slug}.{config.workspace_slug}.{config.tenant_slug}.localhost"


def _traefik_labels(config: DeployConfig) -> dict:
    """Generate Traefik Docker labels for automatic routing."""
    name = _container_name(config)
    hostname = _default_hostname(config)

    # Build Host rule: default hostname + any custom domains
    hosts = [f"Host(`{hostname}`)"]
    for domain in (config.custom_domains or []):
        hosts.append(f"Host(`{domain}`)")
    host_rule = " || ".join(hosts)

    labels = {
        "traefik.enable": "true",
        f"traefik.http.routers.{name}.rule": host_rule,
        f"traefik.http.routers.{name}.entrypoints": "web",
        f"traefik.http.services.{name}.loadbalancer.server.port": str(config.container_port),
    }

    # Add HTTPS router for custom domains (not localhost)
    if config.custom_domains:
        labels[f"traefik.http.routers.{name}-secure.rule"] = host_rule
        labels[f"traefik.http.routers.{name}-secure.entrypoints"] = "websecure"
        labels[f"traefik.http.routers.{name}-secure.tls.certresolver"] = "letsencrypt"

    return labels


class LocalDeployTarget(DeployTarget):
    """Deploys containers on the local Docker daemon."""

    def __init__(self):
        self.client = docker.from_env()

    async def deploy(self, config: DeployConfig) -> DeployResult:
        """Build or pull image, then create and start a container."""
        container_name = _container_name(config)
        build_logs = []

        try:
            # Stop and remove existing container if any
            await self._cleanup_existing(container_name)

            # Get or build the image
            image_tag = await self._resolve_image(config, build_logs)

            # Build runtime env
            env = _build_runtime_env(config)

            # Ensure network exists
            self._ensure_network()

            # Build labels: Adhara metadata + Traefik routing
            labels = {
                "adhara.engine": "true",
                "adhara.site_id": config.site_id,
                "adhara.site_slug": config.site_slug,
                "adhara.tenant_slug": config.tenant_slug,
                "adhara.workspace_slug": config.workspace_slug,
                "adhara.container_port": str(config.container_port),
                "adhara.host_port": str(config.host_port or ""),
            }
            labels.update(_traefik_labels(config))

            # Create and start container
            # Both host port mapping (direct access) and Traefik labels (hostname routing)
            container = self.client.containers.run(
                image=image_tag,
                name=container_name,
                detach=True,
                ports={f"{config.container_port}/tcp": config.host_port},
                environment=env,
                network=NETWORK_NAME,
                labels=labels,
                restart_policy={"Name": "unless-stopped"},
            )

            logger.info(f"Container {container_name} started: {container.short_id}")

            return DeployResult(
                success=True,
                container_id=container.id,
                image_tag=image_tag,
                host_port=config.host_port,
                container_port=config.container_port,
                logs="\n".join(build_logs),
            )

        except Exception as e:
            logger.error(f"Deploy failed for {container_name}: {e}")
            return DeployResult(
                success=False,
                error=str(e),
                logs="\n".join(build_logs),
            )

    async def _resolve_image(self, config: DeployConfig, build_logs: list[str]) -> str:
        """Get the Docker image — build it or pull it depending on source_type."""
        if config.source_type == "git_repo":
            return await self._build_from_git(config, build_logs)
        elif config.source_type == "docker_image":
            # Pre-built image — use as-is
            tag = config.source_url or config.image_tag
            if not tag:
                raise ValueError("No image tag or source_url provided for docker_image source")
            build_logs.append(f"Using pre-built image: {tag}")
            return tag
        elif config.source_type == "docker_registry":
            return await self._pull_from_registry(config, build_logs)
        elif config.source_type == "upload":
            return await self._build_from_upload(config, build_logs)
        else:
            raise ValueError(f"Unknown source_type: {config.source_type}")

    async def _build_from_git(self, config: DeployConfig, build_logs: list[str]) -> str:
        """Clone git repo and build Docker image."""
        tag = f"ae-{config.site_slug}:latest"
        build_logs.append(f"Cloning {config.source_url}...")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Clone repo
            proc = await asyncio.create_subprocess_exec(
                "git", "clone", "--depth=1", config.source_url, tmpdir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(f"Git clone failed: {stderr.decode()}")
            build_logs.append("Clone complete.")

            # Build image
            dockerfile_path = config.dockerfile_path or "Dockerfile"
            build_logs.append(f"Building image {tag} from {dockerfile_path}...")

            buildargs = dict(config.build_env or {})
            image, logs = self.client.images.build(
                path=tmpdir,
                dockerfile=dockerfile_path,
                tag=tag,
                buildargs=buildargs,
                rm=True,
            )
            for chunk in logs:
                if "stream" in chunk:
                    build_logs.append(chunk["stream"].strip())

            build_logs.append(f"Image built: {tag}")
            return tag

    async def _pull_from_registry(self, config: DeployConfig, build_logs: list[str]) -> str:
        """Pull image from a Docker registry."""
        image_ref = config.source_url
        if not image_ref:
            raise ValueError("No source_url provided for docker_registry source")

        build_logs.append(f"Pulling {image_ref}...")
        self.client.images.pull(image_ref)
        build_logs.append(f"Pull complete: {image_ref}")
        return image_ref

    async def _build_from_upload(self, config: DeployConfig, build_logs: list[str]) -> str:
        """Build from uploaded source archive (tarball/zip stored in MinIO)."""
        # The source_url for upload type points to the MinIO path
        # For now, we treat it like a local path or pre-extracted directory
        tag = f"ae-{config.site_slug}:latest"
        build_logs.append(f"Building from uploaded source: {tag}")

        if not config.source_url:
            raise ValueError("No source path provided for upload source")

        buildargs = dict(config.build_env or {})
        image, logs = self.client.images.build(
            path=config.source_url,
            dockerfile=config.dockerfile_path or "Dockerfile",
            tag=tag,
            buildargs=buildargs,
            rm=True,
        )
        for chunk in logs:
            if "stream" in chunk:
                build_logs.append(chunk["stream"].strip())

        build_logs.append(f"Image built: {tag}")
        return tag

    async def _cleanup_existing(self, container_name: str):
        """Stop and remove an existing container with this name."""
        try:
            container = self.client.containers.get(container_name)
            logger.info(f"Stopping existing container {container_name}")
            container.stop(timeout=10)
            container.remove()
        except NotFound:
            pass

    def _ensure_network(self):
        """Ensure the adhara-engine-net network exists."""
        try:
            self.client.networks.get(NETWORK_NAME)
        except NotFound:
            self.client.networks.create(NETWORK_NAME, driver="bridge")

    async def stop(self, container_name: str) -> None:
        try:
            container = self.client.containers.get(container_name)
            container.stop(timeout=10)
            logger.info(f"Container {container_name} stopped")
        except NotFound:
            raise ValueError(f"Container {container_name} not found")

    async def restart(self, container_name: str) -> None:
        try:
            container = self.client.containers.get(container_name)
            container.restart(timeout=10)
            logger.info(f"Container {container_name} restarted")
        except NotFound:
            raise ValueError(f"Container {container_name} not found")

    async def logs(self, container_name: str, follow: bool = False, tail: int = 100) -> AsyncIterator[str]:
        try:
            container = self.client.containers.get(container_name)
            if follow:
                for line in container.logs(stream=True, follow=True, tail=tail):
                    yield line.decode("utf-8", errors="replace").rstrip()
            else:
                output = container.logs(tail=tail).decode("utf-8", errors="replace")
                for line in output.splitlines():
                    yield line
        except NotFound:
            raise ValueError(f"Container {container_name} not found")

    async def status(self, container_name: str) -> dict:
        try:
            container = self.client.containers.get(container_name)
            return {
                "container_id": container.short_id,
                "name": container_name,
                "status": container.status,
                "image": container.image.tags[0] if container.image.tags else "unknown",
                "ports": container.ports,
            }
        except NotFound:
            return {
                "name": container_name,
                "status": "not_found",
            }

    async def set_env(self, container_name: str, env: dict) -> None:
        """Update env vars by recreating the container with new env."""
        try:
            container = self.client.containers.get(container_name)
            # Get current config
            image = container.image
            ports = container.ports
            labels = container.labels
            network = NETWORK_NAME

            # Stop and remove
            container.stop(timeout=10)
            container.remove()

            # Recreate with new env
            self.client.containers.run(
                image=image,
                name=container_name,
                detach=True,
                ports=ports,
                environment=env,
                network=network,
                labels=labels,
                restart_policy={"Name": "unless-stopped"},
            )
            logger.info(f"Container {container_name} recreated with new env vars")
        except NotFound:
            raise ValueError(f"Container {container_name} not found")

    async def remove(self, container_name: str) -> None:
        try:
            container = self.client.containers.get(container_name)
            container.stop(timeout=10)
            container.remove()
        except NotFound:
            pass
