"""Services router — exposes Docker Compose service status and logs."""

import os

import docker
from docker.errors import NotFound
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import require_auth
from app.core.authorize import authorize
from app.core.database import get_db
from app.core.permissions import Permission

router = APIRouter(tags=["services"])

_client = docker.from_env()

# Metadata for known Adhara Engine services
SERVICE_META = {
    "api": {
        "display_name": "API Server",
        "description": "FastAPI backend — REST API for the engine",
        "icon": "server",
        "category": "core",
    },
    "ui": {
        "display_name": "Dashboard UI",
        "description": "React admin dashboard",
        "icon": "layout-dashboard",
        "category": "core",
        "management_url": "http://engine.localhost",
    },
    "db": {
        "display_name": "PostgreSQL",
        "description": "Primary database — tenants, workspaces, sites, deployments",
        "icon": "database",
        "category": "data",
    },
    "redis": {
        "display_name": "Redis",
        "description": "Cache and session store",
        "icon": "zap",
        "category": "data",
    },
    "traefik": {
        "display_name": "Traefik",
        "description": "Reverse proxy — routes traffic to sites and services",
        "icon": "network",
        "category": "networking",
        "management_url": "http://localhost:8080",
        "management_label": "Traefik Dashboard",
    },
    "minio": {
        "display_name": "MinIO",
        "description": "S3-compatible object storage for assets and uploads",
        "icon": "hard-drive",
        "category": "storage",
        "management_url": "http://localhost:9001",
        "management_label": "MinIO Console",
    },
    "registry": {
        "display_name": "Docker Registry",
        "description": "Private container image registry (localhost:5000)",
        "icon": "container",
        "category": "storage",
    },
    "loki": {
        "display_name": "Loki",
        "description": "Log aggregation backend — query logs via Grafana Explore",
        "icon": "scroll-text",
        "category": "observability",
        "management_url": "http://localhost:3003/explore",
        "management_label": "Explore in Grafana",
    },
    "alloy": {
        "display_name": "Grafana Alloy",
        "description": "Log collector — ships Docker container logs to Loki",
        "icon": "radio-tower",
        "category": "observability",
    },
    "grafana": {
        "display_name": "Grafana",
        "description": "Dashboards and log viewer — query Loki, visualize metrics",
        "icon": "bar-chart-3",
        "category": "observability",
        "management_url": "http://localhost:3003",
        "management_label": "Grafana Dashboard",
    },
    "logto": {
        "display_name": "Logto",
        "description": "Lightweight OIDC identity provider — SSO, users, roles",
        "icon": "shield",
        "category": "auth",
        "management_url": "http://localhost:3002",
        "management_label": "Logto Admin Console",
    },
    "zitadel": {
        "display_name": "Zitadel",
        "description": "Enterprise identity and access management — SSO, users, roles",
        "icon": "shield",
        "category": "auth",
        "management_url": "/ui/console/",
        "management_label": "Zitadel Console",
    },
}

CATEGORY_ORDER = ["core", "data", "networking", "storage", "observability", "auth"]


def _extract_service_name(container_name: str) -> str:
    """Extract service name from Docker Compose container name like 'adhara-engine-api-1'."""
    # Remove project prefix and instance suffix
    name = container_name.lstrip("/")
    if name.startswith("adhara-engine-"):
        name = name[len("adhara-engine-"):]
    # Remove trailing -N instance number
    parts = name.rsplit("-", 1)
    if len(parts) == 2 and parts[1].isdigit():
        name = parts[0]
    return name


def _container_to_service(container) -> dict:
    """Convert a Docker container object to a service info dict."""
    name = _extract_service_name(container.name)
    meta = SERVICE_META.get(name, {})

    # Get health status
    health = container.attrs.get("State", {}).get("Health", {})
    health_status = health.get("Status") if health else None

    # Get port mappings
    ports = {}
    for port_spec, bindings in (container.ports or {}).items():
        if bindings:
            for b in bindings:
                ports[port_spec] = f"{b.get('HostIp', '0.0.0.0')}:{b['HostPort']}"

    return {
        "name": name,
        "container_name": container.name.lstrip("/"),
        "display_name": meta.get("display_name", name.title()),
        "description": meta.get("description", ""),
        "icon": meta.get("icon", "box"),
        "category": meta.get("category", "other"),
        "status": container.status,
        "health": health_status,
        "image": container.image.tags[0] if container.image.tags else str(container.image.short_id),
        "ports": ports,
        "management_url": meta.get("management_url"),
        "management_label": meta.get("management_label"),
        "started_at": container.attrs.get("State", {}).get("StartedAt"),
    }


@router.get("/api/v1/services")
async def list_services(user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    """List all Adhara Engine Docker Compose services with status."""
    await authorize(user, Permission.PLATFORM_SETTINGS, "platform", None, db)
    containers = _client.containers.list(
        all=True,
        filters={"label": ["com.docker.compose.project=adhara-engine"]},
    )

    services = [_container_to_service(c) for c in containers]

    # Sort by category order, then by name
    def sort_key(s):
        cat_idx = CATEGORY_ORDER.index(s["category"]) if s["category"] in CATEGORY_ORDER else 99
        return (cat_idx, s["name"])

    services.sort(key=sort_key)
    return {"services": services}


@router.get("/api/v1/services/{service_name}/logs")
async def get_service_logs(service_name: str, tail: int = Query(default=200, le=2000), user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    """Get logs for a specific Docker Compose service."""
    await authorize(user, Permission.PLATFORM_SETTINGS, "platform", None, db)
    containers = _client.containers.list(
        all=True,
        filters={"label": ["com.docker.compose.project=adhara-engine"]},
    )

    # Find the matching container
    target = None
    for c in containers:
        if _extract_service_name(c.name) == service_name:
            target = c
            break

    if not target:
        raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")

    logs = target.logs(tail=tail, timestamps=True).decode("utf-8", errors="replace")
    return {
        "service": service_name,
        "lines": logs.splitlines(),
    }


@router.post("/api/v1/services/{service_name}/restart")
def restart_service(service_name: str, user: dict = Depends(require_auth)):
    """Restart a specific Docker Compose service container."""
    # Safety: don't allow restarting db without warning
    containers = _client.containers.list(
        all=True,
        filters={"label": ["com.docker.compose.project=adhara-engine"]},
    )

    target = None
    for c in containers:
        if _extract_service_name(c.name) == service_name:
            target = c
            break

    if not target:
        raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")

    target.restart(timeout=15)
    return {"status": "restarted", "service": service_name}
