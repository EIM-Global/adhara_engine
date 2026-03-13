"""
Preview environment lifecycle manager.

Handles:
  - Creating preview environments from PR events
  - Updating preview deploys on PR push
  - Destroying previews on PR merge/close
  - TTL-based cleanup of stale previews
"""

import logging
from datetime import datetime, timezone

from arq.connections import RedisSettings, create_pool
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.pipeline import PipelineRun
from app.models.preview_environment import PreviewEnvironment
from app.models.site import Site
from app.services.port_manager import allocate_port

logger = logging.getLogger(__name__)

# Lazily initialized ARQ pool
_arq_pool = None


async def _get_arq_pool():
    global _arq_pool
    if _arq_pool is None:
        url = settings.redis_url.replace("redis://", "")
        parts = url.split("/")
        host_port = parts[0]
        database = int(parts[1]) if len(parts) > 1 else 0
        host, port = (host_port.rsplit(":", 1) + ["6379"])[:2]
        _arq_pool = await create_pool(
            RedisSettings(host=host, port=int(port), database=database)
        )
    return _arq_pool


async def create_or_update_preview(
    db: Session,
    site: Site,
    pr_number: int,
    pr_branch: str,
    commit_sha: str,
    git_provider: str,
    pr_title: str | None = None,
    pr_author: str | None = None,
    pr_url: str | None = None,
) -> PreviewEnvironment:
    """Create or update a preview environment for a PR.

    If a preview already exists for this PR, it updates the commit and
    triggers a new build. Otherwise creates a new preview environment.
    """
    # Check for existing preview
    existing = (
        db.query(PreviewEnvironment)
        .filter(
            PreviewEnvironment.site_id == site.id,
            PreviewEnvironment.pr_number == pr_number,
            PreviewEnvironment.status != "destroyed",
        )
        .first()
    )

    if existing:
        # Update existing preview with new commit
        existing.commit_sha = commit_sha
        existing.pr_title = pr_title or existing.pr_title
        existing.pr_author = pr_author or existing.pr_author
        existing.status = "building"
        existing.updated_at = datetime.now(timezone.utc)
        preview = existing
    else:
        # Allocate a port for the preview
        port = allocate_port(db, f"preview-{site.id}-pr{pr_number}")

        preview = PreviewEnvironment(
            site_id=site.id,
            tenant_id=site.tenant_id,
            pr_number=pr_number,
            pr_title=pr_title,
            pr_author=pr_author,
            pr_branch=pr_branch,
            pr_url=pr_url,
            git_provider=git_provider,
            commit_sha=commit_sha,
            status="building",
            host_port=port,
            preview_url=f"http://localhost:{port}",
        )
        db.add(preview)

    db.commit()
    db.refresh(preview)

    # Create pipeline run for the preview build
    run = PipelineRun(
        site_id=site.id,
        tenant_id=site.tenant_id,
        trigger="preview",
        git_provider=git_provider,
        git_ref=f"refs/heads/{pr_branch}",
        commit_sha=commit_sha,
        status="pending",
        triggered_by=f"preview:pr-{pr_number}",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    preview.pipeline_run_id = run.id
    db.commit()

    # Enqueue the pipeline
    try:
        pool = await _get_arq_pool()
        await pool.enqueue_job("run_pipeline", str(run.id))
        logger.info(
            f"Preview pipeline {run.id} enqueued for PR #{pr_number} on {site.slug}"
        )
    except Exception as e:
        run.status = "failed"
        preview.status = "error"
        db.commit()
        logger.error(f"Failed to enqueue preview pipeline: {e}")

    return preview


async def destroy_preview(
    db: Session,
    preview: PreviewEnvironment,
    reason: str = "manual",
) -> None:
    """Destroy a preview environment — stop container and clean up."""
    import docker

    if preview.container_id:
        try:
            client = docker.from_env()
            container = client.containers.get(preview.container_id)
            container.stop(timeout=10)
            container.remove(force=True)
            logger.info(f"Preview container {preview.container_id} destroyed")
        except docker.errors.NotFound:
            logger.info(f"Preview container {preview.container_id} already gone")
        except Exception as e:
            logger.error(f"Error destroying preview container: {e}")

    preview.status = "destroyed"
    preview.destroy_reason = reason
    preview.destroyed_at = datetime.now(timezone.utc)
    db.commit()

    logger.info(
        f"Preview PR #{preview.pr_number} on site {preview.site_id} "
        f"destroyed (reason: {reason})"
    )


async def cleanup_stale_previews(db: Session) -> int:
    """Destroy previews that have exceeded their TTL."""
    now = datetime.now(timezone.utc)
    active = (
        db.query(PreviewEnvironment)
        .filter(
            PreviewEnvironment.status.in_(["running", "building", "pending"]),
        )
        .all()
    )

    destroyed = 0
    for preview in active:
        age_hours = (now - preview.created_at).total_seconds() / 3600
        if age_hours > preview.ttl_hours:
            await destroy_preview(db, preview, reason="ttl_expired")
            destroyed += 1

    # Also destroy previews for closed/merged PRs
    closed = (
        db.query(PreviewEnvironment)
        .filter(
            PreviewEnvironment.pr_state.in_(["merged", "closed"]),
            PreviewEnvironment.status != "destroyed",
        )
        .all()
    )
    for preview in closed:
        await destroy_preview(db, preview, reason=f"pr_{preview.pr_state}")
        destroyed += 1

    return destroyed
