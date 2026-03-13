# Adhara Engine - Product Requirements Document

**Version:** 1.0
**Date:** 2026-02-18
**Status:** Draft
**Author:** Patrick Farrell

---

## 1. Executive Summary

Adhara Engine is a self-hosted, multi-tenant deployment platform for frontend websites that connect to the Adhara Web backend. Think of it as a self-managed Vercel — but with full control over where containers run, from a local machine to Google Cloud Run to any cloud provider.

Each tenant (company/client) can have multiple workspaces, and each workspace hosts a site running as a Docker container. Adhara Engine manages the full lifecycle: building, deploying, routing traffic, SSL provisioning, environment configuration, and multi-cloud orchestration.

**Why not just use Vercel?**
- No control over server placement (can't co-locate frontend with backend to reduce latency)
- No multi-tenant management layer
- No native integration with Adhara Web
- Vendor lock-in and per-seat pricing at scale

---

## 2. Problem Statement

Today, Adhara Web provides a complete backend for online businesses (CMS, commerce, email, CRM, scheduling). Custom frontends connect via REST API. But deploying those frontends requires third-party platforms like Vercel, which creates:

1. **Latency:** Servers scattered across providers add unnecessary hops between frontend and backend
2. **No control:** Cannot choose where containers run geographically
3. **No multi-tenant orchestration:** Managing dozens of client sites across separate Vercel accounts is operationally painful
4. **Cost:** Per-seat, per-project pricing doesn't scale for agencies managing many client sites

Adhara Engine solves this by providing a single management plane that orchestrates frontend containers across any infrastructure.

---

## 3. Architecture Overview

```
                         ┌─────────────────────────────────────────────┐
                         │            Adhara Engine                     │
                         │                                             │
   Tenants ──────────▶   │  ┌──────────┐    ┌──────────────────────┐   │
   (CLI / Web UI)        │  │ Admin API │    │   Container Manager  │   │
                         │  │ (FastAPI) │───▶│                      │   │
                         │  └──────────┘    │  ┌────┐ ┌────┐ ┌────┐│   │
                         │       │          │  │Site│ │Site│ │Site││   │
                         │       ▼          │  │ :3001│ │:3002│ │:3003││   │
                         │  ┌──────────┐    │  └────┘ └────┘ └────┘│   │
                         │  │ Web UI   │    └──────────────────────┘   │
                         │  │ (React)  │              │                │
                         │  └──────────┘              ▼                │
                         │                    ┌──────────────┐         │
   Internet ────────▶    │                    │   Traefik    │         │
   (custom domains)      │                    │ (Reverse Proxy│         │
                         │                    │  + Auto SSL)  │         │
                         │                    └──────────────┘         │
                         └─────────────────────────────────────────────┘
                                              │
                                              ▼
                                    ┌──────────────────┐
                                    │   Adhara Web     │
                                    │   (Backend API)  │
                                    │   REST API       │
                                    └──────────────────┘
```

### Core Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Admin API** | FastAPI (Python) | Tenant/workspace/site CRUD, deployment orchestration, configuration |
| **Web UI** | React | Admin dashboard for managing tenants, sites, deployments, logs |
| **CLI** | Python (Typer/Click) | Command-line management for power users and automation |
| **Reverse Proxy** | Traefik | Dynamic traffic routing, auto-SSL via Let's Encrypt, container discovery |
| **Container Runtime** | Docker Engine | Local container execution |
| **Cloud Deployer** | Cloud Run API (V1) | Remote container deployment to Google Cloud |
| **Database** | PostgreSQL | Tenant, workspace, site, deployment metadata |
| **Cache/Queue** | Redis | Build queue, deployment status, real-time updates |

---

## 4. Data Model

### Hierarchy

```
Tenant (Company)
  └── Workspace (Project/Environment)
       └── Site (Single Docker Container)
            ├── Deployments (version history)
            ├── Environment Variables
            ├── Custom Domain(s)
            └── Deploy Target (local | cloud-run | aws-ecs | ...)
```

### Entities

#### Tenant
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| name | string | Company/organization name |
| slug | string | URL-safe identifier |
| plan | enum | Subscription tier |
| owner_email | string | Primary contact |
| created_at | timestamp | Creation date |

#### Workspace
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| tenant_id | UUID | FK to Tenant |
| name | string | Workspace name (e.g., "Production", "Staging") |
| slug | string | URL-safe identifier |
| adhara_api_url | string | Adhara Web backend URL for this workspace |
| adhara_api_key | string (encrypted) | API key for Adhara Web |
| created_at | timestamp | Creation date |

#### Site
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| workspace_id | UUID | FK to Workspace |
| name | string | Site name |
| slug | string | URL-safe identifier |
| source_type | enum | `git_repo`, `docker_image`, `docker_registry`, `upload` |
| source_url | string | Git URL, image path, or registry URL |
| dockerfile_path | string | Path to Dockerfile (for git source) |
| build_command | string | Optional build override |
| container_port | integer | Port the app listens on INSIDE the container (e.g., 3000 for Next.js, 5173 for Vite) |
| host_port | integer | Port mapped on the host machine (auto-assigned from pool, or manually set) |
| deploy_target | enum | `local`, `cloud_run`, `aws_ecs`, `azure_container` |
| deploy_region | string | Target region (e.g., `us-east1`, `us-east-1`) |
| custom_domains | string[] | List of custom domains |
| runtime_env | jsonb (encrypted) | Runtime environment variables (injected via Docker `-e`, available to server-side code) |
| build_env | jsonb (encrypted) | Build-time environment variables (passed as `--build-arg`, inlined into JS bundles — e.g., `NEXT_PUBLIC_*`) |
| health_check_path | string | Health check endpoint path (default: `/api/health`) |
| status | enum | `stopped`, `building`, `deploying`, `running`, `error` |
| current_deployment_id | UUID | FK to active Deployment |
| created_at | timestamp | Creation date |

#### Deployment
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| site_id | UUID | FK to Site |
| version | integer | Auto-incrementing version number |
| source_ref | string | Git commit SHA or image tag |
| image_tag | string | Built Docker image tag |
| container_port | integer | Snapshot of container_port at deploy time |
| host_port | integer | Snapshot of host_port at deploy time |
| status | enum | `queued`, `building`, `pushing`, `deploying`, `live`, `failed`, `rolled_back` |
| build_logs | text | Build output (reference to MinIO path) |
| deploy_logs | text | Deployment output (reference to MinIO path) |
| created_at | timestamp | When deployment was triggered |
| deployed_at | timestamp | When deployment went live |
| deployed_by | string | User who triggered it |

---

## 5. Deployment Sources

Adhara Engine supports three ways to get a site's Docker image:

### 5.1 Git Repository (Auto-Build)

```
User pushes code → Engine pulls repo → Builds Docker image → Deploys container
```

- Connect a Git repository (GitHub, GitLab, Bitbucket, self-hosted)
- Engine detects framework (Next.js, Astro, Nuxt, Vite, etc.) or uses provided Dockerfile
- Webhook triggers auto-deploy on push to configured branch
- Build happens on the Engine host (or delegated to Cloud Build for cloud targets)

### 5.2 Pre-Built Docker Image (Direct Upload)

```
User builds image locally → Pushes to Engine's registry → Engine deploys container
```

- Tenant builds their own Docker image via their CI/CD pipeline
- Pushes to Engine's built-in container registry (or tags for Engine to pull)
- Engine deploys the provided image directly — no build step

### 5.3 Docker Registry Pull

```
User specifies registry URL + tag → Engine pulls image → Deploys container
```

- Tenant provides a registry URL (Docker Hub, GCR, ECR, GHCR, any OCI-compliant registry)
- Engine stores registry credentials per site (encrypted)
- Engine pulls the specified image and tag
- Supports automatic re-pull on tag update (e.g., `latest` or semver tags)
- Registry credential management per tenant

### 5.4 Code Upload (Tarball/Zip)

```
Client uploads code archive → Engine unpacks → Builds Docker image → Deploys container
```

- Client POSTs a `.tar.gz` or `.zip` archive of project source code to the API
- `POST /api/v1/sites/{id}/deploy` with `source: "upload"` and `Content-Type: multipart/form-data`
- Engine unpacks the archive, detects or uses the provided Dockerfile, and builds the image
- No git repo required — code comes directly from the caller
- Primary use case: AI-powered website builders that generate code programmatically and deploy directly to the engine without an intermediate git step
- Also useful for: drag-and-drop deploy UIs, CI/CD systems that produce source bundles, local directory deploys
- Archive is stored in MinIO for rollback and audit purposes
- Max upload size configurable per tenant (default: 500 MB)

---

## 6. Traffic Routing & SSL

### Traefik Integration

Traefik acts as the edge router, automatically discovering Docker containers and routing traffic:

```
Request flow:
  client → DNS → Engine IP → Traefik → Docker container (port)

Traefik configuration:
  - Docker provider: auto-discovers containers via labels
  - ACME provider: Let's Encrypt for automatic SSL
  - Dynamic routing: hostname → container mapping
```

### Custom Domains

1. Tenant adds custom domain in Engine UI/CLI
2. Engine provides required DNS records (CNAME to engine host, or A record)
3. Tenant configures DNS at their registrar
4. Engine verifies DNS propagation
5. Traefik auto-provisions SSL certificate via Let's Encrypt
6. Traffic routes to the correct container

### Default Domains

Each site gets a default subdomain:
```
{site-slug}.{workspace-slug}.{tenant-slug}.engine.adharaweb.com
```

---

## 7. Multi-Cloud Deployment

### V1 Targets

| Target | Implementation | Use Case |
|--------|---------------|----------|
| **Local Docker** | Docker Engine API | Development, single-server production, small scale |
| **Google Cloud Run** | Cloud Run Admin API v2 | Production, auto-scaling, geographic placement |

### Future Targets (V2+)

| Target | Implementation | Use Case |
|--------|---------------|----------|
| **AWS ECS/Fargate** | AWS SDK | AWS-native customers |
| **Azure Container Apps** | Azure SDK | Azure-native customers |
| **Fly.io** | Fly API | Edge deployment |
| **Kubernetes** | K8s API | Enterprise self-hosted |

### Deploy Target Interface

Each deploy target implements a common interface:

```python
class DeployTarget(ABC):
    async def deploy(self, image: str, config: SiteConfig) -> DeployResult
    async def stop(self, deployment_id: str) -> None
    async def restart(self, deployment_id: str) -> None
    async def logs(self, deployment_id: str, follow: bool) -> AsyncIterator[str]
    async def status(self, deployment_id: str) -> DeployStatus
    async def set_env(self, deployment_id: str, env: dict) -> None
    async def scale(self, deployment_id: str, instances: int) -> None
```

This abstraction allows adding new cloud providers without changing the core engine.

### Kubernetes Readiness (Design Principles)

The engine architecture is designed so it can run on Kubernetes without a rewrite:

1. **`KubernetesDeployTarget`**: Each site becomes a K8s Deployment + Service + Ingress. The `deploy()` method creates/updates these resources via the K8s API. `scale()` adjusts replica count. `logs()` streams pod logs.
2. **Stateless API**: The Engine API is stateless — all state is in PostgreSQL and Redis. This means the API itself can run as a K8s Deployment with horizontal scaling.
3. **Container images in a registry**: All deploy flows push built images to a container registry (local registry in V1, GCR/ECR in production). K8s pulls from the same registry — no change needed.
4. **Config via env vars**: All service configuration uses environment variables, which map directly to K8s ConfigMaps and Secrets.
5. **Traefik on K8s**: Traefik has a native Kubernetes IngressRoute CRD provider, replacing Docker labels with K8s Ingress annotations. Same routing logic, different provider.
6. **Helm chart** (Phase 4): Package the entire engine (API, Zitadel, Traefik, Loki stack) as a Helm chart for one-command K8s deployment.

**Design rules to preserve K8s compatibility:**
- Never depend on Docker socket for core functionality (only for `LocalDeployTarget`)
- Keep the `DeployTarget` interface the only place that touches container orchestration
- Store all persistent state in PostgreSQL/Redis/MinIO, never on local filesystem
- All inter-service communication uses DNS names, not hardcoded IPs

---

## 8. Adhara Web Integration

Each site connects to Adhara Web's backend via environment variables injected at deploy time:

| Variable | Description |
|----------|-------------|
| `ADHARA_API_URL` | Adhara Web REST API base URL |
| `ADHARA_API_KEY` | API key for authentication |
| `ADHARA_WORKSPACE_ID` | Workspace identifier in Adhara Web |
| `ADHARA_PUBLIC_URL` | The site's public-facing URL |

The Engine does **not** tightly couple with Adhara Web internally. Sites communicate with Adhara Web over its public REST API, the same way any custom frontend would. This keeps the architecture decoupled and allows sites to be built with any framework.

---

## 9. Admin Interface

### 9.1 CLI (`adhara-engine`)

Primary management tool for power users and automation.

```bash
# Tenant management
adhara-engine tenant create --name "Acme Corp" --email admin@acme.com
adhara-engine tenant list
adhara-engine tenant delete acme-corp

# Workspace management
adhara-engine workspace create --tenant acme-corp --name "Production"
adhara-engine workspace list --tenant acme-corp

# Site management
adhara-engine site create --workspace acme-prod --name "Main Site" \
  --source git --repo https://github.com/acme/website.git \
  --port 3000 --target local
adhara-engine site create --workspace acme-prod --name "Blog" \
  --source registry --image ghcr.io/acme/blog:latest \
  --port 8080 --target cloud-run --region us-east1
adhara-engine site deploy acme-prod/main-site
adhara-engine site logs acme-prod/main-site --follow
adhara-engine site restart acme-prod/main-site
adhara-engine site stop acme-prod/main-site

# Environment variables (runtime — default, injected via Docker -e)
adhara-engine env set acme-prod/main-site ADHARA_API_KEY=sk_live_xxx
adhara-engine env set acme-prod/main-site STRIPE_SECRET_KEY=sk_live_yyy

# Environment variables (build-time — requires rebuild)
adhara-engine env set acme-prod/main-site NEXT_PUBLIC_SITE_URL=https://acme.com --build
adhara-engine env set acme-prod/main-site NEXT_PUBLIC_GA_ID=G-XXXXXXX --build
# Note: NEXT_PUBLIC_* vars auto-detect as --build scope

adhara-engine env list acme-prod/main-site          # Shows both tiers with scope labels
adhara-engine env unset acme-prod/main-site OLD_VAR

# Domain management
adhara-engine domain add acme-prod/main-site www.acme.com
adhara-engine domain verify acme-prod/main-site www.acme.com
adhara-engine domain list acme-prod/main-site

# Deployment history
adhara-engine deploy list acme-prod/main-site
adhara-engine deploy rollback acme-prod/main-site --to v3

# System
adhara-engine status
adhara-engine logs --system
```

### 9.2 Web UI (React)

Full dashboard for visual management:

**Pages:**
| Page | Features |
|------|----------|
| **Dashboard** | Overview of all tenants, sites, health status, resource usage |
| **Tenant Detail** | Workspaces list, usage metrics, billing info |
| **Workspace Detail** | Sites list, Adhara Web connection config |
| **Site Detail** | Deployment status, logs (real-time streaming), env vars, domains, deploy history |
| **Deploy** | Trigger manual deploy, select source/branch/tag, view build progress |
| **Settings** | Engine configuration, cloud provider credentials, registry auth |
| **Users** | Super admin, admin, and tenant-level user management |

**Access Levels:**
| Role | Scope | Capabilities |
|------|-------|-------------|
| **Super Admin** | Engine-wide | Full access, manage all tenants, system config |
| **Admin** | Engine-wide | Manage tenants and sites, no system config |
| **Tenant Owner** | Own tenant | Manage own workspaces and sites |
| **Tenant Member** | Own tenant | Deploy, view logs, manage env vars |
| **Viewer** | Own tenant | Read-only access |

---

## 10. Key Features (V1)

### 10.1 Container Lifecycle Management
- Start, stop, restart containers
- Health checks and auto-restart on failure
- Graceful shutdown with configurable timeout
- Resource limits (CPU, memory) per site

### 10.2 Port Management & Routing Visibility

The admin interface (CLI and Web UI) provides full visibility into how traffic flows from the internet to each container.

**Port concepts:**
```
Internet → Traefik (ports 80/443) → Host Port (e.g., 3047) → Container Port (e.g., 3000)
              ↑                          ↑                         ↑
         Public entry              Auto-assigned or           What the app
         (shared by all)           manually set per site      listens on inside
                                                              the container
```

**Routing table view (CLI + Web UI):**
```
$ adhara-engine ports

TENANT       WORKSPACE    SITE          CONTAINER PORT  HOST PORT  DOMAINS                    STATUS
─────────────────────────────────────────────────────────────────────────────────────────────────────
acme-corp    production   main-site     3000            3001       acme.com, www.acme.com     running
acme-corp    staging      main-site     3000            3002       staging.acme.com           running
beta-inc     production   storefront    5173            3003       shop.beta.com              running
beta-inc     production   blog          8080            3004       blog.beta.com              stopped
```

**Port management features:**
- **Auto-assignment:** Host ports auto-assigned from configurable pool (default: 3001-4000)
- **Manual override:** Admins can set a specific host port via CLI or Web UI
- **Conflict detection:** Engine prevents two sites from using the same host port
- **Port change:** Changing a port triggers a container restart with the new mapping
- **Container port detection:** For common frameworks, auto-detect the container port:
  - Next.js → 3000
  - Vite → 5173
  - Nuxt → 3000
  - Astro → 4321
  - Express/Fastify → 3000
  - Custom → must be specified or read from Dockerfile EXPOSE

**CLI commands:**
```bash
# View all port mappings across all sites
adhara-engine ports

# View ports for a specific tenant
adhara-engine ports --tenant acme-corp

# Change a site's container port (app changed what port it listens on)
adhara-engine site set-port acme-corp/production/main-site --container-port 8080

# Change a site's host port (manual override)
adhara-engine site set-port acme-corp/production/main-site --host-port 3050

# Check for port conflicts
adhara-engine ports --check-conflicts
```

**Web UI — Site Detail page:**
The Site Detail page shows a routing diagram:
```
┌─────────────────────────────────────────────────────┐
│  Routing                                             │
│                                                      │
│  acme.com ──→ Traefik :443 ──→ :3001 ──→ :3000     │
│  www.acme.com ──→ Traefik :443 ──→ :3001 ──→ :3000 │
│                                                      │
│  Container Port: [3000] ✏️   Host Port: [3001] ✏️    │
│  Port Pool: 3001-4000       Status: ● Running       │
└─────────────────────────────────────────────────────┘
```

**API endpoints:**
```
GET    /api/v1/ports                           # All port mappings (admin view)
GET    /api/v1/ports?tenant_id={id}            # Filtered by tenant
PATCH  /api/v1/sites/{id}/ports                # Update container_port and/or host_port
```

### 10.3 Environment Variable Management

Sites have **two tiers** of environment variables:

#### Runtime Env Vars (`runtime_env`)
- Injected into the container via Docker `-e` flags at start time
- Available to server-side code via `process.env`
- **Changing a runtime var → container restart (seconds)**
- Examples: `STRIPE_SECRET_KEY`, `AUTH_SECRET`, `ADHARA_API_URL`, `ADHARA_API_KEY`

#### Build-time Env Vars (`build_env`)
- Passed as `--build-arg` during `docker build`
- Inlined into the JavaScript bundle by the framework's bundler at build time
- **Changing a build var → full rebuild + redeploy required (minutes)**
- The CLI/UI must warn the user when a build var change requires a rebuild
- Examples: `NEXT_PUBLIC_SITE_URL`, `NEXT_PUBLIC_GA_ID`, `NEXT_PUBLIC_GTM_ID`

#### Auto-detection
- Vars starting with `NEXT_PUBLIC_` default to `build_env` scope
- All other vars default to `runtime_env` scope
- Users can override the scope explicitly via CLI flag or UI toggle

#### Behavior
- Encrypted storage (AES-256) for both tiers
- Env var inheritance from workspace level (both tiers)
- Auto-inject Adhara Web connection vars as `runtime_env` (they're server-side)
- `PUT /api/v1/sites/{id}/env` accepts `scope` parameter: `build` or `runtime`
- When a `build_env` var is changed, the API returns a warning that a rebuild is needed and does NOT auto-deploy — the user must explicitly trigger `POST /sites/{id}/deploy`

### 10.3 Deployment Pipeline
- Build queue with concurrency limits
- Build caching (Docker layer cache)
- Zero-downtime deployments (blue-green for local, native for Cloud Run)
- Rollback to any previous deployment
- Deploy previews (per-branch deployments with preview URLs)

### 10.4 Logging & Monitoring
- Real-time log streaming (stdout/stderr)
- Log persistence and search
- Container health metrics (CPU, memory, network)
- Deployment event timeline
- Webhook notifications on deploy success/failure

### 10.5 Multi-Cloud Orchestration
- Unified interface across local Docker and Cloud Run
- Region selection per site
- Deploy target migration (move a site from local to Cloud Run)
- Cloud provider credential management (encrypted)

### 10.6 Extensible Deployment Pipeline

The deployment pipeline is built as an ordered sequence of **stages**, each with **injection points** where custom steps can be added. This allows the pipeline to evolve over time — adding security scanning, linting, testing, notifications, or any custom logic — without modifying the core engine.

#### Default Pipeline Stages

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  SOURCE  │───▶│  PREPARE │───▶│  BUILD   │───▶│  PUBLISH │───▶│  DEPLOY  │
│          │    │          │    │          │    │          │    │          │
│ Pull code│    │ Install  │    │ Docker   │    │ Push to  │    │ Start    │
│ or image │    │ deps,    │    │ build    │    │ registry │    │ container│
│          │    │ validate │    │          │    │          │    │ + route  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
      │               │               │               │               │
   pre/post        pre/post        pre/post        pre/post        pre/post
   hooks           hooks           hooks           hooks           hooks
```

#### Injection Points

Every stage exposes `pre_` and `post_` hooks where custom steps run:

| Hook | Runs | Example Use Cases |
|------|------|-------------------|
| `pre_source` | Before fetching code/image | Auth check, quota validation |
| `post_source` | After code is available locally | **Security scan**, license check, secret detection |
| `pre_prepare` | Before dependency install | Lock file validation |
| `post_prepare` | After deps installed | Dependency vulnerability scan (e.g., `pnpm audit`) |
| `pre_build` | Before Docker build | Inject build-time configs |
| `post_build` | After image is built | Image vulnerability scan (Trivy, Snyk), size check |
| `pre_publish` | Before pushing to registry | Image signing, attestation |
| `post_publish` | After image is in registry | Notify artifact system |
| `pre_deploy` | Before container starts | Smoke test config, warm caches |
| `post_deploy` | After container is live | Health check, integration tests, Slack notification |

#### Step Definition

Each custom step is a Docker container or script with a standard interface:

```yaml
# Example: Security scanner step
steps:
  - name: snyk-code-scan
    stage: post_source
    image: snyk/snyk-cli:latest
    command: ["snyk", "test", "--all-projects"]
    timeout: 300s
    fail_behavior: block    # block | warn | log
    env:
      SNYK_TOKEN: ${SNYK_TOKEN}

  - name: trivy-image-scan
    stage: post_build
    image: aquasec/trivy:latest
    command: ["trivy", "image", "--exit-code", "1", "--severity", "CRITICAL", "$IMAGE"]
    timeout: 120s
    fail_behavior: block

  - name: slack-notify
    stage: post_deploy
    image: curlimages/curl:latest
    command: ["curl", "-X", "POST", "$SLACK_WEBHOOK", "-d", "{\"text\": \"Deployed $SITE\"}"]
    timeout: 30s
    fail_behavior: log
```

#### Step Configuration Scope

Steps can be configured at multiple levels, with lower levels inheriting and overriding:

```
Engine-wide defaults (all sites get these)
  └── Tenant-level overrides (all sites for this tenant)
       └── Workspace-level overrides (all sites in this workspace)
            └── Site-level overrides (this specific site)
```

#### Fail Behaviors

| Behavior | Effect |
|----------|--------|
| `block` | Step failure stops the pipeline. Deployment fails. |
| `warn` | Step failure logs a warning. Pipeline continues. Deployment marked with warning. |
| `log` | Step failure is logged silently. Pipeline continues normally. |

#### Pipeline Execution Model

- Steps within a stage run **sequentially** by default (order matters for scanning)
- Steps can be marked `parallel: true` to run concurrently within the same hook point
- Each step receives the pipeline context (source path, image tag, site config, previous step outputs)
- Step output (stdout/stderr) is captured in deployment logs
- Steps have configurable timeouts with sensible defaults
- Steps can pass artifacts/data to subsequent steps via a shared pipeline context

#### CLI Integration

```bash
# List pipeline steps for a site
adhara-engine pipeline list acme-prod/main-site

# Add a step
adhara-engine pipeline add acme-prod/main-site \
  --name snyk-scan \
  --stage post_source \
  --image snyk/snyk-cli:latest \
  --command "snyk test" \
  --fail-behavior block

# Remove a step
adhara-engine pipeline remove acme-prod/main-site snyk-scan

# Disable a step without removing it
adhara-engine pipeline disable acme-prod/main-site snyk-scan

# Test a step in dry-run mode
adhara-engine pipeline test acme-prod/main-site snyk-scan

# View step execution history
adhara-engine pipeline history acme-prod/main-site
```

---

## 11. Security

| Area | Approach |
|------|----------|
| **Secrets** | All API keys, env vars, registry credentials encrypted at rest (AES-256-GCM) |
| **Authentication** | Zitadel (self-hosted OIDC/OAuth2 provider): Google OAuth, passkeys/WebAuthn, email/password. API keys and service account tokens for CLI and machine-to-machine (AI builder) |
| **Authorization** | Zitadel RBAC with organization-level roles. 1 Zitadel Organization = 1 Engine Tenant. Roles: Super Admin, Tenant Owner, Member, Viewer |
| **Network** | Traefik enforces HTTPS. Internal container network isolated per tenant |
| **Registry Auth** | Credentials stored encrypted, scoped per tenant |
| **Audit Log** | All admin actions logged with actor, timestamp, and details |
| **Container Isolation** | Containers run with minimal privileges, no host network access |

---

## 12. Configuration

### Engine Configuration (`adhara-engine.yaml`)

```yaml
engine:
  host: 0.0.0.0
  port: 8000
  secret_key: ${ENGINE_SECRET_KEY}

database:
  url: postgresql://user:pass@localhost:5432/adhara_engine

redis:
  url: redis://localhost:6379

traefik:
  api_url: http://localhost:8080
  acme_email: ssl@adharaweb.com

docker:
  socket: ${DOCKER_HOST:-/var/run/docker.sock}  # Works with OrbStack, Docker Desktop, Podman, etc.
  network: adhara-engine-net
  registry: localhost:5000  # built-in registry

cloud_providers:
  google_cloud:
    project_id: ${GCP_PROJECT_ID}
    credentials_file: ${GCP_CREDENTIALS_FILE}

defaults:
  deploy_target: local
  container_memory: 512Mi
  container_cpu: 0.5
  health_check_interval: 30s
  auto_restart: true
```

---

## 13. Local-First Development & Deployment

Adhara Engine is designed to run locally first — on your laptop or a single VM — with zero cloud dependencies for V1. Everything spins up with a single `make` command.

### Prerequisites

- Any Docker-compatible runtime: OrbStack, Docker Desktop, Docker Engine, Podman, Colima, or Rancher Desktop — anything that provides the Docker CLI and Docker Compose. The engine uses the standard Docker API (`/var/run/docker.sock`) and does not depend on any specific Docker distribution.
- Python 3.11+ (for API development)
- Node.js 20+ (for Web UI development)
- Make

### Makefile

The Makefile is the single entry point for all operations:

```makefile
# ============================================================
# Adhara Engine - Makefile
# ============================================================

.PHONY: up down restart status logs clean build dev db-migrate db-seed cli-install

# ── Lifecycle ────────────────────────────────────────────────

up:                     ## Start everything (API, UI, Traefik, DB, Redis, Registry)
	docker compose up -d
	@echo "Adhara Engine running at http://localhost:8000"
	@echo "Web UI at http://localhost:3000"
	@echo "Traefik dashboard at http://localhost:8080"

down:                   ## Stop everything
	docker compose down

restart:                ## Restart all services
	docker compose restart

clean:                  ## Stop everything and remove volumes (DESTRUCTIVE)
	docker compose down -v --remove-orphans
	docker system prune -f

# ── Development ──────────────────────────────────────────────

dev:                    ## Start in dev mode (hot reload for API + UI)
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

build:                  ## Rebuild all images
	docker compose build --no-cache

# ── Database ─────────────────────────────────────────────────

db-migrate:             ## Run database migrations
	docker compose exec api alembic upgrade head

db-seed:                ## Seed database with sample data
	docker compose exec api python scripts/seed.py

db-reset:               ## Reset database (DESTRUCTIVE)
	docker compose exec api alembic downgrade base
	docker compose exec api alembic upgrade head

# ── CLI ──────────────────────────────────────────────────────

cli-install:            ## Install the CLI tool locally
	pip install -e ./cli

# ── Monitoring ───────────────────────────────────────────────

status:                 ## Show status of all services
	docker compose ps

logs:                   ## Tail logs from all services
	docker compose logs -f

logs-api:               ## Tail API logs only
	docker compose logs -f api

logs-traefik:           ## Tail Traefik logs only
	docker compose logs -f traefik

# ── Testing ──────────────────────────────────────────────────

test:                   ## Run all tests
	docker compose exec api pytest
	cd ui && pnpm test

test-api:               ## Run API tests only
	docker compose exec api pytest

test-ui:                ## Run UI tests only
	cd ui && pnpm test

# ── Shortcuts ────────────────────────────────────────────────

init: up db-migrate db-seed cli-install   ## First-time setup: start, migrate, seed, install CLI
	@echo ""
	@echo "========================================="
	@echo "  Adhara Engine is ready!"
	@echo "  API:     http://localhost:8000"
	@echo "  Web UI:  http://localhost:3000"
	@echo "  CLI:     adhara-engine --help"
	@echo "========================================="

help:                   ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
```

### Quick Start

```bash
git clone https://github.com/eim-internal/adhara-engine.git
cd adhara-engine
make init    # That's it. Everything starts, migrates, seeds, and installs the CLI.
```

### Docker Compose Architecture

```yaml
# docker-compose.yml
services:
  api:
    build: ./api
    ports: ["8000:8000"]
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock  # Engine manages Docker containers
      - ./api:/app                                  # Dev: hot reload
    environment:
      - DATABASE_URL=postgresql://engine:engine@db:5432/adhara_engine
      - REDIS_URL=redis://redis:6379
      - ENGINE_SECRET_KEY=${ENGINE_SECRET_KEY:-dev-secret-change-me}
    depends_on: [db, redis]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      retries: 3

  ui:
    build: ./ui
    ports: ["3000:3000"]
    environment:
      - API_URL=http://api:8000
    depends_on: [api]

  traefik:
    image: traefik:v3
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"   # Traefik dashboard
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./traefik/traefik.yml:/etc/traefik/traefik.yml
      - ./traefik/dynamic:/etc/traefik/dynamic
      - traefik-certs:/letsencrypt
    depends_on: [api]

  db:
    image: postgres:16-alpine
    ports: ["5432:5432"]
    environment:
      - POSTGRES_USER=engine
      - POSTGRES_PASSWORD=engine
      - POSTGRES_DB=adhara_engine
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  registry:
    image: registry:2
    ports: ["5000:5000"]
    volumes:
      - registry-data:/var/lib/registry

  # Object storage for deployment logs and backups
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"    # S3 API
      - "9001:9001"    # Console
    environment:
      - MINIO_ROOT_USER=engine
      - MINIO_ROOT_PASSWORD=engine-secret
    volumes:
      - minio-data:/data

  # Logging stack
  alloy:
    image: grafana/alloy:latest
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./alloy/config.alloy:/etc/alloy/config.alloy
    depends_on: [loki]

  loki:
    image: grafana/loki:latest
    ports: ["3100:3100"]
    volumes:
      - loki-data:/loki

  grafana:
    image: grafana/grafana:latest
    ports: ["3001:3000"]
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-data:/var/lib/grafana
    depends_on: [loki]

  # Authentication & Identity (Zitadel)
  zitadel:
    image: ghcr.io/zitadel/zitadel:latest
    command: start-from-init --masterkeyFromEnv --tlsMode disabled
    ports: ["8081:8080"]
    environment:
      - ZITADEL_MASTERKEY=${ZITADEL_MASTERKEY:-MasterkeyNeedsToHave32Characters}
      - ZITADEL_DATABASE_POSTGRES_HOST=db
      - ZITADEL_DATABASE_POSTGRES_PORT=5432
      - ZITADEL_DATABASE_POSTGRES_DATABASE=zitadel
      - ZITADEL_DATABASE_POSTGRES_USER_USERNAME=zitadel
      - ZITADEL_DATABASE_POSTGRES_USER_PASSWORD=zitadel
      - ZITADEL_DATABASE_POSTGRES_USER_SSL_MODE=disable
      - ZITADEL_DATABASE_POSTGRES_ADMIN_USERNAME=engine
      - ZITADEL_DATABASE_POSTGRES_ADMIN_PASSWORD=engine
      - ZITADEL_DATABASE_POSTGRES_ADMIN_SSL_MODE=disable
      - ZITADEL_EXTERNALSECURE=false
      - ZITADEL_EXTERNALPORT=8081
      - ZITADEL_EXTERNALDOMAIN=localhost
    depends_on: [db]
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:8080/debug/healthz"]
      interval: 10s
      retries: 5

volumes:
  pgdata:
  registry-data:
  traefik-certs:
  minio-data:
  loki-data:
  grafana-data:
```

### Project Structure

```
adhara-engine/
├── Makefile                    # Single entry point for all operations
├── docker-compose.yml          # Production-like local setup
├── docker-compose.dev.yml      # Dev overrides (hot reload, debug ports)
├── .env.example                # Environment variable template
├── api/                        # FastAPI backend
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/                # Database migrations
│   ├── app/
│   │   ├── main.py
│   │   ├── models/             # SQLAlchemy models
│   │   ├── routers/            # API endpoints
│   │   ├── services/           # Business logic
│   │   │   ├── container.py    # Docker container management
│   │   │   ├── deployer.py     # Deployment orchestration
│   │   │   ├── pipeline.py     # Extensible pipeline engine
│   │   │   └── cloud/          # Cloud provider adapters
│   │   │       ├── base.py     # DeployTarget ABC
│   │   │       ├── local.py    # Local Docker target
│   │   │       └── cloudrun.py # Cloud Run target
│   │   ├── schemas/            # Pydantic models
│   │   └── core/               # Config, security, DB
│   ├── tests/
│   └── scripts/
│       └── seed.py
├── ui/                         # React frontend
│   ├── Dockerfile
│   ├── package.json
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   └── api/                # API client
│   └── tests/
├── cli/                        # Python CLI (Typer)
│   ├── setup.py
│   ├── adhara_engine/
│   │   ├── __init__.py
│   │   ├── main.py             # CLI entry point
│   │   ├── commands/           # Command groups
│   │   │   ├── tenant.py
│   │   │   ├── workspace.py
│   │   │   ├── site.py
│   │   │   ├── deploy.py
│   │   │   ├── env.py
│   │   │   ├── domain.py
│   │   │   └── pipeline.py
│   │   └── client.py           # HTTP client to Engine API
│   └── tests/
└── traefik/                    # Traefik configuration
    ├── traefik.yml
    └── dynamic/
```

---

## 14. API Design (Key Endpoints)

```
# Tenants
POST   /api/v1/tenants
GET    /api/v1/tenants
GET    /api/v1/tenants/{tenant_id}
PATCH  /api/v1/tenants/{tenant_id}
DELETE /api/v1/tenants/{tenant_id}

# Workspaces
POST   /api/v1/tenants/{tenant_id}/workspaces
GET    /api/v1/tenants/{tenant_id}/workspaces
GET    /api/v1/workspaces/{workspace_id}
PATCH  /api/v1/workspaces/{workspace_id}
DELETE /api/v1/workspaces/{workspace_id}

# Sites
POST   /api/v1/workspaces/{workspace_id}/sites
GET    /api/v1/workspaces/{workspace_id}/sites
GET    /api/v1/sites/{site_id}
PATCH  /api/v1/sites/{site_id}
DELETE /api/v1/sites/{site_id}

# Deployments
POST   /api/v1/sites/{site_id}/deploy
GET    /api/v1/sites/{site_id}/deployments
POST   /api/v1/sites/{site_id}/rollback
POST   /api/v1/sites/{site_id}/restart
POST   /api/v1/sites/{site_id}/stop

# Ports
GET    /api/v1/ports                              # All port mappings (admin routing table)
GET    /api/v1/ports?tenant_id={tenant_id}         # Filtered by tenant
PATCH  /api/v1/sites/{site_id}/ports               # Update container_port / host_port

# Environment Variables
GET    /api/v1/sites/{site_id}/env
PUT    /api/v1/sites/{site_id}/env
DELETE /api/v1/sites/{site_id}/env/{key}

# Domains
POST   /api/v1/sites/{site_id}/domains
GET    /api/v1/sites/{site_id}/domains
DELETE /api/v1/sites/{site_id}/domains/{domain}
POST   /api/v1/sites/{site_id}/domains/{domain}/verify

# Logs
GET    /api/v1/sites/{site_id}/logs
GET    /api/v1/sites/{site_id}/logs/stream  (WebSocket)

# System
GET    /api/v1/system/status
GET    /api/v1/system/health
```

---

## 15. Milestones

### Phase 1: Foundation (MVP)
- [ ] Project structure, Makefile, Docker Compose (`make init` works end-to-end)
- [ ] Engine API with tenant/workspace/site CRUD
- [ ] Local Docker deployment (build from Dockerfile, run container)
- [ ] Pre-built image deployment (pull and run)
- [ ] Docker registry pull deployment
- [ ] Traefik integration (dynamic routing, auto-SSL)
- [ ] Environment variable management
- [ ] CLI tool (full command set via Typer)
- [ ] Basic Web UI (dashboard, site management, logs)
- [ ] PostgreSQL + Redis setup with Alembic migrations
- [ ] Container lifecycle (start, stop, restart, health checks)
- [ ] Default deployment pipeline (source → prepare → build → publish → deploy)

### Phase 2: Production Ready
- [ ] Google Cloud Run deployment target
- [ ] Git webhook auto-deploy
- [ ] Framework auto-detection and build
- [ ] Zero-downtime deployments (blue-green)
- [ ] Deployment rollback
- [ ] Custom domain management with auto-SSL
- [ ] RBAC and multi-user auth
- [ ] Audit logging
- [ ] Build caching
- [ ] Extensible pipeline: custom steps at pre/post hooks per stage
- [ ] Pipeline step marketplace (curated security scanning, notification steps)

### Phase 3: Scale
- [ ] AWS ECS/Fargate deployment target
- [ ] Azure Container Apps deployment target
- [ ] Deploy previews (per-branch)
- [ ] Resource usage monitoring and alerts
- [ ] Webhook notifications (Slack, email)
- [ ] Tenant billing/usage tracking
- [ ] API rate limiting
- [ ] Multi-region Traefik (for distributed deployments)

### Phase 4: Enterprise
- [ ] Kubernetes deployment target
- [ ] SSO/SAML authentication
- [ ] Compliance (SOC2, audit trails)
- [ ] White-label engine UI
- [ ] Terraform/Pulumi provider
- [ ] GitOps workflow (declarative site config)

---

## 16. Success Metrics

| Metric | Target |
|--------|--------|
| Deploy time (local) | < 60 seconds from trigger to live |
| Deploy time (Cloud Run) | < 120 seconds from trigger to live |
| Routing latency (Traefik overhead) | < 5ms added |
| Uptime (engine management plane) | 99.9% |
| Sites per engine instance | 100+ on a single server |
| Time to onboard new tenant | < 5 minutes via CLI |

---

## 17. Resolved Design Decisions

### 17.1 Build Infrastructure

**Decision:** Both local and cloud.

- **V1:** Builds happen on the Engine host using Docker Engine directly. Simple, no cloud dependency.
- **V2+:** Optionally offload to Google Cloud Build for cloud-targeted deployments. Engine detects the deploy target and routes builds accordingly — local Docker build for `local` targets, Cloud Build for `cloud_run` targets.

### 17.2 Database Multi-Tenancy

**Decision:** Shared schema with Row-Level Security (RLS).

All tenants share the same PostgreSQL tables with a `tenant_id` column on every table. RLS policies enforce isolation at the database level as defense-in-depth (the API also enforces tenant scoping via auth middleware).

**Why this approach:**
- Simplest Alembic migrations — one `alembic upgrade head`, all tenants updated atomically
- Trivial connection pooling — one pool, one database
- Easy cross-tenant admin queries for super-admin dashboards
- Tenant creation is near-instant (just INSERT, no schema provisioning)
- Adequate for the metadata-heavy, low-volume-per-tenant data pattern of a deployment platform

**Deployment logs externalized:**
Build logs and deploy logs (`build_logs`, `deploy_logs` on the Deployment table) will be stored in object storage (MinIO locally, S3/GCS in cloud) rather than in PostgreSQL. The Deployment row stores only a reference (object key/path). This keeps PostgreSQL tables small and fast.

```
Deployment.build_logs    → MinIO: /logs/{tenant}/{site}/{deploy_id}/build.log
Deployment.deploy_logs   → MinIO: /logs/{tenant}/{site}/{deploy_id}/deploy.log
```

### 17.3 Billing & Pricing

**Decision:** Dual billing — via Adhara Web AND natively in the Engine.

The Engine supports two billing modes that can be used independently or together:

**Mode 1: Adhara Web Billing (delegated)**
- Billing flows through Adhara Web's existing Stripe integration
- Engine reports usage metrics (sites, deployments, compute hours) to Adhara Web via API
- Adhara Web handles invoicing, payment collection, plan management
- Best for tenants already on Adhara Web

**Mode 2: Native Engine Billing (standalone)**
- Engine has its own Stripe integration for standalone deployments
- Supports per-tenant subscription plans with metered add-ons
- Useful when Engine runs independently of Adhara Web

**Pricing dimensions (configurable per deployment):**

| Dimension | Description |
|-----------|-------------|
| **Per tenant** | Base subscription fee per tenant/company |
| **Per site** | Charge per active site (running container) |
| **Per deployment** | Charge per deployment triggered (or included quota) |
| **Compute hours** | Metered CPU/memory usage per container |
| **Add-ons** | Extra charges for: additional domains, priority support, Cloud Run targets, pipeline steps |

### 17.4 Backup Strategy

**Decision:** Automated `pg_dump` + Docker volume snapshots.

| Component | Backup Method | Schedule | Storage |
|-----------|--------------|----------|---------|
| **Engine metadata** (PostgreSQL) | `pg_dump` to compressed SQL | Daily (configurable) | Object storage (MinIO/S3/GCS) |
| **Deployment logs** | Already in object storage | N/A (native durability) | MinIO/S3/GCS |
| **Container registry** | Volume snapshot | Daily | Local or object storage |
| **Traefik config/certs** | Volume snapshot | Daily | Local or object storage |
| **Engine config** | Git-tracked (`adhara-engine.yaml`) | On change | Git repository |

**Makefile targets:**
```bash
make backup           # Run all backups
make backup-db        # PostgreSQL dump only
make backup-registry  # Registry volume snapshot
make restore-db       # Restore from latest pg_dump
make restore-db FILE=backup-2026-02-18.sql.gz  # Restore specific backup
```

**Retention:** 7 daily backups + 4 weekly backups (configurable). Old backups auto-purged.

### 17.5 CDN Integration

**Decision:** No CDN in V1. Traefik handles everything directly.

- V1: Traefik serves as both reverse proxy and edge — handles SSL, routing, and caching headers
- V2+: Add CDN as a pluggable option. **Bunny CDN** is the recommended first integration ($0.01/GB, 123 PoPs, full REST API, auto-SSL). Engine would programmatically create CDN zones per site via Bunny's API.
- The CDN layer will be abstracted behind a `CdnProvider` interface so additional providers (Fastly, CloudFront) can be added later

### 17.6 Logging Stack

**Decision:** Loki + Grafana + Grafana Alloy (open-source).

```
Docker containers → Grafana Alloy (collector) → Loki (storage) → Grafana (UI)
```

| Component | Role | Resource Usage |
|-----------|------|----------------|
| **Grafana Alloy** | Collects container logs via Docker socket, replaces deprecated Promtail | ~50MB RAM |
| **Loki** | Log storage engine — indexes metadata only, stores logs compressed | ~100MB RAM |
| **Grafana** | Web UI for log search, dashboards, alerting | ~100MB RAM |

**Why Loki over Graylog/OpenSearch:**
- 10x lower storage cost (indexes labels, not full text)
- ~250MB total RAM vs 1.5GB+ for Graylog (which requires OpenSearch + MongoDB)
- Docker Compose native — just add 3 services
- Grafana provides dashboards for both logs AND container metrics
- Log retention configurable per-tenant via Loki's retention policies

**Added to Docker Compose:**
```yaml
services:
  alloy:
    image: grafana/alloy:latest
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./alloy/config.alloy:/etc/alloy/config.alloy
    depends_on: [loki]

  loki:
    image: grafana/loki:latest
    ports: ["3100:3100"]
    volumes:
      - loki-data:/loki

  grafana:
    image: grafana/grafana:latest
    ports: ["3001:3000"]
    volumes:
      - grafana-data:/var/lib/grafana
    depends_on: [loki]
```

**Log retention:** Configurable via Loki retention policies. Default: 30 days for build logs, 7 days for runtime logs. Adjustable per-tenant as a billing dimension.

---

## 18. Remaining Open Questions

1. **Log retention pricing:** Should extended log retention (beyond 30 days) be a paid add-on?
2. ~~**SSO for V1:**~~ **RESOLVED:** Zitadel provides OAuth/OIDC (Google login), passkeys/WebAuthn, email/password, and service account tokens from V1. Zitadel Organizations map 1:1 to Engine Tenants.
3. **Monitoring/alerting:** Should Grafana also be used for container health metrics (CPU, memory), or keep that separate?
4. **White-label:** Should tenants be able to see the Grafana dashboards for their own sites, or only super-admins?
