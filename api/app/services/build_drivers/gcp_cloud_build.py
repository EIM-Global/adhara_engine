"""
GCP Cloud Build driver — offloads image builds to Google Cloud Build.

Requires:
  - google-cloud-build Python SDK (lazy import — not a hard dependency)
  - GCP service account with Cloud Build Editor role
  - Source code pushed to GCS or Cloud Source Repos

Environment variables:
  - GCP_PROJECT_ID: Google Cloud project ID
  - GCP_REGION: Build region (default: us-central1)
  - GOOGLE_APPLICATION_CREDENTIALS: Path to service account key JSON

The driver:
  1. Uploads source to a GCS staging bucket
  2. Submits a Cloud Build job
  3. Polls for completion
  4. Returns the built image tag from Artifact Registry
"""

import asyncio
import logging
import os
import tarfile
import tempfile
import time

from app.services.build_drivers.base import BuildDriver, BuildRequest, BuildResult

logger = logging.getLogger(__name__)


class GCPCloudBuildDriver(BuildDriver):
    """Builds Docker images via Google Cloud Build."""

    def __init__(self):
        self._project_id = os.environ.get("GCP_PROJECT_ID")
        self._region = os.environ.get("GCP_REGION", "us-central1")
        self._staging_bucket = os.environ.get(
            "GCP_BUILD_STAGING_BUCKET", f"{self._project_id}_cloudbuild"
        )

    def _log(self, request: BuildRequest, stage: str, line: str):
        if request.log_callback:
            request.log_callback(stage, line)

    async def clone(self, request: BuildRequest) -> BuildResult:
        """Clone source locally for upload to GCS."""
        start = time.monotonic()
        logs = []

        try:
            if request.source_type != "git_repo":
                msg = f"GCP Cloud Build: source_type '{request.source_type}' — using direct image"
                logs.append(msg)
                return BuildResult(
                    success=True,
                    image_tag=request.source_url,
                    clone_logs="\n".join(logs),
                    clone_duration_ms=int((time.monotonic() - start) * 1000),
                )

            clone_dir = tempfile.mkdtemp(prefix="ae-gcp-clone-")
            clone_url = request.source_url
            if request.git_token and clone_url and clone_url.startswith("https://"):
                username = request.git_token_username or "oauth2"
                clone_url = clone_url.replace(
                    "https://", f"https://{username}:{request.git_token}@"
                )

            msg = f"Cloning {request.source_url} for GCP Cloud Build..."
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
            _, stderr = await proc.communicate()

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

            # Get commit SHA
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

        except Exception as e:
            return BuildResult(
                success=False, error=str(e),
                clone_logs="\n".join(logs),
                clone_duration_ms=int((time.monotonic() - start) * 1000),
            )

    async def scan(self, request: BuildRequest, clone_dir: str | None) -> BuildResult:
        """Scan handled by ScanDriver."""
        return BuildResult(
            success=True, scan_passed=None,
            scan_logs="Scan handled by ScanDriver",
            scan_duration_ms=0,
        )

    async def build(self, request: BuildRequest, clone_dir: str | None) -> BuildResult:
        """Submit build to Google Cloud Build."""
        start = time.monotonic()
        logs = []

        if request.source_type in ("docker_image", "docker_registry"):
            return BuildResult(
                success=True, image_tag=request.source_url,
                build_logs="Using pre-built image",
                build_duration_ms=int((time.monotonic() - start) * 1000),
            )

        if not clone_dir:
            return BuildResult(
                success=False, error="No source directory",
                build_duration_ms=int((time.monotonic() - start) * 1000),
            )

        if not self._project_id:
            return BuildResult(
                success=False,
                error="GCP_PROJECT_ID not configured",
                build_duration_ms=int((time.monotonic() - start) * 1000),
            )

        try:
            # Lazy import — google-cloud-build is optional
            from google.cloud.devtools import cloudbuild_v1
            from google.cloud import storage as gcs
        except ImportError:
            return BuildResult(
                success=False,
                error="google-cloud-build SDK not installed. Run: pip install google-cloud-build google-cloud-storage",
                build_logs="\n".join(logs),
                build_duration_ms=int((time.monotonic() - start) * 1000),
            )

        try:
            sha_short = (request.commit_sha or "latest")[:12]
            image_tag = f"{self._region}-docker.pkg.dev/{self._project_id}/adhara/ae-{request.site_slug}:{sha_short}"

            msg = f"Submitting build to GCP Cloud Build -> {image_tag}"
            logs.append(msg)
            self._log(request, "build", msg)

            # 1. Create source tarball and upload to GCS
            tarball_path = tempfile.mktemp(suffix=".tar.gz")
            with tarfile.open(tarball_path, "w:gz") as tar:
                tar.add(clone_dir, arcname=".")

            gcs_client = gcs.Client(project=self._project_id)
            bucket = gcs_client.bucket(self._staging_bucket)
            blob_name = f"source/ae-{request.site_slug}-{sha_short}.tar.gz"
            blob = bucket.blob(blob_name)
            blob.upload_from_filename(tarball_path)

            msg = f"Source uploaded to gs://{self._staging_bucket}/{blob_name}"
            logs.append(msg)
            self._log(request, "build", msg)

            # 2. Submit Cloud Build
            client = cloudbuild_v1.CloudBuildClient()

            build_config = cloudbuild_v1.Build(
                source=cloudbuild_v1.Source(
                    storage_source=cloudbuild_v1.StorageSource(
                        bucket=self._staging_bucket,
                        object_=blob_name,
                    )
                ),
                steps=[
                    cloudbuild_v1.BuildStep(
                        name="gcr.io/cloud-builders/docker",
                        args=[
                            "build",
                            "-t", image_tag,
                            "-f", request.dockerfile_path,
                            *[
                                item
                                for k, v in (request.build_env or {}).items()
                                for item in ["--build-arg", f"{k}={v}"]
                            ],
                            ".",
                        ],
                    ),
                ],
                images=[image_tag],
                options=cloudbuild_v1.BuildOptions(
                    machine_type=cloudbuild_v1.BuildOptions.MachineType.E2_HIGHCPU_8,
                ),
                timeout={"seconds": 600},
            )

            operation = client.create_build(
                project_id=self._project_id, build=build_config
            )

            msg = "Build submitted, waiting for completion..."
            logs.append(msg)
            self._log(request, "build", msg)

            # 3. Poll for completion
            result_build = await asyncio.to_thread(operation.result, timeout=600)

            duration_ms = int((time.monotonic() - start) * 1000)

            if result_build.status == cloudbuild_v1.Build.Status.SUCCESS:
                msg = f"GCP Cloud Build succeeded: {image_tag}"
                logs.append(msg)
                self._log(request, "build", msg)

                # Append build logs
                if result_build.log_url:
                    logs.append(f"Build logs: {result_build.log_url}")

                return BuildResult(
                    success=True,
                    image_tag=image_tag,
                    build_logs="\n".join(logs),
                    build_duration_ms=duration_ms,
                )
            else:
                error = f"Cloud Build failed with status: {result_build.status.name}"
                logs.append(error)
                return BuildResult(
                    success=False, error=error,
                    build_logs="\n".join(logs),
                    build_duration_ms=duration_ms,
                )

        except Exception as e:
            return BuildResult(
                success=False, error=str(e),
                build_logs="\n".join(logs),
                build_duration_ms=int((time.monotonic() - start) * 1000),
            )

    async def push(self, request: BuildRequest, image_tag: str) -> BuildResult:
        """GCP Cloud Build pushes to Artifact Registry automatically."""
        start = time.monotonic()
        msg = f"Image already pushed by Cloud Build: {image_tag}"
        return BuildResult(
            success=True,
            image_tag=image_tag,
            push_logs=msg,
            push_duration_ms=int((time.monotonic() - start) * 1000),
        )
