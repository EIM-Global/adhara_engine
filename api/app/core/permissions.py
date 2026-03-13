"""
Permissions and role definitions for Adhara Engine RBAC.

This module defines:
  - Permission enum: 24 fine-grained permissions checked at endpoints
  - ROLE_PERMISSIONS: maps each of 10 roles to their granted permissions
  - Role hierarchy: platform > tenant > workspace > site

Roles are assigned via the Membership model (not JWT claims) so that
revocation is instant — delete the membership row and the next API
call is denied.

Usage at endpoint level:
    from app.core.authorize import authorize
    from app.core.permissions import Permission

    @router.post("/api/v1/sites/{site_id}/deploy")
    async def deploy(site_id: UUID, user=Depends(require_auth), db=Depends(get_db)):
        await authorize(user, Permission.SITE_DEPLOY, "site", site_id, db)
        ...
"""

from enum import Enum


class Permission(str, Enum):
    """Fine-grained permissions checked at the endpoint level."""

    # ── Tenant ───────────────────────────────────────────────
    TENANT_CREATE = "tenant:create"
    TENANT_DELETE = "tenant:delete"
    TENANT_UPDATE = "tenant:update"
    TENANT_VIEW = "tenant:view"
    TENANT_MANAGE_MEMBERS = "tenant:manage_members"

    # ── Workspace ────────────────────────────────────────────
    WORKSPACE_CREATE = "workspace:create"
    WORKSPACE_DELETE = "workspace:delete"
    WORKSPACE_UPDATE = "workspace:update"
    WORKSPACE_VIEW = "workspace:view"
    WORKSPACE_MANAGE_MEMBERS = "workspace:manage_members"

    # ── Site ─────────────────────────────────────────────────
    SITE_CREATE = "site:create"
    SITE_DELETE = "site:delete"
    SITE_UPDATE = "site:update"
    SITE_VIEW = "site:view"
    SITE_DEPLOY = "site:deploy"
    SITE_STOP = "site:stop"
    SITE_RESTART = "site:restart"
    SITE_ROLLBACK = "site:rollback"
    SITE_LOGS = "site:logs"
    SITE_ENV = "site:env"
    SITE_SERVICES = "site:services"
    SITE_GIT_CONFIG = "site:git_config"
    SITE_NOTIFICATIONS = "site:notifications"

    # ── Platform ─────────────────────────────────────────────
    PLATFORM_SETTINGS = "platform:settings"
    PLATFORM_DASHBOARD = "platform:dashboard"


