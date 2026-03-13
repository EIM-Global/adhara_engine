"""
Pipeline orchestrator — ARQ task that runs the full build pipeline.

Stages: clone -> scan -> build -> push -> deploy

Each stage creates/updates PipelineStage records for tracking.
On success, creates a Deployment record and triggers blue-green deploy.
On failure, records the error and stops the pipeline.
"""

import logging
import re
import shutil
import tempfile
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.deployment import Deployment
from app.models.pipeline import PipelineRun, PipelineStage
from app.models.site import Site
from app.models.tenant import Tenant
from app.models.workspace import Workspace
from app.services.build_drivers import get_build_driver
from app.services.build_drivers.base import BuildRequest
from app.services.scan_drivers import get_scan_driver
from app.services.scan_drivers.base import ScanRequest
from app.services.deploy_target import DeployConfig
from app.services.local_deploy import LocalDeployTarget
from app.services.port_manager import allocate_port

logger = logging.getLogger(__name__)

_TOKEN_PATTERNS = [
    re.compile(r'https://[^@\s]+@', re.IGNORECASE),  # https://TOKEN@github.com
    re.compile(r'(ghp_|gho_|github_pat_)[A-Za-z0-9_]+'),  # GitHub tokens
    re.compile(r'(glpat-)[A-Za-z0-9\-_]+'),  # GitLab tokens
    re.compile(r'(ae_live_|ae_test_)[A-Za-z0-9_]+'),  # Adhara Engine tokens
]


def _sanitize_log(text: str) -> str:
    """Remove sensitive tokens from log output."""
    for pattern in _TOKEN_PATTERNS:
        text = pattern.sub('[REDACTED]', text)
    return text

# Stage definitions: (name, order)
PIPELINE_STAGES = [
    ("clone", 0),
    ("scan", 1),
    ("build", 2),
    ("push", 3),
    ("deploy", 4),
]


