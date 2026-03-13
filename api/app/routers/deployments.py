"""
Deployment and pipeline endpoints.

Deploy flow:
  POST /api/v1/sites/{id}/deploy
    -> Creates PipelineRun + enqueues ARQ job
    -> Returns 202 with pipeline_run_id
    -> Worker executes: clone -> scan -> build -> push -> deploy

Pipeline monitoring:
  GET /api/v1/sites/{id}/pipelines       — list pipeline runs
  GET /api/v1/pipelines/{id}             — get pipeline run with stages
  POST /api/v1/pipelines/{id}/cancel     — cancel a running pipeline

Legacy sync deploy is still available via `synchronous: true` in request body.
"""

import uuid
from datetime import datetime, timezone

from arq import ArqRedis
from arq.connections import RedisSettings, create_pool
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import require_auth
from app.core.authorize import authorize
from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import Permission
from app.models.deployment import Deployment
from app.models.pipeline import PipelineRun, PipelineStage
from app.models.site import Site
from app.schemas.deployment import DeploymentResponse
from app.schemas.pipeline import (
    DeployRequest,
    PipelineRunResponse,
    PipelineRunSummary,
)
from app.services import container_manager

router = APIRouter(tags=["deployments"])

# Redis pool for enqueueing jobs — lazily initialized
_arq_pool: ArqRedis | None = None


async def _get_arq_pool() -> ArqRedis:
    """Get or create the ARQ Redis connection pool."""
    global _arq_pool
    if _arq_pool is None:
        # Parse redis URL
        url = settings.redis_url.replace("redis://", "")
        parts = url.split("/")
        host_port = parts[0]
        database = int(parts[1]) if len(parts) > 1 else 0
        host, port = (host_port.rsplit(":", 1) + ["6379"])[:2]
        _arq_pool = await create_pool(
            RedisSettings(host=host, port=int(port), database=database)
        )
    return _arq_pool


# ── Deploy ────────────────────────────────────────────────────────────


