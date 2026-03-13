"""Container Manager — orchestrates deployments through DeployTarget implementations."""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.deployment import Deployment
from app.models.site import Site
from app.models.workspace import Workspace
from app.models.tenant import Tenant
from app.services.deploy_target import DeployConfig
from app.services.local_deploy import LocalDeployTarget
from app.services.port_manager import allocate_port

logger = logging.getLogger(__name__)

# Singleton deploy targets
_local_target = LocalDeployTarget()


def _get_target(deploy_target: str):
    if deploy_target == "local":
        return _local_target
    raise ValueError(f"Unsupported deploy target: {deploy_target}")


def _container_name(tenant_slug: str, workspace_slug: str, site_slug: str) -> str:
    return f"ae-{tenant_slug}-{workspace_slug}-{site_slug}"


async def deploy_site(db: Session, site_id: str) -> Deployment:
    """Deploy a site: build/pull image, assign port, start container, create deployment record."""
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise ValueError("Site not found")

    workspace = db.query(Workspace).filter(Workspace.id == site.workspace_id).first()
    tenant = db.query(Tenant).filter(Tenant.id == site.tenant_id).first()

    # Auto-assign host port if not set
    if not site.host_port:
        site.host_port = allocate_port(db, str(site.id))
        db.flush()

    # Build runtime env: site vars + workspace Adhara Web vars (site vars take precedence)
    runtime_env = {}
    if workspace.adhara_api_url:
        runtime_env["ADHARA_API_URL"] = workspace.adhara_api_url
    if workspace.adhara_api_key:
        runtime_env["ADHARA_API_KEY"] = workspace.adhara_api_key
    runtime_env["ADHARA_PUBLIC_URL"] = f"http://localhost:{site.host_port}"
    # Site-level env vars override workspace defaults
    runtime_env.update(site.runtime_env or {})

    # Determine next version
    last_deploy = (
        db.query(Deployment)
        .filter(Deployment.site_id == site_id)
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
        container_port=site.container_port,
        host_port=site.host_port,
        status="building",
    )
    db.add(deployment)
    site.status = "building"
    db.commit()
    db.refresh(deployment)

    # Build deploy config
    config = DeployConfig(
        site_id=str(site.id),
        site_slug=site.slug,
        tenant_slug=tenant.slug,
        workspace_slug=workspace.slug,
        image_tag=site.source_url if site.source_type in ("docker_image", "docker_registry") else None,
        source_type=site.source_type,
        source_url=site.source_url,
        dockerfile_path=site.dockerfile_path or "Dockerfile",
        build_command=site.build_command,
        container_port=site.container_port,
        host_port=site.host_port,
        runtime_env=runtime_env,
        build_env=dict(site.build_env or {}),
        health_check_path=site.health_check_path,
        custom_domains=site.custom_domains or [],
    )

    # Execute deployment
    target = _get_target(site.deploy_target)
    deployment.status = "deploying"
    db.commit()

    result = await target.deploy(config)

    # Update records
    if result.success:
        deployment.status = "live"
        deployment.image_tag = result.image_tag
        deployment.deployed_at = datetime.now(timezone.utc)
        deployment.build_logs = result.logs
        site.status = "running"
        site.current_deployment_id = deployment.id
        logger.info(f"Site {site.slug} deployed successfully on port {result.host_port}")
    else:
        deployment.status = "failed"
        deployment.build_logs = result.logs
        deployment.deploy_logs = result.error
        site.status = "error"
        logger.error(f"Site {site.slug} deploy failed: {result.error}")

    db.commit()
    db.refresh(deployment)
    return deployment


async def stop_site(db: Session, site_id: str) -> None:
    """Stop a running site's container."""
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise ValueError("Site not found")

    workspace = db.query(Workspace).filter(Workspace.id == site.workspace_id).first()
    tenant = db.query(Tenant).filter(Tenant.id == site.tenant_id).first()
    name = _container_name(tenant.slug, workspace.slug, site.slug)

    target = _get_target(site.deploy_target)
    await target.stop(name)

    site.status = "stopped"
    db.commit()


async def restart_site(db: Session, site_id: str) -> None:
    """Restart a site by redeploying (picks up latest env vars).

    deploy_site() internally calls _cleanup_existing() which stops and
    removes the old container before creating a new one, so we don't
    need to stop separately (doing so leaves a stopped container whose
    port binding can race with the new container).
    """
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise ValueError("Site not found")

    await deploy_site(db, site_id)


async def get_site_logs(db: Session, site_id: str, tail: int = 100):
    """Get logs from a site's container."""
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise ValueError("Site not found")

    workspace = db.query(Workspace).filter(Workspace.id == site.workspace_id).first()
    tenant = db.query(Tenant).filter(Tenant.id == site.tenant_id).first()
    name = _container_name(tenant.slug, workspace.slug, site.slug)

    target = _get_target(site.deploy_target)
    lines = []
    async for line in target.logs(name, follow=False, tail=tail):
        lines.append(line)
    return lines


async def get_site_status(db: Session, site_id: str) -> dict:
    """Get container status for a site and sync DB if state drifted."""
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise ValueError("Site not found")

    workspace = db.query(Workspace).filter(Workspace.id == site.workspace_id).first()
    tenant = db.query(Tenant).filter(Tenant.id == site.tenant_id).first()
    name = _container_name(tenant.slug, workspace.slug, site.slug)

    target = _get_target(site.deploy_target)
    status = await target.status(name)

    # Sync DB status with actual container state
    _sync_site_status(db, site, status.get("status", "not_found"))

    return status


def _sync_site_status(db: Session, site: Site, container_status: str) -> None:
    """Update site.status in DB to match actual container state if they diverged."""
    # Map Docker container statuses to site statuses
    if container_status in ("running",):
        expected_db = "running"
    elif container_status in ("not_found", "exited", "dead", "removing"):
        expected_db = "stopped"
    elif container_status in ("created", "restarting"):
        expected_db = "deploying"
    elif container_status in ("paused",):
        expected_db = "stopped"
    else:
        return  # Unknown status, don't touch

    # Only correct drift — don't override transitional states like "building"/"deploying"
    if site.status in ("building", "deploying"):
        return

    if site.status != expected_db:
        logger.info(f"Status drift: site {site.slug} DB={site.status} Docker={container_status} → setting {expected_db}")
        site.status = expected_db
        db.commit()


async def sync_all_sites(db: Session) -> dict:
    """Sync all site statuses with actual container state. Run on API startup."""
    sites = db.query(Site).all()
    synced = 0
    for site in sites:
        if site.status in ("building", "deploying"):
            continue  # Don't interrupt active deployments

        workspace = db.query(Workspace).filter(Workspace.id == site.workspace_id).first()
        tenant = db.query(Tenant).filter(Tenant.id == site.tenant_id).first()
        if not workspace or not tenant:
            continue

        name = _container_name(tenant.slug, workspace.slug, site.slug)
        try:
            target = _get_target(site.deploy_target)
            status = await target.status(name)
            old_status = site.status
            _sync_site_status(db, site, status.get("status", "not_found"))
            if site.status != old_status:
                synced += 1
        except Exception as e:
            logger.warning(f"Failed to sync status for site {site.slug}: {e}")

    return {"total": len(sites), "synced": synced}