async def run_pipeline(ctx: dict, pipeline_run_id: str) -> dict:
    """ARQ task: execute the full build pipeline for a PipelineRun.

    Args:
        ctx: ARQ context (contains redis connection)
        pipeline_run_id: UUID of the PipelineRun to execute

    Returns:
        dict with status and deployment_id (if successful)
    """
    db = SessionLocal()
    clone_dir = None

    try:
        # Load pipeline run and related objects
        run = db.query(PipelineRun).filter(PipelineRun.id == pipeline_run_id).first()
        if not run:
            logger.error(f"PipelineRun {pipeline_run_id} not found")
            return {"status": "error", "error": "PipelineRun not found"}

        site = db.query(Site).filter(Site.id == run.site_id).first()
        if not site:
            _fail_run(db, run, "Site not found")
            return {"status": "error", "error": "Site not found"}

        workspace = db.query(Workspace).filter(Workspace.id == site.workspace_id).first()
        tenant = db.query(Tenant).filter(Tenant.id == site.tenant_id).first()

        # Mark run as running
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        site.status = "building"
        db.commit()

        # Create all stage records upfront
        stages = {}
        for name, order in PIPELINE_STAGES:
            stage = PipelineStage(
                pipeline_run_id=run.id,
                name=name,
                order=order,
                status="pending",
            )
            db.add(stage)
            stages[name] = stage
        db.commit()

        # Get the build driver
        driver_name = site.build_driver or run.build_driver
        driver = get_build_driver(driver_name)
        run.build_driver = driver_name or "local_docker"
        db.commit()

        # Build the request
        build_request = BuildRequest(
            site_id=str(site.id),
            site_slug=site.slug,
            tenant_slug=tenant.slug,
            workspace_slug=workspace.slug,
            source_type=site.source_type,
            source_url=site.source_url,
            git_ref=run.git_ref or f"refs/heads/{site.git_branch or 'main'}",
            commit_sha=run.commit_sha,
            git_token_username=site.git_token_username,
            git_token=site.git_token,
            dockerfile_path=site.dockerfile_path or "Dockerfile",
            build_command=site.build_command,
            build_env=dict(site.build_env or {}),
            scan_enabled=site.scan_enabled,
            scan_fail_on=site.scan_fail_on or "critical",
            registry_url="localhost:5000",  # Local registry
        )

        # ── Stage 1: Clone ────────────────────────────────────────
        clone_result = await _run_stage(
            db, stages["clone"], driver.clone, build_request
        )
        if not clone_result.success:
            _fail_run(db, run, clone_result.error, site=site)
            return {"status": "failed", "error": clone_result.error}

        # Track clone directory for cleanup
        if site.source_type == "git_repo":
            clone_dir = tempfile.gettempdir() + f"/ae-clone-"
            # The clone dir was created inside the driver — find it
            # We use the convention that clone_dir is in the build request
            # For now, we re-derive it from the driver's temp dir pattern
            import glob
            dirs = sorted(glob.glob(tempfile.gettempdir() + "/ae-clone-*"), key=lambda d: -1 * int(d.split("-")[-1]) if d.split("-")[-1].isdigit() else 0)
            clone_dir = dirs[0] if dirs else None

        # Update commit SHA if we got it from clone
        if build_request.commit_sha and not run.commit_sha:
            run.commit_sha = build_request.commit_sha
            db.commit()

        # ── Stage 2: Scan (uses ScanDriver) ──────────────────────
        if build_request.scan_enabled and clone_dir:
            scanner = get_scan_driver()  # Uses default (semgrep)
            scan_request = ScanRequest(
                site_id=str(site.id),
                site_slug=site.slug,
                source_dir=clone_dir,
                fail_on=build_request.scan_fail_on,
                log_callback=build_request.log_callback,
            )
            scan_result = await _run_scan_stage(
                db, stages["scan"], scanner, scan_request
            )
            if not scan_result.success:
                _fail_run(db, run, scan_result.error, site=site)
                return {"status": "failed", "error": scan_result.error}

            if scan_result.passed is False:
                stages["scan"].status = "failed"
                stages["scan"].error = "Scan found findings above threshold"
                stages["scan"].metadata_ = {
                    "findings_by_severity": scan_result.findings_by_severity,
                    "total_findings": scan_result.total_findings,
                }
                db.commit()
                _fail_run(db, run, "Scan failed — findings above threshold", site=site)
                return {"status": "failed", "error": "Scan failed"}
        else:
            # Skip scan stage
            stages["scan"].status = "skipped"
            stages["scan"].logs = "Scanning disabled or no source directory"
            stages["scan"].finished_at = datetime.now(timezone.utc)
            db.commit()

        # ── Stage 3: Build ────────────────────────────────────────
        build_result = await _run_stage(
            db, stages["build"], driver.build, build_request, clone_dir
        )
        if not build_result.success:
            _fail_run(db, run, build_result.error, site=site)
            return {"status": "failed", "error": build_result.error}

        image_tag = build_result.image_tag
        if not image_tag:
            _fail_run(db, run, "Build produced no image tag", site=site)
            return {"status": "failed", "error": "No image tag"}

        # ── Stage 4: Push ─────────────────────────────────────────
        push_result = await _run_stage(
            db, stages["push"], driver.push, build_request, image_tag
        )
        if not push_result.success:
            _fail_run(db, run, push_result.error, site=site)
            return {"status": "failed", "error": push_result.error}

        # Use the registry-qualified tag if push succeeded
        final_image = push_result.image_tag or image_tag
        run.image_ref = final_image
        db.commit()

        # ── Stage 5: Deploy ───────────────────────────────────────
        deploy_result = await _run_deploy_stage(
            db, stages["deploy"], site, workspace, tenant, final_image, run
        )
        if not deploy_result:
            _fail_run(db, run, "Deploy failed", site=site)
            return {"status": "failed", "error": "Deploy failed"}

        # Pipeline succeeded
        run.status = "succeeded"
        run.finished_at = datetime.now(timezone.utc)
        run.deployment_id = deploy_result.id
        site.status = "running"
        site.last_deployed_sha = run.commit_sha
        db.commit()

        logger.info(
            f"Pipeline {run.id} succeeded for site {site.slug} "
            f"-> deployment {deploy_result.id}"
        )

        return {
            "status": "succeeded",
            "deployment_id": str(deploy_result.id),
            "image": final_image,
        }

    except Exception as e:
        logger.exception(f"Pipeline {pipeline_run_id} crashed: {_sanitize_log(str(e))}")
        try:
            run = db.query(PipelineRun).filter(PipelineRun.id == pipeline_run_id).first()
            if run:
                _fail_run(db, run, str(e))
        except Exception:
            pass
        return {"status": "failed", "error": str(e)}

    finally:
        # Clean up clone directory
        if clone_dir:
            try:
                shutil.rmtree(clone_dir, ignore_errors=True)
            except Exception:
                pass
        db.close()


async def _run_stage(db: Session, stage: PipelineStage, func, *args) -> object:
    """Execute a pipeline stage and update the stage record."""
    stage.status = "running"
    stage.started_at = datetime.now(timezone.utc)
    db.commit()

    start = time.monotonic()
    try:
        result = await func(*args)
        duration_ms = int((time.monotonic() - start) * 1000)

        stage.finished_at = datetime.now(timezone.utc)
        stage.duration_ms = duration_ms

        if result.success:
            stage.status = "passed"
            # Consolidate logs from the result
            stage.logs = (
                result.clone_logs or result.scan_logs
                or result.build_logs or result.push_logs or ""
            )
        else:
            stage.status = "failed"
            stage.error = result.error
            stage.logs = (
                result.clone_logs or result.scan_logs
                or result.build_logs or result.push_logs or ""
            )

        db.commit()
        return result

    except Exception as e:
        stage.status = "failed"
        stage.error = str(e)
        stage.finished_at = datetime.now(timezone.utc)
        stage.duration_ms = int((time.monotonic() - start) * 1000)
        db.commit()

        # Return a failed result
        from app.services.build_drivers.base import BuildResult
        return BuildResult(success=False, error=str(e))


