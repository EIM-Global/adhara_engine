"""Resolve slug paths (tenant/workspace/site) to UUIDs."""

from adhara_engine_cli.client import EngineClient


def resolve_tenant(client: EngineClient, slug: str) -> dict:
    """Find tenant by slug. Returns tenant dict or raises."""
    tenants = client.list_tenants()
    for t in tenants:
        if t["slug"] == slug:
            return t
    raise ValueError(f"Tenant '{slug}' not found")


def resolve_workspace(client: EngineClient, path: str) -> dict:
    """Resolve 'tenant-slug/workspace-slug' to workspace dict."""
    parts = path.split("/")
    if len(parts) != 2:
        raise ValueError(f"Expected 'tenant/workspace', got '{path}'")
    tenant_slug, ws_slug = parts
    tenant = resolve_tenant(client, tenant_slug)
    workspaces = client.list_workspaces(tenant["id"])
    for w in workspaces:
        if w["slug"] == ws_slug:
            return w
    raise ValueError(f"Workspace '{ws_slug}' not found in tenant '{tenant_slug}'")


def resolve_site(client: EngineClient, path: str) -> dict:
    """Resolve 'tenant/workspace/site' to site dict."""
    parts = path.split("/")
    if len(parts) != 3:
        raise ValueError(f"Expected 'tenant/workspace/site', got '{path}'")
    tenant_slug, ws_slug, site_slug = parts
    tenant = resolve_tenant(client, tenant_slug)
    workspaces = client.list_workspaces(tenant["id"])
    workspace = None
    for w in workspaces:
        if w["slug"] == ws_slug:
            workspace = w
            break
    if not workspace:
        raise ValueError(f"Workspace '{ws_slug}' not found in tenant '{tenant_slug}'")

    sites = client.list_sites(workspace["id"])
    for s in sites:
        if s["slug"] == site_slug:
            return s
    raise ValueError(f"Site '{site_slug}' not found in workspace '{ws_slug}'")
