"""
Docker Registry browser endpoints with RBAC authorization.

Endpoints:
  GET    /api/v1/registry                        — List all repos filtered by user's site access
  GET    /api/v1/registry/health                  — Registry health and storage stats
  GET    /api/v1/registry/{repository}            — Get tags with metadata for a single repo
  DELETE /api/v1/registry/{repository}            — Delete an entire repo (all tags)
  DELETE /api/v1/registry/{repository}/tags/{tag} — Delete a specific tag

Repos in the registry follow the naming convention `ae-{site_slug}`.
Each repo is mapped back to a Site record for authorization.

Authorization:
  - platform_admin users see everything (single platform-level membership check)
  - All other users see only repos for sites where they have SITE_VIEW permission

Registry URL: http://registry:5000 (Docker network alias)
"""

import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_auth
from app.core.authorize import get_user_memberships
from app.core.database import get_db
from app.core.permissions import ROLE_PERMISSIONS, Permission
from app.models.membership import Membership
from app.models.site import Site
from app.models.tenant import Tenant
from app.models.workspace import Workspace

logger = logging.getLogger(__name__)

router = APIRouter(tags=["registry"])

REGISTRY_BASE = "http://registry:5000"
REGISTRY_TIMEOUT = 10.0


# ── Helpers ───────────────────────────────────────────────────────────


def _is_platform_admin(user: dict, db: Session) -> bool:
    """Return True if the user has a non-expired platform_admin membership."""
    user_id = user["sub"]
    stmt = select(Membership).where(
        Membership.user_id == user_id,
        Membership.resource_type == "platform",
        Membership.role == "platform_admin",
    )
    membership = db.execute(stmt).scalar_one_or_none()
    if membership is None:
        return False
    if membership.expires_at and membership.expires_at < datetime.now(timezone.utc):
        return False
    return True


def _get_authorized_site_slugs(user: dict, db: Session) -> set[str]:
    """
    Return the set of site slugs the user can VIEW, derived from their
    memberships at any level (platform, tenant, workspace, site).
    """
    user_id = user["sub"]
    all_memberships = get_user_memberships(db, user_id)

    site_view_roles: set[str] = {
        role
        for role, perms in ROLE_PERMISSIONS.items()
        if Permission.SITE_VIEW in perms
    }

    authorized_slugs: set[str] = set()

    for m in all_memberships:
        if m.expires_at and m.expires_at < datetime.now(timezone.utc):
            continue
        if m.role not in site_view_roles:
            continue

        if m.resource_type == "platform":
            all_sites = db.query(Site).all()
            for site in all_sites:
                authorized_slugs.add(site.slug)
        elif m.resource_type == "tenant":
            tenant_sites = (
                db.query(Site).filter(Site.tenant_id == m.resource_id).all()
            )
            for site in tenant_sites:
                authorized_slugs.add(site.slug)
        elif m.resource_type == "workspace":
            ws_sites = (
                db.query(Site).filter(Site.workspace_id == m.resource_id).all()
            )
            for site in ws_sites:
                authorized_slugs.add(site.slug)
        elif m.resource_type == "site":
            site = db.query(Site).filter(Site.id == m.resource_id).first()
            if site:
                authorized_slugs.add(site.slug)

    return authorized_slugs


def _require_repo_access(repository: str, user: dict, db: Session) -> None:
    """Raise 403 if the user cannot access this repository."""
    if _is_platform_admin(user, db):
        return

    if repository.startswith("ae-"):
        site_slug = repository.removeprefix("ae-")
        authorized_slugs = _get_authorized_site_slugs(user, db)
        if site_slug in authorized_slugs:
            return

    raise HTTPException(
        status_code=403,
        detail="You don't have permission to access this repository",
    )


async def _fetch_catalog(client: httpx.AsyncClient) -> list[str]:
    """Fetch the full repository catalog from the registry."""
    resp = await client.get(f"{REGISTRY_BASE}/v2/_catalog")
    resp.raise_for_status()
    data = resp.json()
    return data.get("repositories", [])


async def _fetch_tags(client: httpx.AsyncClient, repository: str) -> list[str]:
    """Fetch tags for a single repository from the registry."""
    resp = await client.get(f"{REGISTRY_BASE}/v2/{repository}/tags/list")
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    data = resp.json()
    return data.get("tags") or []


