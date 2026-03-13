import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.database import SessionLocal
from app.routers import (
    tenants,
    workspaces,
    sites,
    deployments,
    domains,
    services,
    members,
    tokens,
    webhooks,
    linked_services,
    notifications,
    health,
    previews,
    platform,
    registry,
)
from app.services.container_manager import sync_all_sites

logger = logging.getLogger(__name__)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: sync site statuses with actual container state
    print("[adhara] Syncing site statuses with Docker...", flush=True)
    db = SessionLocal()
    try:
        result = await sync_all_sites(db)
        print(f"[adhara] Status sync complete: {result['synced']}/{result['total']} sites updated", flush=True)
    except Exception as e:
        print(f"[adhara] Status sync failed (non-fatal): {e}", flush=True)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Adhara Engine",
    description="Multi-tenant frontend deployment platform. Copyright 2026 EIM Global Solutions, LLC.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(tenants.router)
app.include_router(workspaces.router)
app.include_router(sites.router)
app.include_router(deployments.router)
app.include_router(domains.router)
app.include_router(services.router)
app.include_router(members.router)
app.include_router(tokens.router)
app.include_router(webhooks.router)
app.include_router(linked_services.router)
app.include_router(notifications.router)
app.include_router(health.router)
app.include_router(previews.router)
app.include_router(platform.router)
app.include_router(registry.router)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "adhara-engine-api",
        "version": "0.1.0",
    }


@app.get("/")
async def root():
    return {
        "name": "Adhara Engine",
        "version": "0.1.0",
        "docs": "/docs",
    }
