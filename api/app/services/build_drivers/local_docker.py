"""
Local Docker build driver — builds images using the local Docker daemon.

This is the default build driver for Adhara Engine. It:
  - Clones git repos to a temp directory
  - Runs Semgrep for static analysis (if enabled)
  - Builds Docker images via `docker build`
  - Optionally pushes to the local registry (localhost:5000)
"""

import asyncio
import logging
import tempfile
import time

import docker
from docker.errors import BuildError, ImageNotFound

from app.services.build_drivers.base import BuildDriver, BuildRequest, BuildResult

logger = logging.getLogger(__name__)


class LocalDockerBuilder(BuildDriver):
    """Builds Docker images on the local Docker daemon."""

    def __init__(self):
        self.client = docker.from_env()

    def _log(self, request: BuildRequest, stage: str, line: str):
        """Send a log line to the callback if registered."""
        if request.log_callback:
            request.log_callback(stage, line)

    async def clone(self, request: BuildRequest) -> BuildResult:
        """Clone git repo or resolve image source."""
        start = time.monotonic()
        logs = []

        try:
            if request.source_type == "git_repo":
                clone_dir = tempfile.mkdtemp(prefix="ae-clone-")

                # Build clone URL with credentials if provided
                clone_url = request.source_url
                if request.git_token and clone_url:
                    # Insert credentials into HTTPS URL
                    # https://user:token@github.com/org/repo.git
                    if clone_url.startswith("https://"):
                        username = request.git_token_username or "oauth2"
                        clone_url = clone_url.replace(
                            "https://",
                            f"https://{username}:{request.git_token}@",
                        )

                msg = f"Cloning {request.source_url}..."
                logs.append(msg)
                self._log(request, "clone", msg)

                # Clone with optional branch/ref
                clone_args = ["git", "clone", "--depth=1"]
                if request.git_ref:
                    # Extract branch name from refs/heads/main format
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
                    # Sanitize credentials from error message
                    if request.git_token:
                        error = error.replace(request.git_token, "***")
                    return BuildResult(
                        success=False,
                        error=f"Git clone failed: {error}",
                        clone_logs="\n".join(logs),
                        clone_duration_ms=int((time.monotonic() - start) * 1000),
                    )

                # Get commit SHA if not provided
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

            elif request.source_type == "upload":
                msg = f"Using uploaded source: {request.source_url}"
                logs.append(msg)
                self._log(request, "clone", msg)
                return BuildResult(
                    success=True,
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
                success=False,
                error=str(e),
                clone_logs="\n".join(logs),
                clone_duration_ms=int((time.monotonic() - start) * 1000),
            )

    async def scan(self, request: BuildRequest, clone_dir: str | None) -> BuildResult:
        """Run Semgrep static analysis on cloned source."""
        start = time.monotonic()
        logs = []

        if not request.scan_enabled:
            msg = "Scanning disabled — skipping"
            logs.append(msg)
            self._log(request, "scan", msg)
            return BuildResult(
                success=True,
                scan_passed=None,
                scan_logs="\n".join(logs),
                scan_duration_ms=int((time.monotonic() - start) * 1000),
            )

        if not clone_dir:
            msg = "No source directory — skipping scan"
            logs.append(msg)
            self._log(request, "scan", msg)
            return BuildResult(
                success=True,
                scan_passed=None,
                scan_logs="\n".join(logs),
                scan_duration_ms=int((time.monotonic() - start) * 1000),
            )

        try:
            msg = f"Running Semgrep scan (fail on: {request.scan_fail_on})..."
            logs.append(msg)
            self._log(request, "scan", msg)

            # Run semgrep with auto config
            proc = await asyncio.create_subprocess_exec(
                "semgrep", "scan", "--config=auto", "--json",
                "--severity", request.scan_fail_on.upper(),
                clone_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            import json
            findings = {}
            if stdout:
                try:
                    findings = json.loads(stdout.decode())
                except json.JSONDecodeError:
                    pass

            num_findings = len(findings.get("results", []))
            scan_passed = proc.returncode == 0

            if scan_passed:
                msg = f"Scan passed. {num_findings} findings (none at {request.scan_fail_on} or above)"
            else:
                msg = f"Scan FAILED. {num_findings} findings at {request.scan_fail_on} or above"
            logs.append(msg)
            self._log(request, "scan", msg)

            return BuildResult(
                success=True,  # Scan ran successfully (even if findings exist)
                scan_passed=scan_passed,
                scan_findings=findings,
                scan_logs="\n".join(logs),
                scan_duration_ms=int((time.monotonic() - start) * 1000),
            )

        except FileNotFoundError:
            msg = "Semgrep not installed — skipping scan"
            logs.append(msg)
            self._log(request, "scan", msg)
            return BuildResult(
                success=True,
                scan_passed=None,
                scan_logs="\n".join(logs),
                scan_duration_ms=int((time.monotonic() - start) * 1000),
            )
        except Exception as e:
            return BuildResult(
                success=False,
                error=f"Scan error: {e}",
                scan_logs="\n".join(logs),
                scan_duration_ms=int((time.monotonic() - start) * 1000),
            )

    async def build(self, request: BuildRequest, clone_dir: str | None) -> BuildResult:
        """Build Docker image from source."""
        start = time.monotonic()
        logs = []

        try:
            # For pre-built images, just pull
            if request.source_type in ("docker_image", "docker_registry"):
                image_ref = request.source_url
                if not image_ref:
                    return BuildResult(
                        success=False,
                        error="No image reference provided",
                        build_duration_ms=int((time.monotonic() - start) * 1000),
                    )

                if request.source_type == "docker_registry":
                    msg = f"Pulling {image_ref}..."
                    logs.append(msg)
                    self._log(request, "build", msg)
                    self.client.images.pull(image_ref)
                    msg = f"Pull complete: {image_ref}"
                    logs.append(msg)
                    self._log(request, "build", msg)
                else:
                    msg = f"Using pre-built image: {image_ref}"
                    logs.append(msg)
                    self._log(request, "build", msg)

                return BuildResult(
                    success=True,
                    image_tag=image_ref,
                    build_logs="\n".join(logs),
                    build_duration_ms=int((time.monotonic() - start) * 1000),
                )

            # Build from source
            if not clone_dir:
                return BuildResult(
                    success=False,
                    error="No source directory for build",
                    build_duration_ms=int((time.monotonic() - start) * 1000),
                )

            # Generate image tag with commit SHA for traceability
            sha_short = (request.commit_sha or "latest")[:12]
            tag = f"ae-{request.site_slug}:{sha_short}"
            latest_tag = f"ae-{request.site_slug}:latest"

            msg = f"Building image {tag} from {request.dockerfile_path}..."
            logs.append(msg)
            self._log(request, "build", msg)

            buildargs = dict(request.build_env or {})
            image, build_output = self.client.images.build(
                path=clone_dir,
                dockerfile=request.dockerfile_path,
                tag=tag,
                buildargs=buildargs,
                rm=True,
            )

            # Also tag as latest for easy reference
            image.tag(f"ae-{request.site_slug}", "latest")

            for chunk in build_output:
                if "stream" in chunk:
                    line = chunk["stream"].strip()
                    if line:
                        logs.append(line)
                        self._log(request, "build", line)

            msg = f"Image built: {tag}"
            logs.append(msg)
            self._log(request, "build", msg)

            return BuildResult(
                success=True,
                image_tag=tag,
                build_logs="\n".join(logs),
                build_duration_ms=int((time.monotonic() - start) * 1000),
            )

        except BuildError as e:
            error_msg = str(e)
            logs.append(f"Build failed: {error_msg}")
            return BuildResult(
                success=False,
                error=error_msg,
                build_logs="\n".join(logs),
                build_duration_ms=int((time.monotonic() - start) * 1000),
            )
        except Exception as e:
            return BuildResult(
                success=False,
                error=str(e),
                build_logs="\n".join(logs),
                build_duration_ms=int((time.monotonic() - start) * 1000),
            )

    async def push(self, request: BuildRequest, image_tag: str) -> BuildResult:
        """Push image to local registry."""
        start = time.monotonic()
        logs = []

        registry_url = request.registry_url
        if not registry_url:
            msg = "No registry configured — skipping push (using local image)"
            logs.append(msg)
            self._log(request, "push", msg)
            return BuildResult(
                success=True,
                image_tag=image_tag,
                push_logs="\n".join(logs),
                push_duration_ms=int((time.monotonic() - start) * 1000),
            )

        try:
            # Tag for registry
            # image_tag is like "ae-mysite:abc123def456"
            registry_tag = f"{registry_url}/{image_tag}"
            msg = f"Tagging {image_tag} -> {registry_tag}"
            logs.append(msg)
            self._log(request, "push", msg)

            image = self.client.images.get(image_tag)
            # Parse repo:tag from registry_tag
            repo, tag = registry_tag.rsplit(":", 1)
            image.tag(repo, tag)

            # Push
            msg = f"Pushing to {registry_url}..."
            logs.append(msg)
            self._log(request, "push", msg)

            push_output = self.client.images.push(repo, tag=tag, stream=True, decode=True)
            for chunk in push_output:
                if "status" in chunk:
                    line = chunk.get("status", "")
                    if chunk.get("progress"):
                        line += f" {chunk['progress']}"
                    logs.append(line)
                if "error" in chunk:
                    return BuildResult(
                        success=False,
                        error=chunk["error"],
                        push_logs="\n".join(logs),
                        push_duration_ms=int((time.monotonic() - start) * 1000),
                    )

            # Get digest
            digest = None
            try:
                pushed = self.client.images.get(registry_tag)
                if pushed.attrs.get("RepoDigests"):
                    digest = pushed.attrs["RepoDigests"][0].split("@")[1]
            except Exception:
                pass

            msg = f"Push complete: {registry_tag}"
            logs.append(msg)
            self._log(request, "push", msg)

            return BuildResult(
                success=True,
                image_tag=registry_tag,
                image_digest=digest,
                push_logs="\n".join(logs),
                push_duration_ms=int((time.monotonic() - start) * 1000),
            )

        except Exception as e:
            return BuildResult(
                success=False,
                error=str(e),
                push_logs="\n".join(logs),
                push_duration_ms=int((time.monotonic() - start) * 1000),
            )
