"""
Local BuildKit build driver — builds images using `docker buildx build`.

Advantages over basic `docker build`:
  - Better layer caching (cache mounts, inline cache)
  - Concurrent multi-stage builds
  - Build secrets support (--secret)
  - Output to OCI tarballs or direct registry push
  - BuildKit-specific Dockerfile features (heredocs, etc.)

Requires Docker with BuildKit support (Docker 18.09+ or buildx plugin).
"""

import asyncio
import logging
import tempfile
import time

from app.services.build_drivers.base import BuildDriver, BuildRequest, BuildResult

logger = logging.getLogger(__name__)


class LocalBuildKitBuilder(BuildDriver):
    """Builds Docker images using `docker buildx build` with BuildKit."""

    def _log(self, request: BuildRequest, stage: str, line: str):
        if request.log_callback:
            request.log_callback(stage, line)

    async def clone(self, request: BuildRequest) -> BuildResult:
        """Clone git repo (identical to LocalDockerBuilder)."""
        start = time.monotonic()
        logs = []

        try:
            if request.source_type == "git_repo":
                clone_dir = tempfile.mkdtemp(prefix="ae-clone-")

                clone_url = request.source_url
                if request.git_token and clone_url and clone_url.startswith("https://"):
                    username = request.git_token_username or "oauth2"
                    clone_url = clone_url.replace(
                        "https://",
                        f"https://{username}:{request.git_token}@",
                    )

                msg = f"Cloning {request.source_url}..."
                logs.append(msg)
                self._log(request, "clone", msg)

                clone_args = ["git", "clone", "--depth=1"]
                if request.git_ref:
                    branch = request.git_ref
                    if branch.startswith("refs/heads/"):
                        branch = branch[len("refs/heads/"):]
                    clone_args.extend(["--branch", branch])
                clone_args.extend([clone_url, clone_dir])

                proc = await asyncio.create_subprocess_exec(
                    *clone_args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()

                if proc.returncode != 0:
                    error = stderr.decode().strip()
                    if request.git_token:
                        error = error.replace(request.git_token, "***")
                    return BuildResult(
                        success=False,
                        error=f"Git clone failed: {error}",
                        clone_logs="\n".join(logs),
                        clone_duration_ms=int((time.monotonic() - start) * 1000),
                    )

                if not request.commit_sha:
                    sha_proc = await asyncio.create_subprocess_exec(
                        "git", "-C", clone_dir, "rev-parse", "HEAD",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    sha_out, _ = await sha_proc.communicate()
                    if sha_proc.returncode == 0:
                        request.commit_sha = sha_out.decode().strip()

                msg = f"Clone complete. SHA: {request.commit_sha or 'unknown'}"
                logs.append(msg)
                self._log(request, "clone", msg)

                return BuildResult(
                    success=True,
                    clone_logs="\n".join(logs),
                    clone_duration_ms=int((time.monotonic() - start) * 1000),
                )

            elif request.source_type in ("docker_image", "docker_registry"):
                msg = f"Using pre-built image: {request.source_url}"
                logs.append(msg)
                self._log(request, "clone", msg)
                return BuildResult(
                    success=True,
                    image_tag=request.source_url,
                    clone_logs="\n".join(logs),
                    clone_duration_ms=int((time.monotonic() - start) * 1000),
                )

            else:
                return BuildResult(
                    success=False,
                    error=f"Unknown source_type: {request.source_type}",
                    clone_duration_ms=int((time.monotonic() - start) * 1000),
                )

        except Exception as e:
            return BuildResult(
                success=False, error=str(e),
                clone_logs="\n".join(logs),
                clone_duration_ms=int((time.monotonic() - start) * 1000),
            )

    async def scan(self, request: BuildRequest, clone_dir: str | None) -> BuildResult:
        """Scan is handled by ScanDriver — return skip."""
        return BuildResult(
            success=True,
            scan_passed=None,
            scan_logs="Scan handled by ScanDriver",
            scan_duration_ms=0,
        )

    async def build(self, request: BuildRequest, clone_dir: str | None) -> BuildResult:
        """Build Docker image using `docker buildx build`."""
        start = time.monotonic()
        logs = []

        try:
            if request.source_type in ("docker_image", "docker_registry"):
                msg = f"Using pre-built image: {request.source_url}"
                logs.append(msg)
                self._log(request, "build", msg)
                return BuildResult(
                    success=True,
                    image_tag=request.source_url,
                    build_logs="\n".join(logs),
                    build_duration_ms=int((time.monotonic() - start) * 1000),
                )

            if not clone_dir:
                return BuildResult(
                    success=False,
                    error="No source directory for build",
                    build_duration_ms=int((time.monotonic() - start) * 1000),
                )

            sha_short = (request.commit_sha or "latest")[:12]
            tag = f"ae-{request.site_slug}:{sha_short}"

            msg = f"Building image {tag} with BuildKit..."
            logs.append(msg)
            self._log(request, "build", msg)

            # Build command with buildx
            cmd = [
                "docker", "buildx", "build",
                "--file", request.dockerfile_path,
                "--tag", tag,
                "--tag", f"ae-{request.site_slug}:latest",
                "--load",  # Load into local docker daemon
                "--progress=plain",  # Plain text output for logs
            ]

            # Build args
            for key, value in (request.build_env or {}).items():
                cmd.extend(["--build-arg", f"{key}={value}"])

            # Cache configuration — use inline cache for layer reuse
            cmd.extend([
                "--cache-from", f"type=registry,ref=ae-{request.site_slug}:buildcache",
                "--cache-to", "type=inline",
            ])

            cmd.append(clone_dir)

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await proc.communicate()

            if stdout:
                for line in stdout.decode().splitlines():
                    line = line.strip()
                    if line:
                        logs.append(line)
                        self._log(request, "build", line)

            if proc.returncode != 0:
                return BuildResult(
                    success=False,
                    error=f"BuildKit build failed (exit {proc.returncode})",
                    build_logs="\n".join(logs),
                    build_duration_ms=int((time.monotonic() - start) * 1000),
                )

            msg = f"Image built: {tag}"
            logs.append(msg)
            self._log(request, "build", msg)

            return BuildResult(
                success=True,
                image_tag=tag,
                build_logs="\n".join(logs),
                build_duration_ms=int((time.monotonic() - start) * 1000),
            )

        except Exception as e:
            return BuildResult(
                success=False, error=str(e),
                build_logs="\n".join(logs),
                build_duration_ms=int((time.monotonic() - start) * 1000),
            )

    async def push(self, request: BuildRequest, image_tag: str) -> BuildResult:
        """Push image using `docker buildx build --push` or docker push."""
        start = time.monotonic()
        logs = []

        registry_url = request.registry_url
        if not registry_url:
            msg = "No registry configured — skipping push"
            logs.append(msg)
            self._log(request, "push", msg)
            return BuildResult(
                success=True, image_tag=image_tag,
                push_logs="\n".join(logs),
                push_duration_ms=int((time.monotonic() - start) * 1000),
            )

        try:
            registry_tag = f"{registry_url}/{image_tag}"
            msg = f"Pushing {image_tag} -> {registry_tag}"
            logs.append(msg)
            self._log(request, "push", msg)

            # Tag for registry
            tag_proc = await asyncio.create_subprocess_exec(
                "docker", "tag", image_tag, registry_tag,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await tag_proc.communicate()

            # Push
            push_proc = await asyncio.create_subprocess_exec(
                "docker", "push", registry_tag,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await push_proc.communicate()

            if stdout:
                for line in stdout.decode().splitlines():
                    line = line.strip()
                    if line:
                        logs.append(line)

            if push_proc.returncode != 0:
                return BuildResult(
                    success=False,
                    error=f"Push failed (exit {push_proc.returncode})",
                    push_logs="\n".join(logs),
                    push_duration_ms=int((time.monotonic() - start) * 1000),
                )

            msg = f"Push complete: {registry_tag}"
            logs.append(msg)
            self._log(request, "push", msg)

            return BuildResult(
                success=True, image_tag=registry_tag,
                push_logs="\n".join(logs),
                push_duration_ms=int((time.monotonic() - start) * 1000),
            )

        except Exception as e:
            return BuildResult(
                success=False, error=str(e),
                push_logs="\n".join(logs),
                push_duration_ms=int((time.monotonic() - start) * 1000),
            )
