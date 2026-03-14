"""
Authorization engine for Adhara Engine RBAC.

The authorize() function is the single entry point for all permission
checks. It walks UP the resource hierarchy (site -> workspace -> tenant
-> platform) looking for a Membership that grants the requested permission.

Usage:
    await authorize(user, Permission.SITE_DEPLOY, "site", site_id, db)

Hierarchy walk example for a site:
  1. Check: does user have a site-level membership on this site?
  2. Check: does user have a workspace-level membership on the parent workspace?
  3. Check: does user have a tenant-level membership on the parent tenant?
  4. Check: does user have a platform-level membership?
  First match wins (most specific role takes precedence).

Instant revocation:
  Because we check the memberships table on every request (not JWT claims),
  deleting a Membership row takes effect immediately.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import ROLE_PERMISSIONS, Permission
from app.models.membership import Membership
from app.models.site import Site
from app.models.workspace import Workspace


def _flatten_token_scopes(token_scopes: list) -> set[Permission] | None:
    """Extract Permission set from API token scopes (list of dicts or strings).
    Returns None if wildcard '*' is present (meaning all permissions granted).
    """
    flat_perms: list[str] = []
    for scope in token_scopes:
        if isinstance(scope, dict):
            flat_perms.extend(scope.get("permissions", []))
        elif isinstance(scope, str):
            flat_perms.append(scope)
    # Wildcard means all permissions — don't restrict
    if "*" in flat_perms:
        return None
    return {Permission(s) for s in flat_perms if s in Permission._value2member_map_}


async def authorize(
    user: dict,
    permission: Permission,
    resource_type: str,
    resource_id: uuid.UUID | None,
    db: Session,
) -> Membership | None:
    """
    Check if user has a permission on a resource.
    Walks UP the hierarchy: site -> workspace -> tenant -> platform.
    Returns the matching Membership if authorized.
    Raises 403 if denied.
    """
    user_id = user["sub"]

    # Build the resource chain for hierarchical lookup
    resource_chain = await _build_resource_chain(db, resource_type, resource_id)

    # Check each level — first match wins
    for res_type, res_id in resource_chain:
        membership = _get_membership(db, user_id, res_type, res_id)
        if membership is None:
            continue

        # Check expiry
        if membership.expires_at and membership.expires_at < datetime.now(
            timezone.utc
        ):
            continue  # Expired, check next level

        # Check if role grants the requested permission
        role_perms = ROLE_PERMISSIONS.get(membership.role, set())
        # For API tokens, intersect with token scopes
        if user.get("token_type") == "api_token":
            token_scopes = user.get("scopes") or []
            if token_scopes:
                scope_perms = _flatten_token_scopes(token_scopes)
                if scope_perms is not None:  # None = wildcard, no restriction
                    role_perms = role_perms & scope_perms
        if permission in role_perms:
            return membership  # AUTHORIZED

    raise HTTPException(
        status_code=403,
        detail=f"You don't have '{permission.value}' permission on this {resource_type}",
    )


async def authorize_any(
    user: dict,
    permissions: list[Permission],
    resource_type: str,
    resource_id: uuid.UUID | None,
    db: Session,
) -> Membership | None:
    """Check if user has ANY of the listed permissions. Used for OR logic."""
    user_id = user["sub"]
    resource_chain = await _build_resource_chain(db, resource_type, resource_id)

    for res_type, res_id in resource_chain:
        membership = _get_membership(db, user_id, res_type, res_id)
        if membership is None:
            continue
        if membership.expires_at and membership.expires_at < datetime.now(
            timezone.utc
        ):
            continue
        role_perms = ROLE_PERMISSIONS.get(membership.role, set())
        # For API tokens, intersect with token scopes
        if user.get("token_type") == "api_token":
            token_scopes = user.get("scopes") or []
            if token_scopes:
                scope_perms = _flatten_token_scopes(token_scopes)
                if scope_perms is not None:  # None = wildcard, no restriction
                    role_perms = role_perms & scope_perms
        if any(p in role_perms for p in permissions):
            return membership

    raise HTTPException(
        status_code=403,
        detail=f"Insufficient permissions on this {resource_type}",
    )


def get_user_memberships(
    db: Session, user_id: str, resource_type: str | None = None
) -> list[Membership]:
    """Get all memberships for a user, optionally filtered by resource type."""
    stmt = select(Membership).where(Membership.user_id == user_id)
    if resource_type:
        stmt = stmt.where(Membership.resource_type == resource_type)
    return list(db.execute(stmt).scalars().all())


async def _build_resource_chain(
    db: Session, resource_type: str, resource_id: uuid.UUID | None
) -> list[tuple[str, uuid.UUID | None]]:
    """
    Build the hierarchy chain from specific to general.
    Returns list of (resource_type, resource_id) tuples to check.
    """
    chain: list[tuple[str, uuid.UUID | None]] = []

    if resource_type == "site" and resource_id:
        site = db.get(Site, resource_id)
        if site is None:
            raise HTTPException(status_code=404, detail="Site not found")
        chain.append(("site", resource_id))
        chain.append(("workspace", site.workspace_id))
        chain.append(("tenant", site.tenant_id))

    elif resource_type == "workspace" and resource_id:
        workspace = db.get(Workspace, resource_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        chain.append(("workspace", resource_id))
        chain.append(("tenant", workspace.tenant_id))

    elif resource_type == "tenant" and resource_id:
        chain.append(("tenant", resource_id))

    # Always check platform-level last
    chain.append(("platform", None))
    return chain


def _get_membership(
    db: Session, user_id: str, resource_type: str, resource_id: uuid.UUID | None
) -> Membership | None:
    """Look up a single membership for a user on a specific resource."""
    stmt = select(Membership).where(
        Membership.user_id == user_id,
        Membership.resource_type == resource_type,
    )
    if resource_id is not None:
        stmt = stmt.where(Membership.resource_id == resource_id)
    else:
        stmt = stmt.where(Membership.resource_id.is_(None))

    return db.execute(stmt).scalar_one_or_none()