@router.post("/api/v1/sites/{site_id}/deploy", status_code=202)
async def deploy_site(
    site_id: uuid.UUID,
    body: DeployRequest | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Trigger a deployment for a site.

    Creates a PipelineRun and enqueues an ARQ job to execute the pipeline.
    Returns 202 with the pipeline_run_id for tracking.

    If `synchronous: true` is passed, falls back to legacy sync deploy.
    """
    await authorize(user, Permission.SITE_DEPLOY, "site", site_id, db)

    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    # Legacy sync deploy path
    if body and body.synchronous:
        try:
            deployment = await container_manager.deploy_site(db, str(site_id))
            return DeploymentResponse.model_validate(deployment)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Pipeline-based async deploy
    user_id = user.get("sub", "unknown")

    run = PipelineRun(
        site_id=site.id,
        tenant_id=site.tenant_id,
        trigger="manual",
        git_provider=site.git_provider,
        git_ref=body.git_ref if body else None,
        commit_sha=body.commit_sha if body else None,
        status="pending",
        build_driver=body.build_driver if body else site.build_driver,
        triggered_by=user_id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Enqueue pipeline job
    try:
        pool = await _get_arq_pool()
        await pool.enqueue_job("run_pipeline", str(run.id))
    except Exception as e:
        run.status = "failed"
        db.commit()
        raise HTTPException(
            status_code=503,
            detail=f"Failed to enqueue pipeline job: {e}",
        )

    return {
        "pipeline_run_id": str(run.id),
        "status": "pending",
        "message": "Pipeline enqueued. Use GET /api/v1/pipelines/{id} to track progress.",
    }


# ── Stop / Restart ───────────────────────────────────────────────────


@router.post("/api/v1/sites/{site_id}/stop", status_code=200)
async def stop_site(
    site_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Stop a running site."""
    await authorize(user, Permission.SITE_STOP, "site", site_id, db)
    try:
        await container_manager.stop_site(db, str(site_id))
        return {"status": "stopped", "site_id": str(site_id)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/v1/sites/{site_id}/restart", status_code=200)
async def restart_site(
    site_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Restart a site's container."""
    await authorize(user, Permission.SITE_RESTART, "site", site_id, db)
    try:
        await container_manager.restart_site(db, str(site_id))
        return {"status": "restarted", "site_id": str(site_id)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Logs / Status ────────────────────────────────────────────────────


@router.get("/api/v1/sites/{site_id}/logs")
async def get_site_logs(
    site_id: uuid.UUID,
    tail: int = 100,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get container logs for a site."""
    await authorize(user, Permission.SITE_LOGS, "site", site_id, db)
    try:
        lines = await container_manager.get_site_logs(db, str(site_id), tail=tail)
        return {"site_id": str(site_id), "lines": lines}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/api/v1/sites/{site_id}/status")
async def get_site_container_status(
    site_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get container status for a site."""
    await authorize(user, Permission.SITE_VIEW, "site", site_id, db)
    try:
        return await container_manager.get_site_status(db, str(site_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/api/v1/sites/{site_id}/deployments",
    response_model=list[DeploymentResponse],
)
async def list_deployments(
    site_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """List all deployments for a site."""
    await authorize(user, Permission.SITE_VIEW, "site", site_id, db)
    return (
        db.query(Deployment)
        .filter(Deployment.site_id == site_id)
        .order_by(Deployment.version.desc())
        .all()
    )


# ── Pipeline Endpoints ───────────────────────────────────────────────


@router.get(
    "/api/v1/sites/{site_id}/pipelines",
    response_model=list[PipelineRunSummary],
)
async def list_pipelines(
    site_id: uuid.UUID,
    limit: int = 20,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """List pipeline runs for a site."""
    await authorize(user, Permission.SITE_VIEW, "site", site_id, db)
    return (
        db.query(PipelineRun)
        .filter(PipelineRun.site_id == site_id)
        .order_by(PipelineRun.created_at.desc())
        .limit(limit)
        .all()
    )


@router.get(
    "/api/v1/pipelines/{pipeline_run_id}",
    response_model=PipelineRunResponse,
)
async def get_pipeline(
    pipeline_run_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get a pipeline run with all its stages."""
    run = db.query(PipelineRun).filter(PipelineRun.id == pipeline_run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    await authorize(user, Permission.SITE_VIEW, "site", run.site_id, db)
    return run


@router.post("/api/v1/pipelines/{pipeline_run_id}/cancel", status_code=200)
async def cancel_pipeline(
    pipeline_run_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Cancel a running or pending pipeline."""
    run = db.query(PipelineRun).filter(PipelineRun.id == pipeline_run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    if run.status not in ("pending", "running"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel pipeline in status: {run.status}",
        )

    run.status = "cancelled"
    run.finished_at = datetime.now(timezone.utc)

    # Mark pending/running stages as skipped
    for stage in run.stages:
        if stage.status in ("pending", "running"):
            stage.status = "skipped"
            stage.finished_at = datetime.now(timezone.utc)

    db.commit()
    return {"status": "cancelled", "pipeline_run_id": str(run.id)}


@router.post("/api/v1/sites/{site_id}/pipelines/cancel-pending", status_code=200)
async def cancel_pending_pipelines(
    site_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Cancel all pending pipeline runs for a site."""
    await authorize(user, Permission.SITE_DEPLOY, "site", site_id, db)

    pending_runs = (
        db.query(PipelineRun)
        .filter(PipelineRun.site_id == site_id, PipelineRun.status == "pending")
        .all()
    )

    now = datetime.now(timezone.utc)
    cancelled_count = 0
    for run in pending_runs:
        run.status = "cancelled"
        run.finished_at = now
        for stage in run.stages:
            if stage.status in ("pending", "running"):
                stage.status = "skipped"
                stage.finished_at = now
        cancelled_count += 1

    db.commit()
    return {"cancelled": cancelled_count, "site_id": str(site_id)}


@router.delete("/api/v1/sites/{site_id}/pipelines/completed", status_code=200)
async def clear_completed_pipelines(
    site_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Delete all finished (cancelled/failed/success) pipeline runs for a site.

    Keeps only pending and running pipelines. Use this to clean up old history.
    """
    await authorize(user, Permission.SITE_DEPLOY, "site", site_id, db)

    finished_runs = (
        db.query(PipelineRun)
        .filter(
            PipelineRun.site_id == site_id,
            PipelineRun.status.in_(["cancelled", "failed", "success"]),
        )
        .all()
    )

    deleted_count = 0
    for run in finished_runs:
        # Delete stages first (cascade may handle this, but be explicit)
        for stage in run.stages:
            db.delete(stage)
        db.delete(run)
        deleted_count += 1

    db.commit()
    return {"deleted": deleted_count, "site_id": str(site_id)}


@router.post("/api/v1/pipelines/{pipeline_run_id}/retry", status_code=202)
async def retry_pipeline(
    pipeline_run_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Retry a failed or cancelled pipeline by creating a new run with the same parameters."""
    old_run = db.query(PipelineRun).filter(PipelineRun.id == pipeline_run_id).first()
    if not old_run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    if old_run.status not in ("failed", "cancelled"):
        raise HTTPException(
            status_code=409,
            detail=f"Can only retry failed or cancelled pipelines, not: {old_run.status}",
        )

    await authorize(user, Permission.SITE_DEPLOY, "site", old_run.site_id, db)

    user_id = user.get("sub", "unknown")
    new_run = PipelineRun(
        site_id=old_run.site_id,
        tenant_id=old_run.tenant_id,
        trigger="manual",
        git_provider=old_run.git_provider,
        git_ref=old_run.git_ref,
        commit_sha=old_run.commit_sha,
        status="pending",
        build_driver=old_run.build_driver,
        triggered_by=user_id,
    )
    db.add(new_run)
    db.commit()
    db.refresh(new_run)

    try:
        pool = await _get_arq_pool()
        await pool.enqueue_job("run_pipeline", str(new_run.id))
    except Exception as e:
        new_run.status = "failed"
        db.commit()
        raise HTTPException(status_code=503, detail=f"Failed to enqueue pipeline job: {e}")

    return {
        "pipeline_run_id": str(new_run.id),
        "status": "pending",
        "message": "Pipeline retry enqueued.",
    }


# ── Registry Images ──────────────────────────────────────────────


@router.get("/api/v1/sites/{site_id}/images")
async def list_site_images(
    site_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """List Docker images in the registry for a site."""
    await authorize(user, Permission.SITE_VIEW, "site", site_id, db)

    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    repo_name = f"ae-{site.slug}"
    import httpx

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # List tags for this site's repo
            resp = await client.get(f"http://registry:5000/v2/{repo_name}/tags/list")
            if resp.status_code == 404:
                return {"repository": repo_name, "tags": []}
            resp.raise_for_status()
            data = resp.json()
            return {"repository": repo_name, "tags": data.get("tags", [])}
    except httpx.ConnectError:
        return {"repository": repo_name, "tags": [], "error": "Registry unavailable"}
    except Exception as e:
        return {"repository": repo_name, "tags": [], "error": str(e)}
