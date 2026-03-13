"""
Membership CRUD endpoints for hierarchical RBAC.

Manages user-to-resource role assignments at three levels:
  - Tenant:    /api/v1/tenants/{id}/members
  - Workspace: /api/v1/workspaces/{id}/members
  - Site:      /api/v1/sites/{id}/members

Each endpoint validates that the role is valid for the resource type
and that the granting user has manage_members permission.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import require_auth
from app.core.authorize import authorize
from app.core.database import get_db
from app.core.permissions import VALID_ROLES, Permission
from app.models.membership import Membership
from app.schemas.membership import (
    MembershipCreate,
    MembershipResponse,
    MembershipUpdate,
)

router = APIRouter(tags=["members"])


# ── Tenant Members ───────────────────────────────────────────────────


@router.get(
    "/api/v1/tenants/{tenant_id}/members",
    response_model=list[MembershipResponse],
)
async def list_tenant_members(
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """List all members of a tenant."""
    await authorize(user, Permission.TENANT_VIEW, "tenant", tenant_id, db)
    return (
        db.query(Membership)
        .filter(
            Membership.resource_type == "tenant",
            Membership.resource_id == tenant_id,
        )
        .order_by(Membership.granted_at.desc())
        .all()
    )


@router.post(
    "/api/v1/tenants/{tenant_id}/members",
    response_model=MembershipResponse,
    status_code=201,
)
async def add_tenant_member(
    tenant_id: uuid.UUID,
    data: MembershipCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Add a member to a tenant."""
    await authorize(user, Permission.TENANT_MANAGE_MEMBERS, "tenant", tenant_id, db)
    return _create_membership(db, "tenant", tenant_id, data, user)