async def _fetch_manifest(
    client: httpx.AsyncClient, repository: str, tag: str
) -> dict | None:
    """Fetch the manifest for a specific tag and extract metadata."""
    # Get the V2 manifest for size info
    headers = {"Accept": "application/vnd.docker.distribution.manifest.v2+json"}
    resp = await client.get(
        f"{REGISTRY_BASE}/v2/{repository}/manifests/{tag}",
        headers=headers,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()

    manifest = resp.json()
    digest = resp.headers.get("Docker-Content-Digest", "")

    # Sum layer sizes
    layers = manifest.get("layers", [])
    total_size = sum(layer.get("size", 0) for layer in layers)
    config_size = manifest.get("config", {}).get("size", 0)
    total_size += config_size

    # Try to get creation date from config blob
    created = None
    config_digest = manifest.get("config", {}).get("digest")
    if config_digest:
        try:
            config_resp = await client.get(
                f"{REGISTRY_BASE}/v2/{repository}/blobs/{config_digest}"
            )
            if config_resp.status_code == 200:
                config_data = config_resp.json()
                created = config_data.get("created")
                arch = config_data.get("architecture", "")
                os_name = config_data.get("os", "")
            else:
                arch = ""
                os_name = ""
        except Exception:
            arch = ""
            os_name = ""
    else:
        arch = ""
        os_name = ""

    return {
        "tag": tag,
        "digest": digest,
        "size": total_size,
        "created": created,
        "architecture": f"{os_name}/{arch}" if os_name and arch else arch or None,
        "layers": len(layers),
    }


async def _delete_tag(
    client: httpx.AsyncClient, repository: str, tag: str
) -> bool:
    """Delete a tag from the registry by deleting its manifest digest."""
    # First get the manifest to obtain the digest
    headers = {"Accept": "application/vnd.docker.distribution.manifest.v2+json"}
    resp = await client.get(
        f"{REGISTRY_BASE}/v2/{repository}/manifests/{tag}",
        headers=headers,
    )
    if resp.status_code == 404:
        return False
    resp.raise_for_status()

    digest = resp.headers.get("Docker-Content-Digest")
    if not digest:
        return False

    # Delete by digest
    del_resp = await client.delete(
        f"{REGISTRY_BASE}/v2/{repository}/manifests/{digest}"
    )
    return del_resp.status_code == 202


def _build_repo_metadata(repository: str, db: Session) -> dict:
    """
    Given a repository name (e.g. ae-my-site), look up the corresponding
    Site record and return enriched metadata fields.
    """
    site_slug = repository.removeprefix("ae-") if repository.startswith("ae-") else None
    if not site_slug:
        return {}

    row = (
        db.query(Site, Workspace.slug, Tenant.slug)
        .join(Workspace, Site.workspace_id == Workspace.id)
        .join(Tenant, Site.tenant_id == Tenant.id)
        .filter(Site.slug == site_slug)
        .first()
    )
    if row is None:
        return {}

    site, workspace_slug, tenant_slug = row
    return {
        "site_id": str(site.id),
        "site_name": site.name,
        "site_slug": site.slug,
        "tenant_slug": tenant_slug,
        "workspace_slug": workspace_slug,
    }


# ── Response Models ──────────────────────────────────────────────────


class TagDetail(BaseModel):
    tag: str
    digest: str
    size: int
    created: str | None = None
    architecture: str | None = None
    layers: int = 0


class RepoDetail(BaseModel):
    repository: str
    tags: list[str]
    tag_details: list[TagDetail] = []
    site_id: str | None = None
    site_name: str | None = None
    site_slug: str | None = None
    tenant_slug: str | None = None
    workspace_slug: str | None = None


class RegistryHealth(BaseModel):
    reachable: bool
    repository_count: int = 0
    total_tags: int = 0
    error: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────────


@router.get("/api/v1/registry/health", response_model=RegistryHealth)
async def registry_health(user: dict = Depends(require_auth)):
    """Check registry health and return basic stats."""
    try:
        async with httpx.AsyncClient(timeout=REGISTRY_TIMEOUT) as client:
            resp = await client.get(f"{REGISTRY_BASE}/v2/")
            reachable = resp.status_code == 200

            repos: list[str] = []
            total_tags = 0
            if reachable:
                repos = await _fetch_catalog(client)
                for repo in repos:
                    tags = await _fetch_tags(client, repo)
                    total_tags += len(tags)

            return RegistryHealth(
                reachable=reachable,
                repository_count=len(repos),
                total_tags=total_tags,
            )
    except Exception as exc:
        return RegistryHealth(reachable=False, error=str(exc))


@router.get("/api/v1/registry")
async def list_registry(
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """List all Docker repositories visible to the authenticated user.

    Returns a list of objects with shape:
      { repository, tags[], site_id?, site_name?, site_slug?,
        tenant_slug?, workspace_slug? }
    """
    is_admin = _is_platform_admin(user, db)

    authorized_slugs: set[str] | None = None
    if not is_admin:
        authorized_slugs = _get_authorized_site_slugs(user, db)

    try:
        async with httpx.AsyncClient(timeout=REGISTRY_TIMEOUT) as client:
            repositories = await _fetch_catalog(client)

            results = []
            for repo in repositories:
                if not is_admin:
                    slug = repo.removeprefix("ae-") if repo.startswith("ae-") else None
                    if slug is None or slug not in authorized_slugs:
                        continue

                tags = await _fetch_tags(client, repo)
                entry: dict = {"repository": repo, "tags": tags}
                entry.update(_build_repo_metadata(repo, db))
                results.append(entry)

            return {"repositories": results}

    except httpx.ConnectError:
        logger.warning("Docker registry unreachable at %s", REGISTRY_BASE)
        return {"repositories": [], "error": "Docker registry is unreachable"}
    except httpx.HTTPStatusError as exc:
        logger.error("Registry catalog request failed: %s", exc)
        return {"repositories": [], "error": "Registry returned an unexpected error"}
    except Exception as exc:
        logger.error("Unexpected error querying registry: %s", exc)
        return {"repositories": [], "error": str(exc)}


@router.get("/api/v1/registry/{repository:path}/detail", response_model=RepoDetail)
async def get_registry_repo_detail(
    repository: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get detailed tag metadata for a repository.

    Returns tags with digest, size, creation date, and architecture.
    """
    _require_repo_access(repository, user, db)

    try:
        async with httpx.AsyncClient(timeout=REGISTRY_TIMEOUT) as client:
            tags = await _fetch_tags(client, repository)

            # Fetch metadata for each tag
            tag_details: list[dict] = []
            for tag in tags:
                detail = await _fetch_manifest(client, repository, tag)
                if detail:
                    tag_details.append(detail)

            meta = _build_repo_metadata(repository, db)
            return RepoDetail(
                repository=repository,
                tags=tags,
                tag_details=[TagDetail(**d) for d in tag_details],
                **meta,
            )

    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Docker registry is unreachable")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Repository '{repository}' not found")
        raise HTTPException(status_code=502, detail="Registry returned an unexpected error")


@router.get("/api/v1/registry/{repository:path}")
async def get_registry_repo(
    repository: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get tags and metadata for a single Docker repository (lightweight)."""
    _require_repo_access(repository, user, db)

    try:
        async with httpx.AsyncClient(timeout=REGISTRY_TIMEOUT) as client:
            tags = await _fetch_tags(client, repository)
            entry: dict = {"repository": repository, "tags": tags}
            entry.update(_build_repo_metadata(repository, db))
            return entry

    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Docker registry is unreachable")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Repository '{repository}' not found")
        raise HTTPException(status_code=502, detail="Registry returned an unexpected error")


@router.delete("/api/v1/registry/{repository:path}/tags/{tag}")
async def delete_registry_tag(
    repository: str,
    tag: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Delete a specific tag from a repository.

    Requires platform_admin or site-level access with appropriate permissions.
    """
    _require_repo_access(repository, user, db)

    try:
        async with httpx.AsyncClient(timeout=REGISTRY_TIMEOUT) as client:
            deleted = await _delete_tag(client, repository, tag)
            if not deleted:
                raise HTTPException(
                    status_code=404,
                    detail=f"Tag '{tag}' not found in repository '{repository}'",
                )
            return {"status": "deleted", "repository": repository, "tag": tag}

    except HTTPException:
        raise
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Docker registry is unreachable")
    except Exception as exc:
        logger.error("Error deleting tag %s/%s: %s", repository, tag, exc)
        raise HTTPException(status_code=500, detail="Failed to delete tag")


@router.delete("/api/v1/registry/{repository:path}")
async def delete_registry_repo(
    repository: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Delete all tags from a repository.

    Requires platform_admin or site-level access.
    """
    _require_repo_access(repository, user, db)

    try:
        async with httpx.AsyncClient(timeout=REGISTRY_TIMEOUT) as client:
            tags = await _fetch_tags(client, repository)
            deleted_count = 0
            errors: list[str] = []

            for tag in tags:
                try:
                    success = await _delete_tag(client, repository, tag)
                    if success:
                        deleted_count += 1
                    else:
                        errors.append(f"Failed to delete {tag}")
                except Exception as exc:
                    errors.append(f"{tag}: {exc}")

            return {
                "status": "deleted",
                "repository": repository,
                "deleted_tags": deleted_count,
                "errors": errors if errors else None,
            }

    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Docker registry is unreachable")
    except Exception as exc:
        logger.error("Error deleting repo %s: %s", repository, exc)
        raise HTTPException(status_code=500, detail="Failed to delete repository")
