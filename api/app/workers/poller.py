"""
Git polling fallback — ARQ cron job that checks for new commits.

For sites with auto_deploy=True that don't use webhooks, this poller
runs `git ls-remote` every 60 seconds to detect new commits on the
watched branch.

This is a fallback — webhooks are preferred for lower latency.
The poller is useful for:
  - Self-hosted GitLab instances behind firewalls
  - Repos where you can't configure webhooks
  - Disaster recovery if webhooks stop firing
"""

import asyncio
import logging

from app.core.database import SessionLocal
from app.models.pipeline import PipelineRun
from app.models.site import Site

logger = logging.getLogger(__name__)


async def poll_git_repos(ctx: dict) -> dict:
    """ARQ cron: poll auto_deploy sites for new commits.

    Runs every 60 seconds. For each site with auto_deploy=True and
    source_type=git_repo, does `git ls-remote` to get the latest SHA
    on the watched branch. If it differs from last_deployed_sha,
    enqueues a pipeline.
    """
    db = SessionLocal()
    results = {"polled": 0, "triggered": 0, "errors": 0}

    try:
        sites = (
            db.query(Site)
            .filter(
                Site.auto_deploy.is_(True),
                Site.source_type == "git_repo",
                Site.source_url.isnot(None),
            )
            .all()
        )

        for site in sites:
            try:
                result = await _poll_site(db, site, ctx)
                results["polled"] += 1
                if result:
                    results["triggered"] += 1
            except Exception as e:
                results["errors"] += 1
                logger.warning(f"Poll error for {site.slug}: {e}")

        return results

    finally:
        db.close()


async def _poll_site(db, site: Site, ctx: dict) -> bool:
    """Poll a single site for new commits. Returns True if pipeline enqueued."""
    branch = site.git_branch or "main"

    # Build clone URL with credentials if available
    remote_url = site.source_url
    if site.git_token and remote_url and remote_url.startswith("https://"):
        username = site.git_token_username or "oauth2"
        remote_url = remote_url.replace(
            "https://",
            f"https://{username}:{site.git_token}@",
        )

    # Run git ls-remote to get the latest SHA
    proc = await asyncio.create_subprocess_exec(
        "git", "ls-remote", remote_url, f"refs/heads/{branch}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        error = stderr.decode().strip()
        # Sanitize credentials
        if site.git_token:
            error = error.replace(site.git_token, "***")
        logger.warning(f"git ls-remote failed for {site.slug}: {error}")
        return False

    # Parse output: "<sha>\trefs/heads/<branch>"
    output = stdout.decode().strip()
    if not output:
        logger.debug(f"No refs found for {site.slug} branch {branch}")
        return False

    remote_sha = output.split("\t")[0]

    # Compare with last deployed SHA
    if remote_sha == site.last_deployed_sha:
        return False  # No new commits

    logger.info(
        f"New commit detected for {site.slug}: "
        f"{(site.last_deployed_sha or 'none')[:8]} -> {remote_sha[:8]}"
    )

    # Check if there's already a pending/running pipeline for this SHA
    existing = (
        db.query(PipelineRun)
        .filter(
            PipelineRun.site_id == site.id,
            PipelineRun.commit_sha == remote_sha,
            PipelineRun.status.in_(["pending", "running"]),
        )
        .first()
    )
    if existing:
        logger.debug(f"Pipeline already running for {site.slug}@{remote_sha[:8]}")
        return False

    # Create pipeline run
    run = PipelineRun(
        site_id=site.id,
        tenant_id=site.tenant_id,
        trigger="polling",
        git_provider=site.git_provider,
        git_ref=f"refs/heads/{branch}",
        commit_sha=remote_sha,
        status="pending",
        triggered_by="poller",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Enqueue via ARQ
    try:
        from arq import ArqRedis
        redis: ArqRedis = ctx.get("redis")
        if redis:
            await redis.enqueue_job("run_pipeline", str(run.id))
            logger.info(f"Poller pipeline {run.id} enqueued for {site.slug}")
            return True
        else:
            logger.error("No Redis connection in worker context for poller")
            run.status = "failed"
            db.commit()
            return False
    except Exception as e:
        logger.error(f"Failed to enqueue poller pipeline for {site.slug}: {e}")
        run.status = "failed"
        db.commit()
        return False
