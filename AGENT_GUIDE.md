# Adhara Engine — AI Agent Integration Guide

> **Purpose**: This document gives an AI agent everything it needs to programmatically create tenants, workspaces, sites, and deploy applications through the Adhara Engine API. No codebase scanning required.

---

## Quick Start

```bash
# Base URL
ENGINE_URL="http://localhost:8000"

# Auth: either an API token or OIDC JWT
AUTH="Authorization: Bearer ae_live_xxx"

# 1. Create tenant
TENANT=$(curl -s -X POST "$ENGINE_URL/api/v1/tenants" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"name":"Acme Corp","slug":"acme","owner_email":"admin@acme.com","plan":"pro"}')
TENANT_ID=$(echo $TENANT | jq -r '.id')

# 2. Create workspace
WORKSPACE=$(curl -s -X POST "$ENGINE_URL/api/v1/tenants/$TENANT_ID/workspaces" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"name":"Production","slug":"production"}')
WORKSPACE_ID=$(echo $WORKSPACE | jq -r '.id')

# 3. Create site
SITE=$(curl -s -X POST "$ENGINE_URL/api/v1/workspaces/$WORKSPACE_ID/sites" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"name":"My App","slug":"my-app","source_type":"docker_image","source_url":"myapp:latest","container_port":3000}')
SITE_ID=$(echo $SITE | jq -r '.id')

# 4. Set env vars
curl -s -X PUT "$ENGINE_URL/api/v1/sites/$SITE_ID/env" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"runtime_env":{"DATABASE_URL":"postgres://...","SECRET_KEY":"xxx"}}'

# 5. Deploy
curl -s -X POST "$ENGINE_URL/api/v1/sites/$SITE_ID/deploy" \
  -H "$AUTH" -H "Content-Type: application/json" -d '{}'
# Returns 202 with pipeline_run_id

# 6. Check status
curl -s "$ENGINE_URL/api/v1/sites/$SITE_ID/status" -H "$AUTH"
```

---

## API Reference

### Authentication

Two methods (check `Authorization` header):

| Method | Format | Use Case |
|--------|--------|----------|
| API Token | `Bearer ae_live_{random}` | Scripts, CI/CD, service accounts |
| OIDC JWT | `Bearer eyJ...` | Browser users via Logto/Zitadel |

In dev mode (no auth configured), requests work without a token.

### Base URL

All endpoints are prefixed with `/api/v1`. Health check is at `/health`.

---

### Tenants

Tenants are the top-level organizational unit.

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/tenants` | Create tenant |
| `GET` | `/tenants` | List all tenants |
| `GET` | `/tenants/{tenant_id}` | Get tenant |
| `PATCH` | `/tenants/{tenant_id}` | Update tenant |
| `DELETE` | `/tenants/{tenant_id}` | Delete tenant (cascades) |

**Create tenant request:**
```json
{
  "name": "Acme Corp",
  "slug": "acme",
  "owner_email": "admin@acme.com",
  "plan": "free"
}
```

**Plans:** `free`, `starter`, `pro`, `enterprise`

**Response includes:** `id` (UUID), `name`, `slug`, `plan`, `owner_email`, `created_at`

---

### Workspaces

Workspaces group sites within a tenant. A workspace can optionally link to an Adhara Web instance.

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/tenants/{tenant_id}/workspaces` | Create workspace |
| `GET` | `/tenants/{tenant_id}/workspaces` | List workspaces |
| `GET` | `/workspaces/{workspace_id}` | Get workspace |
| `PATCH` | `/workspaces/{workspace_id}` | Update workspace |
| `DELETE` | `/workspaces/{workspace_id}` | Delete workspace (cascades) |

**Create workspace request:**
```json
{
  "name": "Production",
  "slug": "production",
  "adhara_api_url": "https://app.adhara.app",
  "adhara_api_key": "optional-api-key"
}
```

---

### Sites