async def _run_scan_stage(
    db: Session, stage: PipelineStage, scanner, scan_request
):
    """Execute the scan stage using a ScanDriver."""
    from app.services.scan_drivers.base import ScanResult

    stage.status = "running"
    stage.started_at = datetime.now(timezone.utc)
    db.commit()

    try:
        result = await scanner.scan(scan_request)

        stage.finished_at = datetime.now(timezone.utc)
        stage.duration_ms = result.duration_ms
        stage.logs = result.logs

        if result.success:
            if result.passed is None:
                stage.status = "skipped"
            elif result.passed:
                stage.status = "passed"
            else:
                stage.status = "failed"
                stage.error = "Findings above threshold"
        else:
            stage.status = "failed"
            stage.error = result.error

        db.commit()
        return result

    except Exception as e:
        stage.status = "failed"
        stage.error = str(e)
        stage.finished_at = datetime.now(timezone.utc)
        db.commit()
        return ScanResult(success=False, error=str(e))


async def _run_deploy_stage(
    db: Session,
    stage: PipelineStage,
    site: Site,
    workspace: Workspace,
    tenant: Tenant,
    image_tag: str,
    run: PipelineRun,
) -> Deployment | None:
    """Execute the deploy stage — create Deployment record and start container."""
    stage.status = "running"
    stage.started_at = datetime.now(timezone.utc)
    db.commit()

    start = time.monotonic()
    logs = []

    try:
        # Auto-assign host port if not set
        if not site.host_port:
            site.host_port = allocate_port(db, str(site.id))
            db.flush()

        # Determine next version
        last_deploy = (
            db.query(Deployment)
            .filter(Deployment.site_id == site.id)
            .order_by(Deployment.version.desc())
            .first()
        )
        next_version = (last_deploy.version + 1) if last_deploy else 1

        # Create deployment record
        deployment = Deployment(
            site_id=site.id,
            tenant_id=site.tenant_id,
            version=next_version,
            source_ref=site.source_url,
            image_tag=image_tag,
            container_port=site.container_port,
            host_port=site.host_port,
            status="deploying",
        )
        db.add(deployment)
        db.commit()
        db.refresh(deployment)

        logs.append(f"Deployment v{next_version} created")

        # Build runtime env
        runtime_env = {}
        if workspace.adhara_api_url:
            runtime_env["ADHARA_API_URL"] = workspace.adhara_api_url
        # NOTE: Workspace API key is no longer injected into containers.
        # Use per-deployment scoped tokens instead (see PR-8/PR-16).
        runtime_env["ADHARA_PUBLIC_URL"] = f"http://localhost:{site.host_port}"
        runtime_env.update(site.runtime_env or {})

        # Deploy using LocalDeployTarget (blue-green)
        target = LocalDeployTarget()
        config = DeployConfig(
            site_id=str(site.id),
            site_slug=site.slug,
            tenant_slug=tenant.slug,
            workspace_slug=workspace.slug,
            image_tag=image_tag,
            source_type="docker_image",  # We already built the image
            source_url=image_tag,
            dockerfile_path=site.dockerfile_path or "Dockerfile",
            container_port=site.container_port,
            host_port=site.host_port,
            runtime_env=runtime_env,
            health_check_path=site.health_check_path,
            custom_domains=site.custom_domains or [],
        )

        result = await target.deploy(config)

        duration_ms = int((time.monotonic() - start) * 1000)

        if result.success:
            deployment.status = "live"
            deployment.deployed_at = datetime.now(timezone.utc)
            deployment.build_logs = "\n".join(logs)
            site.current_deployment_id = deployment.id
            site.active_container_id = result.container_id

            stage.status = "passed"
            stage.logs = "\n".join(logs)
            logs.append(f"Container started: {result.container_id}")
        else:
            deployment.status = "failed"
            deployment.deploy_logs = result.error

            stage.status = "failed"
            stage.error = result.error
            stage.logs = "\n".join(logs)

        stage.finished_at = datetime.now(timezone.utc)
        stage.duration_ms = duration_ms
        db.commit()

        return deployment if result.success else None

    except Exception as e:
        logger.exception(f"Deploy stage failed: {e}")
        stage.status = "failed"
        stage.error = str(e)
        stage.finished_at = datetime.now(timezone.utc)
        stage.duration_ms = int((time.monotonic() - start) * 1000)
        db.commit()
        return None


def _fail_run(
    db: Session, run: PipelineRun, error: str, site: Site | None = None
):
    """Mark a pipeline run as failed."""
    run.status = "failed"
    run.finished_at = datetime.now(timezone.utc)
    if site:
        site.status = "error"
    db.commit()
    logger.error(f"Pipeline {run.id} failed: {_sanitize_log(error)}")