# ── Role -> Permission mappings ──────────────────────────────
# Each role gets a specific set of permissions.
# The authorize() function walks up the resource hierarchy
# (site -> workspace -> tenant -> platform) checking memberships
# at each level.

ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    # ── Platform level ───────────────────────────────────────
    "platform_admin": set(Permission),  # ALL permissions
    "platform_viewer": {
        Permission.TENANT_VIEW,
        Permission.WORKSPACE_VIEW,
        Permission.SITE_VIEW,
        Permission.SITE_LOGS,
        Permission.PLATFORM_DASHBOARD,
    },
    # ── Tenant level ─────────────────────────────────────────
    "tenant_owner": {
        Permission.TENANT_DELETE,
        Permission.TENANT_UPDATE,
        Permission.TENANT_VIEW,
        Permission.TENANT_MANAGE_MEMBERS,
        Permission.WORKSPACE_CREATE,
        Permission.WORKSPACE_DELETE,
        Permission.WORKSPACE_UPDATE,
        Permission.WORKSPACE_VIEW,
        Permission.WORKSPACE_MANAGE_MEMBERS,
        Permission.SITE_CREATE,
        Permission.SITE_DELETE,
        Permission.SITE_UPDATE,
        Permission.SITE_VIEW,
        Permission.SITE_DEPLOY,
        Permission.SITE_STOP,
        Permission.SITE_RESTART,
        Permission.SITE_ROLLBACK,
        Permission.SITE_LOGS,
        Permission.SITE_ENV,
        Permission.SITE_SERVICES,
        Permission.SITE_GIT_CONFIG,
        Permission.SITE_NOTIFICATIONS,
        Permission.PLATFORM_DASHBOARD,
    },
    "tenant_admin": {
        Permission.TENANT_UPDATE,
        Permission.TENANT_VIEW,
        Permission.TENANT_MANAGE_MEMBERS,
        Permission.WORKSPACE_CREATE,
        Permission.WORKSPACE_DELETE,
        Permission.WORKSPACE_UPDATE,
        Permission.WORKSPACE_VIEW,
        Permission.WORKSPACE_MANAGE_MEMBERS,
        Permission.SITE_CREATE,
        Permission.SITE_DELETE,
        Permission.SITE_UPDATE,
        Permission.SITE_VIEW,
        Permission.SITE_DEPLOY,
        Permission.SITE_STOP,
        Permission.SITE_RESTART,
        Permission.SITE_ROLLBACK,
        Permission.SITE_LOGS,
        Permission.SITE_ENV,
        Permission.SITE_SERVICES,
        Permission.SITE_GIT_CONFIG,
        Permission.SITE_NOTIFICATIONS,
        Permission.PLATFORM_DASHBOARD,
    },
    "tenant_member": {
        Permission.TENANT_VIEW,
        Permission.WORKSPACE_VIEW,
        Permission.SITE_VIEW,
        Permission.SITE_LOGS,
    },
    # ── Workspace level ──────────────────────────────────────
    "workspace_admin": {
        Permission.WORKSPACE_DELETE,
        Permission.WORKSPACE_UPDATE,
        Permission.WORKSPACE_VIEW,
        Permission.WORKSPACE_MANAGE_MEMBERS,
        Permission.SITE_CREATE,
        Permission.SITE_DELETE,
        Permission.SITE_UPDATE,
        Permission.SITE_VIEW,
        Permission.SITE_DEPLOY,
        Permission.SITE_STOP,
        Permission.SITE_RESTART,
        Permission.SITE_ROLLBACK,
        Permission.SITE_LOGS,
        Permission.SITE_ENV,
        Permission.SITE_SERVICES,
        Permission.SITE_GIT_CONFIG,
        Permission.SITE_NOTIFICATIONS,
        Permission.PLATFORM_DASHBOARD,
    },
    "workspace_deployer": {
        Permission.WORKSPACE_VIEW,
        Permission.SITE_VIEW,
        Permission.SITE_DEPLOY,
        Permission.SITE_STOP,
        Permission.SITE_RESTART,
        Permission.SITE_ROLLBACK,
        Permission.SITE_LOGS,
        Permission.SITE_ENV,
        Permission.SITE_NOTIFICATIONS,
        Permission.PLATFORM_DASHBOARD,
    },
    "workspace_viewer": {
        Permission.WORKSPACE_VIEW,
        Permission.SITE_VIEW,
        Permission.SITE_LOGS,
        Permission.PLATFORM_DASHBOARD,
    },
    # ── Site level ───────────────────────────────────────────
    "site_admin": {
        Permission.SITE_DELETE,
        Permission.SITE_UPDATE,
        Permission.SITE_VIEW,
        Permission.SITE_DEPLOY,
        Permission.SITE_STOP,
        Permission.SITE_RESTART,
        Permission.SITE_ROLLBACK,
        Permission.SITE_LOGS,
        Permission.SITE_ENV,
        Permission.SITE_SERVICES,
        Permission.SITE_GIT_CONFIG,
        Permission.SITE_NOTIFICATIONS,
    },
    "site_deployer": {
        Permission.SITE_VIEW,
        Permission.SITE_DEPLOY,
        Permission.SITE_STOP,
        Permission.SITE_RESTART,
        Permission.SITE_ROLLBACK,
        Permission.SITE_LOGS,
        Permission.SITE_ENV,
        Permission.SITE_NOTIFICATIONS,
    },
    "site_viewer": {
        Permission.SITE_VIEW,
        Permission.SITE_LOGS,
    },
}


# ── Valid roles per resource type ────────────────────────────
VALID_ROLES: dict[str, list[str]] = {
    "platform": ["platform_admin", "platform_viewer"],
    "tenant": ["tenant_owner", "tenant_admin", "tenant_member"],
    "workspace": ["workspace_admin", "workspace_deployer", "workspace_viewer"],
    "site": ["site_admin", "site_deployer", "site_viewer"],
}