Sites are individual deployed applications (containers).

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/workspaces/{workspace_id}/sites` | Create site |
| `GET` | `/workspaces/{workspace_id}/sites` | List sites |
| `GET` | `/sites/{site_id}` | Get site details |
| `PATCH` | `/sites/{site_id}` | Update site |
| `DELETE` | `/sites/{site_id}` | Delete site |

**Create site request:**
```json
{
  "name": "My App",
  "slug": "my-app",
  "source_type": "git_repo",
  "source_url": "https://github.com/org/repo.git",
  "dockerfile_path": "Dockerfile",
  "container_port": 3000,
  "deploy_target": "local",
  "health_check_path": "/health",
  "health_auto_remediate": true,
  "custom_domains": ["app.example.com"]
}
```

**Source types:**

| Type | `source_url` value | Description |
|------|-------------------|-------------|
| `git_repo` | `https://github.com/org/repo.git` | Clones and builds Dockerfile |
| `docker_image` | `myapp:latest` | Uses a local Docker image |
| `docker_registry` | `registry.example.com/myapp:v1` | Pulls from remote registry |
| `upload` | — | Upload tarball via separate endpoint |

**Deploy targets:** `local` (default), `cloud_run`, `aws_ecs`, `azure_container`, `kubernetes`

**Important fields:**

| Field | Default | Description |
|-------|---------|-------------|
| `container_port` | `3000` | Port the app listens on inside the container |
| `host_port` | auto-assigned | External port (allocated from 4001-5000 pool) |
| `dockerfile_path` | `Dockerfile` | Path to Dockerfile relative to repo root |
| `build_command` | — | Optional custom build command |
| `git_branch` | `main` | Branch to build from |
| `auto_deploy` | `false` | Enable webhook-triggered deploys |

---

### Environment Variables

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/sites/{site_id}/env` | Get all env vars |
| `PUT` | `/sites/{site_id}/env` | Set env vars (bulk) |
| `DELETE` | `/sites/{site_id}/env/{key}` | Remove single var |

**Set env vars request:**
```json
{
  "runtime_env": {
    "DATABASE_URL": "postgres://user:pass@host/db",
    "SECRET_KEY": "xxx",
    "DEBUG": "false"
  },
  "build_env": {
    "PUBLIC_API_URL": "https://api.example.com"
  }
}
```

- `runtime_env` — injected into the running container
- `build_env` — available during Docker build (as ARGs)

---

### Deployments

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/sites/{site_id}/deploy` | Trigger deployment (returns 202) |
| `POST` | `/sites/{site_id}/stop` | Stop container |
| `POST` | `/sites/{site_id}/restart` | Restart (redeploy) |
| `GET` | `/sites/{site_id}/status` | Container status |
| `GET` | `/sites/{site_id}/logs?tail=100` | Container logs |
| `GET` | `/sites/{site_id}/deployments` | Deployment history |

**Deploy request (optional body):**
```json
{
  "synchronous": false
}
```

Returns `202 Accepted` with `pipeline_run_id` for async tracking.

**Site statuses:** `stopped`, `building`, `deploying`, `running`, `error`

**Deployment statuses:** `queued`, `building`, `pushing`, `deploying`, `live`, `failed`, `rolled_back`

---

### Pipelines (async deploy tracking)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/sites/{site_id}/pipelines` | List pipeline runs |
| `GET` | `/pipelines/{pipeline_run_id}` | Get pipeline with stages |
| `POST` | `/pipelines/{pipeline_run_id}/cancel` | Cancel running pipeline |
| `POST` | `/pipelines/{pipeline_run_id}/retry` | Retry failed pipeline |

---

### Ports

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/ports` | View port allocation table |
| `PATCH` | `/sites/{site_id}/ports` | Update port assignments |

Host ports are auto-assigned from the range 4001-5000.

---

## Networking & Routing

### Container naming
```
ae-{tenant_slug}-{workspace_slug}-{site_slug}
```
Example: `ae-acme-production-my-app`

### Default hostname
```
{site_slug}.{workspace_slug}.{tenant_slug}.localhost
```
Example: `my-app.production.acme.localhost`

### Custom domains
Set via `custom_domains` array on site creation/update. Traefik handles SSL automatically via Let's Encrypt.

### Docker network
All containers join `adhara-engine-net` bridge network. Services can reach each other by container name.

### Direct port access
Every site is also accessible via its assigned host port: `localhost:{host_port}`

---

## Hierarchy & Cascade

```
Tenant (org)
  └── Workspace (environment/project)
        └── Site (deployed container)
              └── Deployment (version history)
