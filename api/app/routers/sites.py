"""
Site CRUD endpoints with RBAC authorization.

Site operations require:
  - Create: SITE_CREATE (on parent workspace)
  - View/List: SITE_VIEW
  - Update: SITE_UPDATE
  - Delete: SITE_DELETE
  - Env vars: SITE_ENV
  - Ports: SITE_UPDATE
"""

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import require_auth
from app.core.authorize import authorize
from app.core.database import get_db
from app.core.permissions import Permission
from app.core.slugify import slugify
from app.models.site import Site
from app.models.tenant import Tenant
from app.models.workspace import Workspace

logger = logging.getLogger(__name__)
from app.schemas.site import (
    EnvVarBulkSet,
    EnvVarResponse,
    PortUpdate,
    SiteCreate,
    SiteDetailResponse,
    SiteResponse,
    SiteUpdate,
)

router = APIRouter(tags=["sites"])


@router.get("/api/v1/sites")
async def list_all_sites(
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Return all sites the user can see across all tenants/workspaces."""
    await authorize(user, Permission.PLATFORM_DASHBOARD, "platform", None, db)
    rows = (
        db.query(Site, Workspace.slug, Tenant.slug)
        .join(Workspace, Site.workspace_id == Workspace.id)
        .join(Tenant, Site.tenant_id == Tenant.id)
        .order_by(Tenant.name, Workspace.name, Site.name)
        .all()
    )
    return [
        {
            "id": str(site.id),
            "name": site.name,
            "slug": site.slug,
            "status": site.status,
            "host_port": site.host_port,
            "tenant_slug": t_slug,
            "workspace_slug": w_slug,
        }
        for site, w_slug, t_slug in rows
    ]


@router.post(
    "/api/v1/workspaces/{workspace_id}/sites",
    response_model=SiteResponse,
    status_code=201,
)
async def create_site(
    workspace_id: uuid.UUID,
    data: SiteCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    await authorize(user, Permission.SITE_CREATE, "workspace", workspace_id, db)

    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    slug = data.slug or slugify(data.name)
    existing = (
        db.query(Site)
        .filter(Site.workspace_id == workspace_id, Site.slug == slug)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Site with slug '{slug}' already exists in this workspace",
        )

    site = Site(
        workspace_id=workspace_id,
        tenant_id=workspace.tenant_id,
        name=data.name,
        slug=slug,
        source_type=data.source_type,
        source_url=data.source_url,
        dockerfile_path=data.dockerfile_path,
        build_command=data.build_command,
        container_port=data.container_port,
        deploy_target=data.deploy_target,
        deploy_region=data.deploy_region,
        health_check_path=data.health_check_path,
        git_provider=data.git_provider,
        git_branch=data.git_branch,
        auto_deploy=data.auto_deploy,
    )
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@router.get(
    "/api/v1/workspaces/{workspace_id}/sites",
    response_model=list[SiteResponse],
)
async def list_sites(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    await authorize(user, Permission.SITE_VIEW, "workspace", workspace_id, db)
    return (
        db.query(Site)
        .filter(Site.workspace_id == workspace_id)
        .order_by(Site.created_at.desc())
        .all()
    )


@router.get("/api/v1/sites/{site_id}", response_model=SiteDetailResponse)
async def get_site(
    site_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    await authorize(user, Permission.SITE_VIEW, "site", site_id, db)
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.patch("/api/v1/sites/{site_id}", response_model=SiteResponse)
async def update_site(
    site_id: uuid.UUID,
    data: SiteUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    await authorize(user, Permission.SITE_UPDATE, "site", site_id, db)
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    old_slug = site.slug
    updates = data.model_dump(exclude_unset=True)
    slug_changed = "slug" in updates and updates["slug"] != old_slug

    # If slug changes and a container is running, we need to stop+remove
    # the old container (which has the old name) before redeploying with
    # the new container name.  _cleanup_existing does stop+remove.
    if slug_changed and site.status in ("running", "deploying", "error"):
        from app.services.container_manager import _container_name, _get_target
        workspace = db.query(Workspace).filter(Workspace.id == site.workspace_id).first()
        tenant = db.query(Tenant).filter(Tenant.id == site.tenant_id).first()
        old_name = _container_name(tenant.slug, workspace.slug, old_slug)
        target = _get_target(site.deploy_target)
        try:
            await target._cleanup_existing(old_name)
            logger.info(f"Removed old container {old_name} after slug change")
        except Exception:
            pass  # Container may not exist

    for field, value in updates.items():
        setattr(site, field, value)

    db.commit()
    db.refresh(site)

    # Redeploy with new slug if it changed and site was running
    if slug_changed and old_slug != site.slug:
        from app.services.container_manager import deploy_site
        async def _redeploy():
            from app.core.database import SessionLocal
            redb = SessionLocal()
            try:
                await deploy_site(redb, str(site_id))
            except Exception as e:
                logger.error(f"Redeploy after slug change failed: {e}")
            finally:
                redb.close()
        background_tasks.add_task(_redeploy)

    return site


@router.delete("/api/v1/sites/{site_id}", status_code=204)
async def delete_site(
    site_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    await authorize(user, Permission.SITE_DELETE, "site", site_id, db)
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    db.delete(site)
    db.commit()


# ── Environment Variables ────────────────────────────────────────────


@router.get("/api/v1/sites/{site_id}/env", response_model=EnvVarResponse)
async def get_env_vars(
    site_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    await authorize(user, Permission.SITE_ENV, "site", site_id, db)
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return EnvVarResponse(
        runtime_env=site.runtime_env or {},
        build_env=site.build_env or {},
    )


@router.put("/api/v1/sites/{site_id}/env", response_model=EnvVarResponse)
async def set_env_vars(
    site_id: uuid.UUID,
    data: EnvVarBulkSet,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    await authorize(user, Permission.SITE_ENV, "site", site_id, db)
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    runtime_env = dict(site.runtime_env or {})
    build_env = dict(site.build_env or {})
    build_changed = False

    for var in data.vars:
        scope = var.scope
        if scope == "runtime" and var.key.startswith("NEXT_PUBLIC_"):
            scope = "build"

        if scope == "build":
            build_env[var.key] = var.value
            build_changed = True
        else:
            runtime_env[var.key] = var.value

    site.runtime_env = runtime_env
    site.build_env = build_env
    db.commit()
    db.refresh(site)

    warning = None
    if build_changed:
        warning = "Build-time env vars changed. A rebuild is required — run deploy to apply."

    return EnvVarResponse(
        runtime_env=site.runtime_env or {},
        build_env=site.build_env or {},
        warning=warning,
    )


@router.delete("/api/v1/sites/{site_id}/env/{key}", response_model=EnvVarResponse)
async def delete_env_var(
    site_id: uuid.UUID,
    key: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    await authorize(user, Permission.SITE_ENV, "site", site_id, db)
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    runtime_env = dict(site.runtime_env or {})
    build_env = dict(site.build_env or {})
    warning = None

    if key in runtime_env:
        del runtime_env[key]
    elif key in build_env:
        del build_env[key]
        warning = "Build-time env var removed. A rebuild is required — run deploy to apply."
    else:
        raise HTTPException(status_code=404, detail=f"Env var '{key}' not found")

    site.runtime_env = runtime_env
    site.build_env = build_env
    db.commit()
    db.refresh(site)

    return EnvVarResponse(
        runtime_env=site.runtime_env or {},
        build_env=site.build_env or {},
        warning=warning,
    )


# ── Port Management ──────────────────────────────────────────────────


@router.patch("/api/v1/sites/{site_id}/ports", response_model=SiteResponse)
async def update_ports(
    site_id: uuid.UUID,
    data: PortUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    await authorize(user, Permission.SITE_UPDATE, "site", site_id, db)
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    if data.container_port is not None:
        site.container_port = data.container_port
    if data.host_port is not None:
        conflict = (
            db.query(Site)
            .filter(Site.host_port == data.host_port, Site.id != site_id)
            .first()
        )
        if conflict:
            raise HTTPException(
                status_code=409,
                detail=f"Host port {data.host_port} is already in use by site '{conflict.name}'",
            )
        site.host_port = data.host_port

    db.commit()
    db.refresh(site)
    return site


# ── Ports routing table ──────────────────────────────────────────────


@router.get("/api/v1/ports")
async def get_port_table(
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    await authorize(user, Permission.PLATFORM_DASHBOARD, "platform", None, db)
    sites = (
        db.query(Site)
        .filter(Site.host_port.isnot(None))
        .order_by(Site.host_port)
        .all()
    )
    return [
        {
            "site_id": str(s.id),
            "site_name": s.name,
            "site_slug": s.slug,
            "container_port": s.container_port,
            "host_port": s.host_port,
            "status": s.status,
        }
        for s in sites
    ]
