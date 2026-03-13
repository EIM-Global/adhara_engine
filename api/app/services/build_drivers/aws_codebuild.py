"""
AWS CodeBuild driver — offloads image builds to AWS CodeBuild.

Requires:
  - boto3 SDK (lazy import — not a hard dependency)
  - IAM role with CodeBuild, S3, and ECR permissions

Environment variables:
  - AWS_REGION: AWS region (default: us-east-1)
  - AWS_CODEBUILD_PROJECT: CodeBuild project name
  - AWS_ECR_REGISTRY: ECR registry URL (e.g., 123456789.dkr.ecr.us-east-1.amazonaws.com)
  - AWS_BUILD_BUCKET: S3 bucket for source upload

The driver:
  1. Uploads source tarball to S3
  2. Starts a CodeBuild build
  3. Polls for completion
  4. Returns the ECR image tag
"""

import asyncio
import logging
import os
import tarfile
import tempfile
import time

from app.services.build_drivers.base import BuildDriver, BuildRequest, BuildResult

logger = logging.getLogger(__name__)


class AWSCodeBuildDriver(BuildDriver):
    """Builds Docker images via AWS CodeBuild."""

    def __init__(self):
        self._region = os.environ.get("AWS_REGION", "us-east-1")
        self._project_name = os.environ.get("AWS_CODEBUILD_PROJECT", "adhara-build")
        self._ecr_registry = os.environ.get("AWS_ECR_REGISTRY")
        self._build_bucket = os.environ.get("AWS_BUILD_BUCKET")

    def _log(self, request: BuildRequest, stage: str, line: str):
        if request.log_callback:
            request.log_callback(stage, line)

    async def clone(self, request: BuildRequest) -> BuildResult:
        """Clone source locally for upload to S3."""
        start = time.monotonic()
        logs = []

        try:
            if request.source_type != "git_repo":
                return BuildResult(
                    success=True,
                    image_tag=request.source_url,
                    clone_logs=f"Using pre-built image: {request.source_url}",
                    clone_duration_ms=int((time.monotonic() - start) * 1000),
                )

            clone_dir = tempfile.mkdtemp(prefix="ae-aws-clone-")
            clone_url = request.source_url
            if request.git_token and clone_url and clone_url.startswith("https://"):
                username = request.git_token_username or "oauth2"
                clone_url = clone_url.replace(
                    "https://", f"https://{username}:{request.git_token}@"
                )

            msg = f"Cloning {request.source_url} for AWS CodeBuild..."
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
        """Submit build to AWS CodeBuild."""
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

        if not self._ecr_registry:
            return BuildResult(
                success=False,
                error="AWS_ECR_REGISTRY not configured",
                build_duration_ms=int((time.monotonic() - start) * 1000),
            )

        if not self._build_bucket:
            return BuildResult(
                success=False,
                error="AWS_BUILD_BUCKET not configured",
                build_duration_ms=int((time.monotonic() - start) * 1000),
            )

        try:
            import boto3
        except ImportError:
            return BuildResult(
                success=False,
                error="boto3 SDK not installed. Run: pip install boto3",
                build_logs="\n".join(logs),
                build_duration_ms=int((time.monotonic() - start) * 1000),
            )

        try:
            sha_short = (request.commit_sha or "latest")[:12]
            image_tag = f"{self._ecr_registry}/ae-{request.site_slug}:{sha_short}"

            msg = f"Submitting build to AWS CodeBuild -> {image_tag}"
            logs.append(msg)
            self._log(request, "build", msg)

            # 1. Create source tarball and upload to S3
            tarball_path = tempfile.mktemp(suffix=".tar.gz")
            with tarfile.open(tarball_path, "w:gz") as tar:
                tar.add(clone_dir, arcname=".")

            s3_key = f"source/ae-{request.site_slug}-{sha_short}.tar.gz"

            s3 = boto3.client("s3", region_name=self._region)
            await asyncio.to_thread(
                s3.upload_file, tarball_path, self._build_bucket, s3_key
            )

            msg = f"Source uploaded to s3://{self._build_bucket}/{s3_key}"
            logs.append(msg)
            self._log(request, "build", msg)

            # 2. Start CodeBuild
            codebuild = boto3.client("codebuild", region_name=self._region)

            env_overrides = [
                {"name": "IMAGE_TAG", "value": image_tag, "type": "PLAINTEXT"},
                {"name": "DOCKERFILE", "value": request.dockerfile_path, "type": "PLAINTEXT"},
            ]
            for k, v in (request.build_env or {}).items():
                env_overrides.append(
                    {"name": k, "value": v, "type": "PLAINTEXT"}
                )

            build_resp = await asyncio.to_thread(
                codebuild.start_build,
                projectName=self._project_name,
                sourceTypeOverride="S3",
                sourceLocationOverride=f"{self._build_bucket}/{s3_key}",
                environmentVariablesOverride=env_overrides,
                buildspecOverride=f"""
version: 0.2
phases:
  pre_build:
    commands:
      - echo Logging in to Amazon ECR...
      - aws ecr get-login-password --region {self._region} | docker login --username AWS --password-stdin {self._ecr_registry}
  build:
    commands:
      - echo Building Docker image...
      - docker build -t $IMAGE_TAG -f $DOCKERFILE .
  post_build:
    commands:
      - echo Pushing Docker image...
      - docker push $IMAGE_TAG
""".strip(),
            )

            build_id = build_resp["build"]["id"]
            msg = f"CodeBuild started: {build_id}"
            logs.append(msg)
            self._log(request, "build", msg)

            # 3. Poll for completion
            while True:
                await asyncio.sleep(10)
                status_resp = await asyncio.to_thread(
                    codebuild.batch_get_builds, ids=[build_id]
                )
                build = status_resp["builds"][0]
                build_status = build["buildStatus"]

                if build_status == "SUCCEEDED":
                    duration_ms = int((time.monotonic() - start) * 1000)
                    msg = f"AWS CodeBuild succeeded: {image_tag}"
                    logs.append(msg)
                    self._log(request, "build", msg)

                    if build.get("logs", {}).get("deepLink"):
                        logs.append(f"Build logs: {build['logs']['deepLink']}")

                    return BuildResult(
                        success=True,
                        image_tag=image_tag,
                        build_logs="\n".join(logs),
                        build_duration_ms=duration_ms,
                    )

                elif build_status in ("FAILED", "FAULT", "STOPPED", "TIMED_OUT"):
                    duration_ms = int((time.monotonic() - start) * 1000)
                    error = f"CodeBuild {build_status}"
                    if build.get("phases"):
                        for phase in build["phases"]:
                            if phase.get("phaseStatus") == "FAILED":
                                contexts = phase.get("contexts", [])
                                if contexts:
                                    error += f": {contexts[0].get('message', '')}"
                    logs.append(error)
                    return BuildResult(
                        success=False, error=error,
                        build_logs="\n".join(logs),
                        build_duration_ms=duration_ms,
                    )

                # Still in progress — check timeout
                elapsed = time.monotonic() - start
                if elapsed > 600:
                    # Cancel build
                    await asyncio.to_thread(
                        codebuild.stop_build, id=build_id
                    )
                    return BuildResult(
                        success=False,
                        error="Build timed out after 10 minutes",
                        build_logs="\n".join(logs),
                        build_duration_ms=int(elapsed * 1000),
                    )

        except Exception as e:
            return BuildResult(
                success=False, error=str(e),
                build_logs="\n".join(logs),
                build_duration_ms=int((time.monotonic() - start) * 1000),
            )

    async def push(self, request: BuildRequest, image_tag: str) -> BuildResult:
        """CodeBuild pushes to ECR as part of the build."""
        return BuildResult(
            success=True,
            image_tag=image_tag,
            push_logs=f"Image already pushed by CodeBuild: {image_tag}",
            push_duration_ms=0,
        )