@router.patch(
    "/api/v1/tenants/{tenant_id}/members/{user_id}",
    response_model=MembershipResponse,
)
async def update_tenant_member(
    tenant_id: uuid.UUID,
    user_id: str,
    data: MembershipUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Update a tenant member's role."""
    await authorize(user, Permission.TENANT_MANAGE_MEMBERS, "tenant", tenant_id, db)
    return _update_membership(db, "tenant", tenant_id, user_id, data)


@router.delete(
    "/api/v1/tenants/{tenant_id}/members/{user_id}",
    status_code=204,
)
async def remove_tenant_member(
    tenant_id: uuid.UUID,
    user_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Remove a member from a tenant. Also removes their workspace and site memberships under this tenant."""
    await authorize(user, Permission.TENANT_MANAGE_MEMBERS, "tenant", tenant_id, db)
    _remove_membership_cascade(db, "tenant", tenant_id, user_id)


# ── Workspace Members ───────────────────────────────────────────────


@router.get(
    "/api/v1/workspaces/{workspace_id}/members",
    response_model=list[MembershipResponse],
)
async def list_workspace_members(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """List all members of a workspace."""
    await authorize(user, Permission.WORKSPACE_VIEW, "workspace", workspace_id, db)
    return (
        db.query(Membership)
        .filter(
            Membership.resource_type == "workspace",
            Membership.resource_id == workspace_id,
        )
        .order_by(Membership.granted_at.desc())
        .all()
    )


@router.post(
    "/api/v1/workspaces/{workspace_id}/members",
    response_model=MembershipResponse,
    status_code=201,
)
async def add_workspace_member(
    workspace_id: uuid.UUID,
    data: MembershipCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Add a member to a workspace."""
    await authorize(
        user, Permission.WORKSPACE_MANAGE_MEMBERS, "workspace", workspace_id, db
    )
    return _create_membership(db, "workspace", workspace_id, data, user)


@router.patch(
    "/api/v1/workspaces/{workspace_id}/members/{user_id}",
    response_model=MembershipResponse,
)
async def update_workspace_member(
    workspace_id: uuid.UUID,
    user_id: str,
    data: MembershipUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Update a workspace member's role."""
    await authorize(
        user, Permission.WORKSPACE_MANAGE_MEMBERS, "workspace", workspace_id, db
    )
    return _update_membership(db, "workspace", workspace_id, user_id, data)


@router.delete(
    "/api/v1/workspaces/{workspace_id}/members/{user_id}",
    status_code=204,
)
async def remove_workspace_member(
    workspace_id: uuid.UUID,
    user_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Remove a member from a workspace. Also removes their site memberships under this workspace."""
    await authorize(
        user, Permission.WORKSPACE_MANAGE_MEMBERS, "workspace", workspace_id, db
    )
    _remove_membership_cascade(db, "workspace", workspace_id, user_id)


# ── Site Members ─────────────────────────────────────────────────────


@router.get(
    "/api/v1/sites/{site_id}/members",
    response_model=list[MembershipResponse],
)
async def list_site_members(
    site_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """List all members of a site."""
    await authorize(user, Permission.SITE_VIEW, "site", site_id, db)
    return (
        db.query(Membership)
        .filter(
            Membership.resource_type == "site",
            Membership.resource_id == site_id,
        )
        .order_by(Membership.granted_at.desc())
        .all()
    )


@router.post(
    "/api/v1/sites/{site_id}/members",
    response_model=MembershipResponse,
    status_code=201,
)
async def add_site_member(
    site_id: uuid.UUID,
    data: MembershipCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Add a member to a site."""
    await authorize(user, Permission.SITE_UPDATE, "site", site_id, db)
    return _create_membership(db, "site", site_id, data, user)


@router.patch(
    "/api/v1/sites/{site_id}/members/{user_id}",
    response_model=MembershipResponse,
)
async def update_site_member(
    site_id: uuid.UUID,
    user_id: str,
    data: MembershipUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Update a site member's role."""
    await authorize(user, Permission.SITE_UPDATE, "site", site_id, db)
    return _update_membership(db, "site", site_id, user_id, data)


@router.delete(
    "/api/v1/sites/{site_id}/members/{user_id}",
    status_code=204,
)
async def remove_site_member(
    site_id: uuid.UUID,
    user_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Remove a member from a site."""
    await authorize(user, Permission.SITE_UPDATE, "site", site_id, db)
    _remove_membership(db, "site", site_id, user_id)


# ── Shared helpers ───────────────────────────────────────────────────


def _create_membership(
    db: Session,
    resource_type: str,
    resource_id: uuid.UUID,
    data: MembershipCreate,
    granting_user: dict,
) -> Membership:
    """Create a membership, validating role for resource type."""
    valid = VALID_ROLES.get(resource_type, [])
    if data.role not in valid:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid role '{data.role}' for {resource_type}. Valid: {valid}",
        )

    # Check for duplicate
    existing = (
        db.query(Membership)
        .filter(
            Membership.user_id == data.user_id,
            Membership.resource_type == resource_type,
            Membership.resource_id == resource_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"User {data.user_id} already has a membership on this {resource_type}",
        )

    membership = Membership(
        user_id=data.user_id,
        user_email=data.user_email,
        resource_type=resource_type,
        resource_id=resource_id,
        role=data.role,
        granted_by=granting_user.get("sub"),
        expires_at=data.expires_at,
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


def _update_membership(
    db: Session,
    resource_type: str,
    resource_id: uuid.UUID,
    user_id: str,
    data: MembershipUpdate,
) -> Membership:
    """Update a membership's role or expiry."""
    membership = (
        db.query(Membership)
        .filter(
            Membership.user_id == user_id,
            Membership.resource_type == resource_type,
            Membership.resource_id == resource_id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")

    if data.role is not None:
        valid = VALID_ROLES.get(resource_type, [])
        if data.role not in valid:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid role '{data.role}' for {resource_type}. Valid: {valid}",
            )
        membership.role = data.role

    if data.expires_at is not None:
        membership.expires_at = data.expires_at

    db.commit()
    db.refresh(membership)
    return membership


def _remove_membership(
    db: Session,
    resource_type: str,
    resource_id: uuid.UUID,
    user_id: str,
):
    """Remove a single membership."""
    membership = (
        db.query(Membership)
        .filter(
            Membership.user_id == user_id,
            Membership.resource_type == resource_type,
            Membership.resource_id == resource_id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")
    db.delete(membership)
    db.commit()


def _remove_membership_cascade(
    db: Session,
    resource_type: str,
    resource_id: uuid.UUID,
    user_id: str,
):
    """Remove a membership and cascade to child resources.

    When removing from tenant: also remove workspace + site memberships
    When removing from workspace: also remove site memberships
    """
    _remove_membership(db, resource_type, resource_id, user_id)

    if resource_type == "tenant":
        # Remove all workspace memberships under this tenant
        from app.models.workspace import Workspace

        workspace_ids = [
            w.id
            for w in db.query(Workspace)
            .filter(Workspace.tenant_id == resource_id)
            .all()
        ]
        for ws_id in workspace_ids:
            m = (
                db.query(Membership)
                .filter(
                    Membership.user_id == user_id,
                    Membership.resource_type == "workspace",
                    Membership.resource_id == ws_id,
                )
                .first()
            )
            if m:
                db.delete(m)

        # Remove all site memberships under this tenant
        from app.models.site import Site

        site_ids = [
            s.id
            for s in db.query(Site).filter(Site.tenant_id == resource_id).all()
        ]
        for s_id in site_ids:
            m = (
                db.query(Membership)
                .filter(
                    Membership.user_id == user_id,
                    Membership.resource_type == "site",
                    Membership.resource_id == s_id,
                )
                .first()
            )
            if m:
                db.delete(m)

        db.commit()

    elif resource_type == "workspace":
        # Remove all site memberships under this workspace
        from app.models.site import Site

        site_ids = [
            s.id
            for s in db.query(Site)
            .filter(Site.workspace_id == resource_id)
            .all()
        ]
        for s_id in site_ids:
            m = (
                db.query(Membership)
                .filter(
                    Membership.user_id == user_id,
                    Membership.resource_type == "site",
                    Membership.resource_id == s_id,
                )
                .first()
            )
            if m:
                db.delete(m)

        db.commit()
