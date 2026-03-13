"""
Health monitor — ARQ cron job that checks running sites every 30 seconds.

Escalation ladder (based on consecutive failures):
  1-2 failures:  Log warning, record HealthEvent
  3 failures:    Restart container
  5 failures:    Trigger full rebuild (new pipeline)
  8 failures:    Rollback to previous deployment
  10+ failures:  Alert (notification) and stop escalating

The failure count resets to 0 on any successful health check.
"""

import logging
from datetime import datetime, timezone

import httpx

from app.core.database import SessionLocal
from app.models.health_event import HealthEvent
from app.models.site import Site

logger = logging.getLogger(__name__)

# Escalation thresholds
RESTART_THRESHOLD = 3
REBUILD_THRESHOLD = 5
ROLLBACK_THRESHOLD = 8
ALERT_THRESHOLD = 10


async def check_all_sites(ctx: dict) -> dict:
    """ARQ cron: health-check all running sites.

    Called every 30 seconds. Checks each site's health endpoint
    and escalates based on consecutive failure count.
    """
    db = SessionLocal()
    results = {"checked": 0, "healthy": 0, "unhealthy": 0, "actions": []}

    try:
        # Only check sites that are actually running
        sites = (
            db.query(Site)
            .filter(Site.status == "running")
            .filter(Site.host_port.isnot(None))
            .all()
        )

        for site in sites:
            try:
                result = await _check_site(db, site, ctx)
                results["checked"] += 1
                if result["healthy"]:
                    results["healthy"] += 1
                else:
                    results["unhealthy"] += 1
                    if result.get("action"):
                        results["actions"].append(
                            f"{site.slug}: {result['action']}"
                        )
            except Exception as e:
                logger.warning(f"Health check error for {site.slug}: {e}")

        return results

    finally:
        db.close()


async def _check_site(db, site: Site, ctx: dict) -> dict:
    """Check a single site's health endpoint and handle escalation."""
    now = datetime.now(timezone.utc)
    health_url = f"http://localhost:{site.host_port}{site.health_check_path}"

    status_code = None
    response_ms = None
    healthy = False
    action_taken = None

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            start = now.timestamp()
            resp = await client.get(health_url)
            response_ms = int((datetime.now(timezone.utc).timestamp() - start) * 1000)
            status_code = resp.status_code
            healthy = 200 <= status_code < 400

    except httpx.TimeoutException:
        status_code = 0
        response_ms = 5000
        healthy = False
    except httpx.ConnectError:
        status_code = 0
        response_ms = 0
        healthy = False
    except Exception as e:
        logger.warning(f"Health check request failed for {site.slug}: {e}")
        status_code = 0
        response_ms = 0
        healthy = False

    # Update site health state
    site.last_health_check = now

    if healthy:
        # Reset failure count on success
        if site.health_failure_count > 0:
            logger.info(
                f"Site {site.slug} recovered after "
                f"{site.health_failure_count} failures"
            )
        site.health_failure_count = 0
        site.health_status = "healthy"
        site.last_healthy_at = now
    else:
        site.health_failure_count = (site.health_failure_count or 0) + 1
        failures = site.health_failure_count

        # Determine escalation action — only auto-remediate if enabled
        auto_heal = getattr(site, 'health_auto_remediate', False)

        if failures >= ALERT_THRESHOLD:
            site.health_status = "down"
            if auto_heal:
                action_taken = "alert"
                await _escalate_alert(db, site)
            else:
                logger.warning(f"Site {site.slug} is down ({failures} failures) — auto-remediation disabled")
        elif failures >= ROLLBACK_THRESHOLD:
            site.health_status = "down"
            if auto_heal:
                action_taken = "rollback"
                await _escalate_rollback(db, site)
            else:
                logger.warning(f"Site {site.slug} needs rollback ({failures} failures) — auto-remediation disabled")
        elif failures >= REBUILD_THRESHOLD:
            site.health_status = "degraded"
            if auto_heal:
                action_taken = "rebuild"
                await _escalate_rebuild(db, site, ctx)
            else:
                logger.warning(f"Site {site.slug} needs rebuild ({failures} failures) — auto-remediation disabled")
        elif failures >= RESTART_THRESHOLD:
            site.health_status = "degraded"
            if auto_heal:
                action_taken = "restart"
                await _escalate_restart(site)
            else:
                logger.warning(f"Site {site.slug} needs restart ({failures} failures) — auto-remediation disabled")
        else:
            site.health_status = "degraded"
            logger.warning(
                f"Site {site.slug} health check failed "
                f"({failures}/{RESTART_THRESHOLD} before restart)"
            )

    # Record health event
    event = HealthEvent(
        site_id=site.id,
        check_time=now,
        status_code=status_code,
        response_ms=response_ms,
        healthy=healthy,
        action_taken=action_taken,
    )
    db.add(event)
    db.commit()

    return {
        "healthy": healthy,
        "status_code": status_code,
        "response_ms": response_ms,
        "action": action_taken,
    }


async def _escalate_restart(site: Site):
    """Restart the container."""
    import docker
    from docker.errors import NotFound

    logger.warning(f"ESCALATION: Restarting {site.slug} (failures: {site.health_failure_count})")
    try:
        client = docker.from_env()
        if site.active_container_id:
            container = client.containers.get(site.active_container_id)
            container.restart(timeout=10)
        else:
            # Try by name pattern
            containers = client.containers.list(
                filters={"label": f"adhara.site_id={site.id}"}
            )
            if containers:
                containers[0].restart(timeout=10)
    except NotFound:
        logger.error(f"Container not found for restart: {site.slug}")
    except Exception as e:
        logger.error(f"Restart failed for {site.slug}: {e}")