```

Deleting a tenant cascades to all workspaces, sites, and deployments beneath it.

---

## RBAC & Permissions

Roles are hierarchical — a tenant_admin inherits workspace and site permissions.

| Scope | Roles |
|-------|-------|
| Platform | `platform_admin`, `platform_viewer` |
| Tenant | `tenant_owner`, `tenant_admin`, `tenant_member` |
| Workspace | `workspace_admin`, `workspace_deployer`, `workspace_viewer` |
| Site | `site_admin`, `site_deployer`, `site_viewer` |

Key permissions for deployment scripts: `SITE_CREATE`, `SITE_DEPLOY`, `SITE_ENV`, `SITE_UPDATE`, `WORKSPACE_CREATE`, `TENANT_CREATE`

---

## CLI Reference

If `adhara-engine` CLI is installed:

```bash
# Tenants
adhara-engine tenant create --name "Acme" --email owner@acme.com --plan pro
adhara-engine tenant list

# Workspaces
adhara-engine workspace create --tenant acme --name production
adhara-engine workspace list --tenant acme

# Sites
adhara-engine site create --workspace acme/production --name "My App" \
  --port 3000 --source git_repo --source-url https://github.com/org/repo.git
adhara-engine site deploy acme/production/my-app
adhara-engine site logs acme/production/my-app
adhara-engine site info acme/production/my-app
adhara-engine site stop acme/production/my-app
adhara-engine site restart acme/production/my-app
```

Slash notation: `{tenant}/{workspace}/{site}`

---

## Common Patterns

### Deploy a two-service app (frontend + backend)

```bash
# Create both sites in the same workspace
# Backend:
POST /workspaces/{ws_id}/sites
  {"name":"API","slug":"api","source_type":"git_repo","source_url":"...","container_port":8080}

# Frontend (reference backend by Engine hostname):
POST /workspaces/{ws_id}/sites
  {"name":"Web","slug":"web","source_type":"git_repo","source_url":"...","container_port":3000}

# Set frontend env to point to backend
PUT /sites/{frontend_id}/env
  {"build_env":{"PUBLIC_API_URL":"http://api.{workspace}.{tenant}.localhost"}}

# Deploy both
POST /sites/{backend_id}/deploy
POST /sites/{frontend_id}/deploy
```

### Link to Adhara Web

Set `adhara_api_url` and `adhara_api_key` on the workspace. Engine automatically injects `ADHARA_API_URL` into all site containers in that workspace.

### Git auto-deploy (webhooks)

```bash
PATCH /sites/{site_id}
{
  "auto_deploy": true,
  "git_branch": "main",
  "git_provider": "github"
}
```
Returns a `webhook_secret` — configure it in your GitHub repo settings.

---

## Environment Variables Injected by Engine

These are automatically available in every container:

| Variable | Value | Description |
|----------|-------|-------------|
| `ADHARA_API_URL` | From workspace config | Adhara Web API URL (if workspace is linked) |
| `ADHARA_PUBLIC_URL` | `http://localhost:{host_port}` | The site's own public URL |

---

## Key Files in This Repo

| File | Purpose |
|------|---------|
| `api/app/routers/tenants.py` | Tenant CRUD endpoints |
| `api/app/routers/workspaces.py` | Workspace CRUD endpoints |
| `api/app/routers/sites.py` | Site CRUD + env endpoints |
| `api/app/routers/deployments.py` | Deploy, stop, restart, logs, status |
| `api/app/services/container_manager.py` | Core deployment orchestration |
| `api/app/services/local_deploy.py` | Docker container lifecycle |
| `api/app/core/auth.py` | Token + OIDC authentication |
| `api/app/core/authorize.py` | RBAC permission checks |
| `api/app/models/` | SQLAlchemy models for all entities |
| `docker-compose.yml` | Full Engine stack (API, worker, Traefik, DB, Redis) |
| `traefik/traefik.yml` | Reverse proxy configuration |
| `cli/` | CLI tool source |

---

## Error Handling

All errors return JSON:
```json
{"detail": "Human-readable error message"}
```

| HTTP Code | Meaning |
|-----------|---------|
| 400 | Bad request (validation error) |
| 401 | Not authenticated |
| 403 | Insufficient permissions |
| 404 | Resource not found |
| 409 | Conflict (e.g., duplicate slug) |
| 422 | Validation error (Pydantic) |
| 500 | Internal server error |

---

*This guide is maintained for AI agent consumption. Last updated: 2026-03-16.*
