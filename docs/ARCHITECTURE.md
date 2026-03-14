# Adhara Engine — Architecture Document

> Copyright (c) 2026 EIM Global Solutions, LLC. All rights reserved.
> Proprietary and confidential.

> Authoritative design document for the Adhara Engine deployment platform.
> Last updated: 2026-03-14

## Table of Contents

1. [System Overview](#system-overview)
2. [Data Model](#data-model)
3. [Pipeline Engine](#pipeline-engine)
4. [Build Drivers](#build-drivers)
5. [Git Provider Layer](#git-provider-layer)
6. [Authentication](#authentication)
7. [RBAC (Role-Based Access Control)](#rbac)
8. [Health Monitoring & Auto-Healing](#health-monitoring--auto-healing)
9. [Linked Services](#linked-services)
10. [Blue-Green Deployments](#blue-green-deployments)
11. [Notifications & Real-Time Streaming](#notifications--real-time-streaming)
12. [API Token System](#api-token-system)
13. [API Endpoint Reference](#api-endpoint-reference)
14. [Implementation Phases](#implementation-phases)

---

## System Overview

Adhara Engine is a self-hosted, multi-tenant deployment platform for web applications. It provides Vercel-like functionality with full data ownership, pluggable build backends, and self-hosted git support.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ADHARA ENGINE                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌───────────────────┐                                             │
│  │  GIT PROVIDER     │  GitHub webhook ──┐                         │
│  │  LAYER            │  GitLab webhook ──┼──▶ Normalized           │
│  │                   │  Polling fallback ─┘    PushEvent           │
│  └───────────────────┘                            │                │
│                                                   ▼                │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │  PIPELINE ENGINE (ARQ / Redis-backed)                    │      │
│  │                                                          │      │
│  │  PipelineRun                                             │      │
│  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐        │      │
│  │  │ CLONE  │─▶│  SCAN  │─▶│ BUILD  │─▶│ DEPLOY │        │      │
│  │  │        │  │(opt)   │  │+ PUSH  │  │        │        │      │
│  │  └────────┘  └────────┘  └────────┘  └────────┘        │      │
│  │  Each = PipelineStage row with status + logs             │      │
│  └──────────────────────────────────────────────────────────┘      │
│                        │                                           │
│                   BUILD stage uses:                                 │
│                        ▼                                           │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │  BUILD DRIVER LAYER (pluggable)                          │      │
│  │  ┌─ LocalDockerBuilder       (Phase 1)                   │      │
│  │  ├─ LocalBuildKitBuilder     (Phase 1.5)                 │      │
│  │  ├─ RemoteBuildKitBuilder    (Phase 2)                   │      │
│  │  ├─ GCPCloudBuildDriver      (Phase 3)                   │      │
│  │  └─ AWSCodeBuildDriver       (Phase 3)                   │      │
│  └──────────────────────────────────────────────────────────┘      │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │  DEPLOY TARGET LAYER (existing)                          │      │
│  │  LocalDeployTarget ──▶ docker run + Traefik labels       │      │
│  │  Blue-green: start green → health check → swap → drain   │      │
│  └──────────────────────────────────────────────────────────┘      │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │  RBAC        │  │  HEALTH      │  │  LINKED      │             │
│  │  Membership  │  │  MONITOR     │  │  SERVICES    │             │
│  │  + API Token │  │  Auto-heal   │  │  Postgres    │             │
│  │  10 roles    │  │  Escalation  │  │  Redis       │             │
│  │  24 perms    │  │  ladder      │  │  MinIO       │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19, TypeScript, Vite 7, Tailwind CSS 4, TanStack Query |
| **Backend** | FastAPI, SQLAlchemy, Alembic, Python 3.12 |
| **Auth** | Pluggable: API tokens (built-in), Logto OIDC (lightweight SSO), or Zitadel OIDC (enterprise SSO) — DB-backed RBAC for authorization |
| **Database** | PostgreSQL 16, Redis 7 |
| **Background Jobs** | ARQ (async Redis queue) |
| **Proxy** | Traefik v3 (auto-discovery via Docker labels) |
| **Storage** | MinIO (S3-compatible) |
| **Logging** | Grafana Loki + Alloy + Grafana dashboards |
| **Registry** | Docker Registry v2 (local) |
| **CLI** | Typer + httpx + Rich |

---

## Data Model

### Entity Hierarchy

```
Tenant (company/organization)
  └── Workspace (environment: production, staging)
       └── Site (individual web application)
            ├── Deployment (version history, immutable records)
            ├── PipelineRun (build pipeline execution)
            │    └── PipelineStage (clone, scan, build, push, deploy)
            ├── LinkedService (postgres, redis, minio_bucket)
            ├── HealthEvent (health check audit trail)
            └── NotificationConfig (webhook, email, slack)

Membership (user ↔ resource role assignment)
APIToken (scoped service account tokens)
```

### Tables (13 total)

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `tenants` | Companies/orgs | name, slug, plan, owner_email |
| `workspaces` | Environments within tenant | name, slug, tenant_id |
| `sites` | Individual web apps | source_type, source_url, status, git_*, health_*, build_driver |
| `deployments` | Immutable deploy records | version, image_tag, status, build_logs |
| `pipeline_runs` | Pipeline execution tracking | trigger, git_provider, commit_sha, status, build_driver |
| `pipeline_stages` | Individual stage progress | name, order, status, logs, duration_ms, metadata |
| `memberships` | RBAC role assignments | user_id, resource_type, resource_id, role, expires_at |
| `api_tokens` | Scoped API tokens | token_hash, scopes, expires_at, revoked |
| `linked_services` | Provisioned infrastructure | service_type, container_id, connection_env |
| `health_events` | Health check history | status_code, response_ms, healthy, action_taken |
| `notification_configs` | Alert channels | type (webhook/email/slack), target, events |
| `preview_environments` | PR preview deployments | pr_number, pr_branch, status, host_port, ttl_hours |

### Site Model — Extended Fields

The Site model has been extended with fields for:

**Git-follow configuration:**
- `git_provider` — "github" or "gitlab"
- `git_provider_url` — custom URL for self-hosted GitLab
- `git_branch` — branch to watch (default: "main")
- `auto_deploy` — enable automatic deploy on push
- `webhook_secret` — per-site webhook secret
- `last_deployed_sha` — deduplication key
- `git_token_username`, `git_token` — deploy token credentials

**Build configuration:**
- `build_driver` — per-site override (null = global default)
- `scan_enabled` — enable code scanning stage
- `scan_fail_on` — severity threshold (critical/high/medium/low)

**Health monitoring:**
- `health_failure_count` — consecutive failure counter
- `health_status` — healthy/degraded/down/unknown
- `last_health_check`, `last_healthy_at` — timestamps

**Blue-green deploy state:**
- `active_container_id` — currently serving traffic
- `pending_container_id` — green container during deploy

---

## Pipeline Engine

### Overview

The pipeline replaces the synchronous deploy flow with an async, staged process backed by ARQ (Redis queue). The pipeline is **optional** — you can still build locally and push images directly.

### Pipeline Flow

```
Trigger (manual / webhook / poll)
    │
    ▼
POST /api/v1/sites/{id}/deploy
    │
    ▼
Create PipelineRun (status: pending)
Create PipelineStages: [clone, scan, build, push, deploy]
    │
    ▼
Enqueue ARQ job: run_pipeline(pipeline_run_id)
    │
    ▼
Return 202 Accepted + pipeline_run_id
    │
    ▼ (background worker)
┌────────────────────────────────────────────────┐
│  CLONE   → git clone --depth=1, checkout SHA   │
│  SCAN    → Semgrep static analysis (optional)  │
│  BUILD   → BuildDriver.build() (pluggable)     │
│  PUSH    → Push to registry (via Traefik /v2)   │
│  DEPLOY  → Blue-green deploy via DeployTarget   │
└────────────────────────────────────────────────┘
    │
    ▼
Update PipelineRun status: succeeded / failed
Create Deployment record (if successful)
Send notifications
```

### Stage Statuses

| Status | Meaning |
|--------|---------|
| `pending` | Not yet started |
| `running` | Currently executing |
| `passed` | Completed successfully |
| `failed` | Error occurred |
| `skipped` | Stage not applicable (e.g., scan disabled) |

### ARQ Worker Configuration

- **Redis-backed**: survives API restarts
- **Max concurrent pipelines**: 10
- **Job timeout**: 10 minutes per pipeline
- **Docker Compose service**: `worker` (same image as `api`, different command)
- **Cron jobs**: health monitor (every 30s)

```yaml
# docker-compose.yml
worker:
  build: ./api
  command: ["arq", "app.workers.settings.WorkerSettings"]
  volumes:
    - ${DOCKER_HOST_SOCKET}:/var/run/docker.sock
  depends_on:
    db: { condition: service_healthy }
    redis: { condition: service_healthy }
```

### Key Files

| File | Purpose |
|------|---------|
| `api/app/services/build_drivers/base.py` | BuildDriver ABC, BuildRequest, BuildResult |
| `api/app/services/build_drivers/local_docker.py` | LocalDockerBuilder — clone, scan, build, push |
| `api/app/services/build_drivers/__init__.py` | Driver registry + get_build_driver() factory |
| `api/app/workers/pipeline.py` | run_pipeline ARQ task — orchestrates stages |
| `api/app/workers/health.py` | check_all_sites ARQ cron — health monitoring |
| `api/app/workers/settings.py` | WorkerSettings — ARQ configuration |
| `api/app/schemas/pipeline.py` | Pydantic schemas for pipeline API responses |
| `api/app/routers/deployments.py` | Deploy + pipeline endpoints (202 async) |

---

## Build Drivers

### Architecture

Build drivers decouple **where** images are built from the pipeline orchestration. Each site can override the global default.

```python
# Resolution order:
driver = site.build_driver or platform_settings["default_build_driver"] or "local_docker"
```

### Interface

```python
class BuildDriver(ABC):
    async def build(self, request: BuildRequest) -> BuildResult: ...
    async def cancel(self, build_id: str) -> None: ...
    async def health(self) -> bool: ...

@dataclass
class BuildRequest:
    git_url: str
    git_ref: str
    dockerfile_path: str
    build_args: dict[str, str]
    image_tag: str
    registry_creds: RegistryAuth | None

@dataclass
class BuildResult:
    success: bool
    image_ref: str
    build_id: str
    duration_seconds: float
    logs: str
    error: str | None
```

### Available Drivers

| Driver | Backend | Phase | Status |
|--------|---------|-------|--------|
| `LocalDockerBuilder` | Docker SDK on host | 1 | DONE |
| `LocalBuildKitBuilder` | `docker buildx build` | 1.5 | DONE |
| `GCPCloudBuildDriver` | Cloud Build REST API | 3 | DONE |
| `AWSCodeBuildDriver` | CodeBuild SDK | 3 | DONE |

---

## Scan Drivers

### Architecture

Scan drivers are decoupled from build drivers — they handle static analysis independently during the SCAN pipeline stage.

```python
class ScanDriver(ABC):
    async def scan(self, request: ScanRequest) -> ScanResult: ...
    async def health(self) -> bool: ...
    @property
    def name(self) -> str: ...
```

### Available Scanners

| Scanner | Backend | Status |
|---------|---------|--------|
| `SemgrepScanner` | Semgrep CLI (30+ languages) | DONE |
| (future) `FortifyScanner` | Fortify SCA | Phase 4 |

### ScanResult

```python
@dataclass
class ScanResult:
    success: bool
    passed: bool | None    # None = not scanned
    findings: list[ScanFinding]
    findings_by_severity: dict[str, int]
    total_findings: int
    logs: str
    raw_output: dict | None
```

### Key Files

| File | Purpose |
|------|---------|
| `api/app/services/scan_drivers/base.py` | ScanDriver ABC, ScanRequest, ScanResult, ScanFinding |
| `api/app/services/scan_drivers/semgrep.py` | SemgrepScanner implementation |
| `api/app/services/scan_drivers/__init__.py` | Scanner registry + get_scan_driver() |

---

## PR Preview Environments

### Overview

PR previews are ephemeral deployments created when a pull request is opened against a site's repo. They auto-destroy when the PR is merged or closed, or when the TTL expires.

### Lifecycle

```
PR Opened (webhook)
    ↓
Create PreviewEnvironment (status: building)
Create PipelineRun (trigger: preview)
Enqueue build → same pipeline as normal deploys
    ↓
PR Updated (new commits pushed)
    ↓
Update preview, trigger new build
    ↓
PR Merged/Closed
    ↓
Destroy preview (stop container, mark destroyed)

TTL Expired (cron every 5 min)
    ↓
Auto-destroy stale previews
```

### Webhook Events

| Provider | Event | Actions |
|----------|-------|---------|
| GitHub | `pull_request` | opened, synchronize, reopened → build; closed → destroy |
| GitLab | `merge_request` | open, update, reopen → build; close, merge → destroy |

### Endpoints

```
GET    /api/v1/sites/{id}/previews       — list active previews
GET    /api/v1/previews/{id}             — get preview details
POST   /api/v1/sites/{id}/previews       — manually create preview
DELETE /api/v1/previews/{id}             — destroy preview
```

### Key Files

| File | Purpose |
|------|---------|
| `api/app/models/preview_environment.py` | PreviewEnvironment model |
| `api/app/services/preview_manager.py` | Create/update/destroy lifecycle |
| `api/app/routers/previews.py` | CRUD endpoints |
| `api/app/workers/preview_cleanup.py` | TTL cleanup cron |

---

## Git Provider Layer

### Supported Providers

| Provider | Webhooks | Polling | Self-Hosted | Auth |
|----------|----------|---------|-------------|------|
| **GitHub** | HMAC-SHA256 signature | `git ls-remote` | GitHub Enterprise | Deploy keys, PAT |
| **GitLab** | Plain token header | `git ls-remote` | Full support | Deploy tokens |

### Webhook Endpoints

```
POST /api/v1/webhooks/github   — X-Hub-Signature-256 verification
POST /api/v1/webhooks/gitlab   — X-Gitlab-Token verification
```

### Normalized PushEvent

Both providers produce the same internal format:

```python
@dataclass
class PushEvent:
    provider: str           # "github" or "gitlab"
    repo_path: str          # "owner/repo"
    branch: str             # "main"
    commit_sha: str         # SHA to build
    clone_url: str          # HTTPS clone URL
    author_name: str | None
    commit_message: str | None
    is_branch_delete: bool
```

### Key Differences

| Aspect | GitHub | GitLab |
|--------|--------|--------|
| Signature | HMAC-SHA256 over body | Plain token string equality |
| Commit SHA | `head_commit.id` or `after` | `checkout_sha` |
| Clone URL | `repository.clone_url` | `project.git_http_url` |
| Repo path | `repository.full_name` | `project.path_with_namespace` |
| Self-hosted | GitHub Enterprise | Admin must enable local network webhooks |

---

## Authentication

Adhara Engine separates **identity** (who is this person?) from **authorization** (what can they access?). Identity is handled by one of three pluggable auth modes. Authorization is always handled by Adhara Engine's own DB-backed RBAC system.

### Auth Modes

| Mode | Profile | Footprint | Best For |
|------|---------|-----------|----------|
| **API Tokens** | (none — core) | 0 MB extra | Small setups, CI/CD, development, headless automation |
| **Logto SSO** | `auth` | +150 MB | Teams wanting lightweight SSO with a polished admin UI |
| **Zitadel SSO** | `zitadel` | +800 MB | Enterprise multi-tenancy, advanced OIDC policies |

All three modes can coexist — API tokens are always available regardless of which SSO provider (if any) is running.

### Mode 1: API Tokens (Built-in, No SSO)

The simplest auth mode. No external identity provider needed.

```
make init       # start core services (no SSO profile)
make token      # generate a platform-admin API token (ae_live_...)
```

- Tokens are generated server-side and stored as SHA-256 hashes
- Scoped to specific resources and permissions (see [API Token System](#api-token-system))
- Users enter the token on the login page — stored in browser localStorage
- Ideal for single-admin setups, development, and CI/CD pipelines

### Mode 2: Logto SSO (Lightweight OIDC)

A full OIDC provider with a modern admin console, social login support, and low resource usage.

```
make init-auth   # start core + Logto (~650 MB total)
```

- **Admin Console:** `http://localhost:3002` — create applications, manage users
- After creating an application in Logto, copy the Client ID to `VITE_OIDC_CLIENT_ID` in `ui/.env`
- Supports social login (Google, GitHub, etc.), passwordless, and email/password
- OIDC endpoints served on port 3001 internally, validated via JWKS

### Mode 3: Zitadel SSO (Enterprise OIDC)

A full-featured identity platform with multi-tenancy, advanced policies, and audit logging.

```
make init-zitadel                   # start core + Zitadel (~1.3 GB total)
bash scripts/setup-zitadel.sh      # auto-configure OIDC application
```

- **Console:** `http://localhost/ui/console/` — routed through Traefik on port 80
- Supports organizations, machine users, custom roles, and compliance features
- First boot takes 3-5 minutes to bootstrap
- OIDC endpoints validated via JWKS with Host header forwarding

### How Auth Detection Works

The auth middleware inspects the `Authorization: Bearer <token>` header and routes automatically:

```
Token arrives
    │
    ├─ Starts with "ae_"  → API token validation (DB hash lookup)
    │
    ├─ Contains 2 dots (JWT) → OIDC JWT validation (JWKS signature check)
    │
    └─ Anything else → OIDC userinfo endpoint (opaque token fallback)
```

This means API tokens and OIDC tokens work simultaneously — no configuration needed to switch between them.

### Key Files

| File | Purpose |
|------|---------|
| `api/app/core/auth.py` | Auth middleware — token detection, JWT + API token validation |
| `api/app/core/config.py` | OIDC settings (issuer, JWKS path, client ID) |
| `api/app/models/api_token.py` | API token model (hash, scopes, expiry) |
| `scripts/create_token.py` | CLI token generation script |

---

## RBAC

### Design Decision

**The OIDC provider handles identity** (who is this person?). **Adhara Engine handles authorization** (what can they access?).

Memberships are stored in our database (not JWT claims) so revocation is **instant** — delete the row, next API call is denied.

### Role Hierarchy

```
PLATFORM level
  ├── platform_admin     — all permissions, all resources
  └── platform_viewer    — read-only across everything

TENANT level
  ├── tenant_owner       — full control of tenant + descendants
  ├── tenant_admin       — manage workspaces, users, settings
  └── tenant_member      — view only

WORKSPACE level
  ├── workspace_admin    — full control of workspace + sites
  ├── workspace_deployer — deploy, restart, rollback
  └── workspace_viewer   — read-only

SITE level
  ├── site_admin         — full control of one site
  ├── site_deployer      — deploy/restart one site
  └── site_viewer        — read-only one site
```

### Authorization Flow

```python
# Every endpoint:
await authorize(user, Permission.SITE_DEPLOY, "site", site_id, db)

# The authorize() function walks UP the hierarchy:
# 1. Check site-level membership
# 2. Check workspace-level membership
# 3. Check tenant-level membership
# 4. Check platform-level membership
# First match wins (most specific role takes precedence)
```

### Permission Matrix

24 permissions across 4 resource types. See `api/app/core/permissions.py` for the complete mapping.

### Revocation

```
Admin removes user from tenant:
  DELETE /api/v1/tenants/{id}/members/{user_id}
    → Deletes membership at tenant level
    → CASCADE: deletes workspace + site memberships under that tenant
    → Immediate effect (DB-checked per request)
```

### Key Files

| File | Purpose |
|------|---------|
| `api/app/models/membership.py` | Membership model |
| `api/app/core/permissions.py` | Permission enum + role mappings |
| `api/app/core/authorize.py` | authorize() function + hierarchy walk |
| `api/app/core/auth.py` | JWT + API token authentication |

---

## Health Monitoring & Auto-Healing

### Health Check Loop

ARQ cron job runs every 30 seconds. For each running site:

1. HTTP GET to `site.health_check_path`
2. If 200: reset failure counter, mark healthy
3. If fail: increment counter, escalate

### Escalation Ladder

| Level | Threshold | Action |
|-------|-----------|--------|
| 1 | 3 consecutive failures | Restart container |
| 2 | 5 consecutive failures | Rebuild from last committed SHA |
| 3 | 8 consecutive failures | Rollback to previous deployment |
| 4 | 10+ consecutive failures | Alert owner via notifications |

Each action is logged as a `HealthEvent` record.

### Site Health Status

| Status | Meaning |
|--------|---------|
| `healthy` | Last health check passed |
| `degraded` | Auto-healing exhausted, owner alerted |
| `down` | Container not running |
| `unknown` | No health checks performed yet |

---

## Linked Services

### Supported Types

| Type | Container | Injected Env Vars |
|------|-----------|-------------------|
| `postgres` | `postgres:16-alpine` | `DATABASE_URL`, `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD` |
| `redis` | `redis:7-alpine` | `REDIS_URL` |
| `minio_bucket` | Shared MinIO instance | `S3_BUCKET`, `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` |

### Provisioning Flow

1. Site declares needed services
2. Pipeline checks if service containers exist
3. Missing services are provisioned (Docker run with auto-generated credentials)
4. Connection env vars injected into site's runtime environment
5. On site delete: configurable — keep data (default) or remove

### Lifecycle Safety

`delete_on_site_removal` defaults to `false` — data is preserved even when sites are deleted. Orphaned services are flagged.

---

## Blue-Green Deployments

### Flow (Zero-Downtime)

```
1. Start NEW container: ae-{tenant}-{workspace}-{site}-green
   (temporary port, no Traefik labels)

2. Wait for health check (up to 60s)

3. If healthy:
   → Apply Traefik labels to GREEN
   → Remove Traefik labels from BLUE (old)
   → Wait 10s drain period
   → Stop BLUE container
   → GREEN becomes the active container

4. If unhealthy:
   → Stop GREEN container
   → BLUE keeps serving (zero disruption)
   → Pipeline marked FAILED
```

### State Tracking

- `site.active_container_id` — currently serving traffic
- `site.pending_container_id` — green container during deploy

---

## Notifications & Real-Time Streaming

### Notification Channels

| Type | Target | Events |
|------|--------|--------|
| `webhook` | Any URL | POST with event JSON payload |
| `email` | Email address | Formatted notification |
| `slack` | Slack webhook URL | Slack message block |

### Supported Events

- `deploy_started`, `deploy_succeeded`, `deploy_failed`
- `health_degraded`, `health_recovered`
- `rollback_triggered`
- `scan_failed`

### Real-Time Log Streaming

```
GET /api/v1/pipelines/{id}/stream  (Server-Sent Events)

Events:
  stage_started   — stage name, order
  stage_log       — incremental log output
  stage_completed — status, duration
  pipeline_done   — final status
```

---

## API Token System

### Token Format

```
ae_live_<32 random chars>
```

- `ae_` prefix distinguishes from OIDC JWTs
- SHA-256 hash stored in database (never plaintext after creation)
- `token_prefix` stores first 12 chars for identification in lists

### Authentication Flow

1. Request arrives with `Authorization: Bearer ae_live_...`
2. Auth middleware detects `ae_` prefix
3. Hash token, look up in `api_tokens` table
4. Check: not revoked, not expired
5. Return synthetic user claims with scoped permissions

### Scoping

Tokens are scoped to specific resources and permissions:

```json
{
  "scopes": [
    {
      "resource_type": "workspace",
      "resource_id": "uuid",
      "permissions": ["site:deploy", "site:restart"]
    }
  ]
}
```

Users cannot create tokens with permissions they don't have.

---

## API Endpoint Reference

### Core Resources

```
GET/POST   /api/v1/tenants
GET/PATCH/DELETE /api/v1/tenants/{id}

GET/POST   /api/v1/tenants/{id}/workspaces
GET/PATCH/DELETE /api/v1/workspaces/{id}

GET/POST   /api/v1/workspaces/{id}/sites
GET/PATCH/DELETE /api/v1/sites/{id}
```

### Pipeline & Deploys

```
POST       /api/v1/sites/{id}/deploy           — trigger pipeline
POST       /api/v1/sites/{id}/rollback/{ver}    — rollback to version
GET        /api/v1/sites/{id}/pipelines         — list pipeline runs
GET        /api/v1/pipelines/{id}               — pipeline + stages
POST       /api/v1/pipelines/{id}/cancel        — cancel running
POST       /api/v1/pipelines/{id}/retry         — retry failed
GET        /api/v1/pipelines/{id}/stream        — SSE log stream
```

### Container Lifecycle

```
POST       /api/v1/sites/{id}/stop
POST       /api/v1/sites/{id}/restart
GET        /api/v1/sites/{id}/status
GET        /api/v1/sites/{id}/logs
```

### Git Configuration

```
PUT        /api/v1/sites/{id}/git-config
POST       /api/v1/webhooks/github
POST       /api/v1/webhooks/gitlab
```

### Environment Variables

```
GET/PUT    /api/v1/sites/{id}/env
DELETE     /api/v1/sites/{id}/env/{key}
```

### Linked Services

```
GET/POST   /api/v1/sites/{id}/services
DELETE     /api/v1/sites/{id}/services/{svc_id}
```

### Membership Management

```
GET/POST   /api/v1/tenants/{id}/members
PATCH/DELETE /api/v1/tenants/{id}/members/{uid}

GET/POST   /api/v1/workspaces/{id}/members
PATCH/DELETE /api/v1/workspaces/{id}/members/{uid}

GET/POST   /api/v1/sites/{id}/members
PATCH/DELETE /api/v1/sites/{id}/members/{uid}
```

### Health & Monitoring

```
GET        /api/v1/sites/{id}/health-history
GET        /api/v1/dashboard/status
```

### Notifications

```
GET/POST   /api/v1/sites/{id}/notifications
PATCH/DELETE /api/v1/notifications/{id}
```

### API Tokens

```
GET/POST   /api/v1/tokens
DELETE     /api/v1/tokens/{id}
```

### PR Previews

```
GET        /api/v1/sites/{id}/previews      — list active previews
GET        /api/v1/previews/{id}            — get preview details
POST       /api/v1/sites/{id}/previews      — create preview manually
DELETE     /api/v1/previews/{id}            — destroy preview
```

### Platform Admin

```
GET        /api/v1/platform/build-drivers   — list available build drivers
GET        /api/v1/platform/scan-drivers    — list available scan drivers
GET        /api/v1/ports
```

---

## Implementation Phases

### Phase 1: Core Pipeline + RBAC (Current)

| Step | Deliverable | Status |
|------|------------|--------|
| 1a | Data models + Alembic migration | DONE |
| 1b | ARQ worker + pipeline orchestrator | DONE |
| 1c | BuildDriver ABC + LocalDockerBuilder | DONE |
| 1d | Blue-green deploy logic | DONE |
| 1e | Health monitor (ARQ cron) | DONE |
| 1f | Wire deploy endpoint to enqueue pipeline | DONE |
| 1g | Membership CRUD endpoints | DONE |
| 1h | API token CRUD endpoints | DONE |
| 1i | Wire authorize() into all endpoints | DONE |

### Phase 2: Git-Follow + Services

| Step | Deliverable | Status |
|------|------------|--------|
| 2a | GitHub + GitLab webhook receivers | DONE |
| 2b | Polling fallback (ARQ cron) | DONE |
| 2c | Linked service provisioning | DONE |
| 2d | Real-time SSE streaming | DONE |
| 2e | Notification system | DONE |
| 2f | PR preview data model (design only) | Deferred to Phase 3 |

### Phase 3: Scanning + Cloud Builds

| Step | Deliverable | Status |
|------|------------|--------|
| 3a | ScanDriver ABC + Semgrep integration | DONE |
| 3b | LocalBuildKitBuilder (docker buildx) | DONE |
| 3c | GCP Cloud Build driver | DONE |
| 3d | AWS CodeBuild driver | DONE |
| 3e | PR preview environments (model + endpoints + webhook) | DONE |
| 3f | Platform admin endpoints (driver listing) | DONE |

### Phase 4: Advanced

| Step | Deliverable |
|------|------------|
| 4a | Fortify scanner integration |
| 4b | Multi-replica / scaling |
| 4c | Log aggregation per-site |
| 4d | Billing / usage metering |