async def _escalate_rebuild(db, site: Site, ctx: dict):
    """Trigger a new pipeline build.

    Only works for git_repo sites — docker_image sites have no source code
    to rebuild from, so we fall back to a container restart instead.
    """
    from arq import ArqRedis

    # For non-git sites, a rebuild makes no sense — fall back to restart
    if site.source_type != "git_repo":
        logger.info(
            f"Skipping rebuild for {site.slug} (source_type={site.source_type}), "
            f"falling back to container restart"
        )
        await _escalate_restart(site)
        return

    logger.warning(f"ESCALATION: Rebuilding {site.slug} (failures: {site.health_failure_count})")

    try:
        from app.models.pipeline import PipelineRun

        # Create a new pipeline run for the rebuild
        run = PipelineRun(
            site_id=site.id,
            tenant_id=site.tenant_id,
            trigger="health_rebuild",
            status="pending",
            triggered_by="health_monitor",
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Enqueue the pipeline job
        redis: ArqRedis = ctx.get("redis")
        if redis:
            await redis.enqueue_job("run_pipeline", str(run.id))
            logger.info(f"Rebuild pipeline {run.id} enqueued for {site.slug}")
        else:
            logger.error("No Redis connection in worker context for rebuild")

    except Exception as e:
        logger.error(f"Rebuild escalation failed for {site.slug}: {e}")


async def _escalate_rollback(db, site: Site):
    """Rollback to the previous successful deployment."""
    from app.models.deployment import Deployment

    logger.warning(f"ESCALATION: Rolling back {site.slug} (failures: {site.health_failure_count})")

    try:
        # Find the previous live deployment (not the current one)
        prev_deploy = (
            db.query(Deployment)
            .filter(
                Deployment.site_id == site.id,
                Deployment.status == "live",
                Deployment.id != site.current_deployment_id,
            )
            .order_by(Deployment.version.desc())
            .first()
        )

        if not prev_deploy or not prev_deploy.image_tag:
            logger.warning(f"No previous deployment to rollback to for {site.slug}")
            return

        logger.info(
            f"Rolling back {site.slug} to v{prev_deploy.version} "
            f"(image: {prev_deploy.image_tag})"
        )

        # Stop current container
        import docker
        client = docker.from_env()
        if site.active_container_id:
            try:
                container = client.containers.get(site.active_container_id)
                container.stop(timeout=10)
                container.remove()
            except Exception:
                pass

        # Re-deploy with the previous image
        # This is a simplified rollback — the full pipeline handles blue-green
        from app.services.local_deploy import LocalDeployTarget, _container_name
        from app.services.deploy_target import DeployConfig
        from app.models.workspace import Workspace
        from app.models.tenant import Tenant

        workspace = db.query(Workspace).filter(Workspace.id == site.workspace_id).first()
        tenant = db.query(Tenant).filter(Tenant.id == site.tenant_id).first()

        config = DeployConfig(
            site_id=str(site.id),
            site_slug=site.slug,
            tenant_slug=tenant.slug,
            workspace_slug=workspace.slug,
            image_tag=prev_deploy.image_tag,
            source_type="docker_image",
            source_url=prev_deploy.image_tag,
            container_port=site.container_port,
            host_port=site.host_port,
            runtime_env=dict(site.runtime_env or {}),
            health_check_path=site.health_check_path,
            custom_domains=site.custom_domains or [],
        )

        target = LocalDeployTarget()
        result = await target.deploy(config)

        if result.success:
            site.current_deployment_id = prev_deploy.id
            site.active_container_id = result.container_id
            site.health_failure_count = 0
            site.health_status = "healthy"
            db.commit()
            logger.info(f"Rollback succeeded for {site.slug}")
        else:
            logger.error(f"Rollback deploy failed for {site.slug}: {result.error}")

    except Exception as e:
        logger.error(f"Rollback failed for {site.slug}: {e}")


async def _escalate_alert(db, site: Site):
    """Send alert notifications."""
    from app.models.notification_config import NotificationConfig

    logger.critical(
        f"ALERT: Site {site.slug} has been down for "
        f"{site.health_failure_count} consecutive checks"
    )

    # Find notification configs for this site
    configs = (
        db.query(NotificationConfig)
        .filter(
            NotificationConfig.site_id == site.id,
            NotificationConfig.enabled.is_(True),
        )
        .all()
    )

    for config in configs:
        events = config.events or []
        if "health_alert" not in events and "all" not in events:
            continue

        try:
            if config.type == "webhook":
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        config.target,
                        json={
                            "event": "health_alert",
                            "site_id": str(site.id),
                            "site_slug": site.slug,
                            "failures": site.health_failure_count,
                            "health_status": site.health_status,
                            "last_healthy_at": (
                                site.last_healthy_at.isoformat()
                                if site.last_healthy_at
                                else None
                            ),
                        },
                    )
                    logger.info(f"Alert webhook sent to {config.target}")

            elif config.type == "slack":
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        config.target,
                        json={
                            "text": (
                                f":rotating_light: *Site Down Alert*\n"
                                f"Site `{site.slug}` has failed "
                                f"{site.health_failure_count} consecutive "
                                f"health checks.\n"
                                f"Status: {site.health_status}\n"
                                f"Last healthy: {site.last_healthy_at or 'Never'}"
                            ),
                        },
                    )
                    logger.info(f"Slack alert sent for {site.slug}")

        except Exception as e:
            logger.error(
                f"Failed to send {config.type} notification for {site.slug}: {e}"
            )
