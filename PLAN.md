# Adhara Engine - Implementation Plan

**Status:** In Progress
**Started:** 2026-02-18
**Goal:** Deploy Next.js/Vite frontend containers locally and on GCP VMs, connected to Adhara Web backend

---

## Phase 1: Foundation (Current Focus)

The goal of Phase 1 is: `make init` works, you can deploy a Next.js app in a Docker container, access it via Traefik, and manage everything via CLI.

---

### Step 1: Project Scaffold
**Status:** [x] Complete
**Estimated:** 1 session

Set up the project structure, Docker Compose, and Makefile so `make init` boots the entire engine.

**Tasks:**
- [ ] Create project directory structure (api/, ui/, cli/, traefik/, alloy/, zitadel/)
- [ ] Create `docker-compose.yml` with all services (API, DB, Redis, Traefik, MinIO, Loki, Grafana, Alloy, Registry, Zitadel)
- [ ] Create `docker-compose.dev.yml` with dev overrides (hot reload, debug ports)
- [ ] Create `Makefile` with all targets (init, up, down, dev, build, logs, status, etc.)
- [ ] Create `.env.example` with all required environment variables
- [ ] Create `traefik/traefik.yml` base configuration (Docker provider, entrypoints, ACME)
- [ ] Create `alloy/config.alloy` for Docker log collection to Loki
- [ ] Verify: `make init` starts all services, `make status` shows all healthy

**Docker runtime note:** The engine is runtime-agnostic — it works with OrbStack, Docker Desktop, Docker Engine, Podman, Colima, or any runtime that provides the Docker CLI, Docker Compose, and the Docker socket (`/var/run/docker.sock` or equivalent). No dependency on Docker Desktop specifically.

**Done when:** `make init` boots PostgreSQL, Redis, Traefik, MinIO, Loki, Grafana, Alloy, Zitadel, and the API container. All services are healthy. Traefik dashboard is accessible at `http://localhost:8080`. Zitadel console is accessible at `http://localhost:8081`.

---

### Step 2: Database Models & API Scaffold
**Status:** [x] Complete
**Estimated:** 1 session
**Depends on:** Step 1

Create the FastAPI application with SQLAlchemy models, Alembic migrations, and basic CRUD endpoints.

**Tasks:**
- [ ] Set up FastAPI app structure (`app/main.py`, routers, services, models, schemas, core)
- [ ] Configure Zitadel integration:
  - [ ] Create Zitadel project and API application via Zitadel console or management API
  - [ ] Configure Google OAuth identity provider in Zitadel
  - [ ] Enable passkeys/WebAuthn login in Zitadel
  - [ ] Map Zitadel Organizations 1:1 to Engine Tenants
  - [ ] Define roles in Zitadel: `super_admin`, `tenant_owner`, `member`, `viewer`
  - [ ] Create service account for API-to-Zitadel communication
- [ ] Implement FastAPI auth middleware:
  - [ ] Validate Zitadel OIDC tokens (JWT verification via Zitadel JWKS endpoint)
  - [ ] Extract tenant/org context from token claims
  - [ ] Role-based route guards (decorators for required roles)
  - [ ] Service account token validation for M2M (CLI, AI builder)
- [ ] Create SQLAlchemy models: Tenant, Workspace, Site, Deployment
- [ ] Add `tenant_id` column on all tenant-scoped tables
- [ ] Set up Alembic with initial migration
- [ ] Implement PostgreSQL Row-Level Security policies
- [ ] Create Pydantic schemas for all entities
- [ ] Implement CRUD routers:
  - [ ] `POST/GET/PATCH/DELETE /api/v1/tenants`
  - [ ] `POST/GET /api/v1/tenants/{id}/workspaces`
  - [ ] `POST/GET /api/v1/workspaces/{id}/sites`
  - [ ] `GET/PATCH/DELETE /api/v1/sites/{id}`
- [ ] Implement two-tier environment variable system:
  - [ ] `runtime_env` (jsonb) and `build_env` (jsonb) columns on Site model
  - [ ] `health_check_path` column on Site model (default: `/api/health`)
  - [ ] `GET /api/v1/sites/{id}/env` — returns both tiers with scope labels
  - [ ] `PUT /api/v1/sites/{id}/env` — accepts `scope` param (`build` or `runtime`)
  - [ ] `DELETE /api/v1/sites/{id}/env/{key}` — removes from either tier
  - [ ] Auto-detect: `NEXT_PUBLIC_*` keys default to `build` scope
  - [ ] Return warning when `build_env` var changes (rebuild required)
- [ ] Add health check endpoint (`GET /health`)
- [ ] Create seed script with sample tenant/workspace/site data
- [ ] Verify: `make db-migrate` runs clean, `make db-seed` populates data, API returns CRUD responses

**Done when:** API starts, migrations run, seed data loads, and you can create a Tenant > Workspace > Site hierarchy via curl/httpie. Env vars can be set on a site.

---

### Step 3: Container Manager (Local Docker)
**Status:** [x] Complete
**Estimated:** 1-2 sessions
**Depends on:** Step 2

The core capability: build and run Docker containers for frontend sites.

**Tasks:**
- [ ] Implement `ContainerManager` service using Docker SDK for Python (`docker` package)
- [ ] Implement `LocalDeployTarget` (implements `DeployTarget` ABC):
  - [ ] `deploy()` — pull/build image, create container with env vars, start it
  - [ ] `stop()` — stop container gracefully
  - [ ] `restart()` — restart container
  - [ ] `logs()` — stream container stdout/stderr
  - [ ] `status()` — check container state (running, stopped, error)
  - [ ] `set_env()` — update runtime env vars and restart container
- [ ] Support four deployment sources:
  - [ ] **Git repo**: clone repo, build Docker image from Dockerfile
  - [ ] **Pre-built image**: use provided image tag directly
  - [ ] **Registry pull**: pull from Docker Hub/GCR/GHCR with optional auth
  - [ ] **Code upload**: accept tarball/zip via API, unpack, build image (for AI builders, drag-and-drop UIs)
- [ ] Auto-detect Dockerfile location (root, or `source_config.dockerfile_path`)
- [ ] Two-tier env var injection:
  - [ ] **Build-time (`build_env`)**: pass as `--build-arg` flags during `docker build`
  - [ ] **Runtime (`runtime_env`)**: inject via Docker `-e` flags at container start
  - [ ] Adhara Web vars (`ADHARA_API_URL`, `ADHARA_API_KEY`, `ADHARA_WORKSPACE_ID`, `ADHARA_PUBLIC_URL`) injected as runtime env
  - [ ] Plus any custom env vars from both tiers on the Site
  - [ ] Changing `runtime_env` → restart container (fast)
  - [ ] Changing `build_env` → warn user, require explicit redeploy (rebuild)
- [ ] Assign dynamic port from configurable range (3001-4000)
- [ ] Container naming convention: `ae-{tenant_slug}-{workspace_slug}-{site_slug}`
- [ ] Connect containers to the `adhara-engine-net` Docker network
- [ ] **Port management:**
  - [ ] Auto-assign host ports from configurable pool (default: 3001-4000)
  - [ ] Track `container_port` (what the app listens on) and `host_port` (mapped on host) per site
  - [ ] Auto-detect container port for common frameworks (Next.js=3000, Vite=5173, etc.)
  - [ ] Conflict detection — prevent two sites from using the same host port
  - [ ] `GET /api/v1/ports` — admin routing table showing all port mappings
  - [ ] `PATCH /api/v1/sites/{id}/ports` — change container or host port (triggers restart)
- [ ] Implement deployment endpoints:
  - [ ] `POST /api/v1/sites/{id}/deploy`
  - [ ] `POST /api/v1/sites/{id}/stop`
  - [ ] `POST /api/v1/sites/{id}/restart`
  - [ ] `GET /api/v1/sites/{id}/logs`
- [ ] Snapshot port assignments on Deployment record
- [ ] Create Deployment records with status tracking
- [ ] Store build/deploy logs in MinIO (not PostgreSQL)
- [ ] Verify: deploy a sample Next.js app, see it running on an assigned port with correct mapping

**Test app for this step:**
```dockerfile
# test-app/Dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build
EXPOSE 3000
CMD ["pnpm", "start"]
```

A minimal Next.js app that reads `ADHARA_API_URL` from env and displays it on the homepage. This proves the full flow works.

**Done when:** You can create a Site via API, trigger `POST /sites/{id}/deploy` with a git repo URL or Docker image, and the container starts running on a dynamic port. Container logs stream to MinIO. Env vars are injected correctly.

---

### Step 4: Traefik Dynamic Routing
**Status:** [x] Complete
**Estimated:** 1 session
**Depends on:** Step 3

Route traffic from custom hostnames to the correct container via Traefik.

**Tasks:**
- [ ] Configure Traefik Docker provider to auto-discover containers via labels
- [ ] When deploying a container, apply Traefik labels:
  - `traefik.enable=true`
  - `traefik.http.routers.{site}.rule=Host(\`{hostname}\`)`
  - `traefik.http.services.{site}.loadbalancer.server.port={port}`
- [ ] Assign default hostname: `{site-slug}.{workspace-slug}.{tenant-slug}.localhost`
- [ ] Support custom domain routing (add Host rule for custom domains)
- [ ] Enable Let's Encrypt ACME for SSL (staging CA for local dev, production CA for cloud)
- [ ] Implement domain management endpoints:
  - [ ] `POST /api/v1/sites/{id}/domains` — add custom domain
  - [ ] `GET /api/v1/sites/{id}/domains` — list domains
  - [ ] `DELETE /api/v1/sites/{id}/domains/{domain}` — remove domain
  - [ ] `POST /api/v1/sites/{id}/domains/{domain}/verify` — check DNS propagation
- [ ] Verify: access deployed site via `http://mysite.myworkspace.mytenant.localhost`

**Done when:** A deployed container is automatically accessible via its hostname through Traefik. Adding a custom domain via API updates Traefik routing. SSL works on non-localhost domains.

---

### Step 5: CLI Tool
**Status:** [x] Complete
**Estimated:** 1-2 sessions
**Depends on:** Step 4

Build the `adhara-engine` CLI using Python Typer.

**Tasks:**
- [ ] Set up CLI package (`cli/` directory with `setup.py` and entry point)
- [ ] Create HTTP client wrapper (`client.py`) for Engine API
- [ ] Implement command groups:
  - [ ] `tenant` — create, list, delete
  - [ ] `workspace` — create, list (scoped to tenant)
  - [ ] `site` — create, list, deploy, stop, restart, logs
  - [ ] `env` — set, list, unset (scoped to site)
  - [ ] `domain` — add, list, remove, verify (scoped to site)
  - [ ] `deploy` — list deployments, rollback
  - [ ] `ports` — routing table view (all port mappings across sites)
  - [ ] `site set-port` — change container or host port
  - [ ] `pipeline` — list, add, remove, disable steps
  - [ ] `status` — system health overview
- [ ] Rich output formatting (tables, colors, spinners) via `rich` library
- [ ] `--json` flag for machine-readable output on all commands
- [ ] `--follow` flag on `site logs` for real-time streaming
- [ ] Install via `pip install -e ./cli` (in Makefile `cli-install` target)
- [ ] Verify: full workflow via CLI from tenant creation to site deployment

**Example workflow to verify:**
```bash
adhara-engine tenant create --name "Test Corp" --email test@example.com
adhara-engine workspace create --tenant test-corp --name "Production"
adhara-engine site create --workspace test-corp/production --name "Main Site" \
  --source registry --image node:20-alpine --port 3000 --target local
adhara-engine env set test-corp/production/main-site ADHARA_API_URL=https://api.adharaweb.com
adhara-engine env set test-corp/production/main-site NEXT_PUBLIC_SITE_URL=https://example.com --build
adhara-engine site deploy test-corp/production/main-site
adhara-engine site logs test-corp/production/main-site --follow
adhara-engine status
```

**Done when:** The entire tenant > workspace > site > deploy > logs workflow works from the CLI. `adhara-engine --help` shows all commands with descriptions.

---

### Step 6: Basic Web UI
**Status:** [x] Complete
**Estimated:** 2-3 sessions
**Depends on:** Step 5

React dashboard for visual management.

**Tasks:**
- [ ] Set up React app with Vite, TypeScript, Tailwind CSS
- [ ] Create API client module (mirrors CLI client)
- [ ] Implement pages:
  - [ ] **Dashboard** — overview of all tenants, total sites, health status
  - [ ] **Tenant List** — table of tenants with workspace count
  - [ ] **Tenant Detail** — workspaces list, Adhara Web connection config
  - [ ] **Workspace Detail** — sites list with status indicators
  - [ ] **Site Detail** — deployment status, env vars editor, domain manager, deploy button
  - [ ] **Site Logs** — real-time log viewer (WebSocket to API)
  - [ ] **Deploy History** — list of deployments with status, rollback button
  - [ ] **Settings** — engine config, cloud provider credentials
- [ ] Implement auth (JWT login for super-admin)
- [ ] Real-time updates via WebSocket for deployment progress
- [ ] Responsive layout (works on tablet for quick checks)
- [ ] Verify: complete workflow through UI matches CLI capabilities

**Done when:** You can manage the full tenant > workspace > site lifecycle through the web UI, including deploying sites, viewing logs, and managing env vars.

---

### Step 7: GCP VM Deployment
**Status:** [x] Complete (docs/GCP_DEPLOYMENT.md)
**Estimated:** 1 session
**Depends on:** Step 6

Run the entire engine on a Google Cloud VM with real domains and SSL.

**Tasks:**
- [ ] Create GCP setup guide (VM specs, firewall rules, Docker install)
- [ ] Recommended VM: `e2-standard-4` (4 vCPU, 16 GB RAM) or `e2-standard-2` for small deployments
- [ ] Configure firewall rules: ports 80, 443, 8000 (API), 3000 (UI)
- [ ] Set up real domain pointing to VM IP (e.g., `engine.adharaweb.com`)
- [ ] Configure Traefik ACME with production Let's Encrypt
- [ ] Update `.env` with production values (secret key, domain, etc.)
- [ ] Test: `make init` on GCP VM, deploy a real Next.js site, access via custom domain with SSL
- [ ] Document: VM sizing guide based on number of sites
- [ ] Create `make deploy-gcp` target for future automated VM provisioning

**Done when:** Engine runs on a GCP VM, a Next.js site is deployed and accessible via HTTPS on a real domain, connected to Adhara Web backend.

---

## Phase 1 Checkpoint

At the end of Phase 1, this works end-to-end:

```
1. Run `make init` on your Mac or a GCP VM
2. Use CLI: `adhara-engine tenant create ...`
3. Use CLI: `adhara-engine site create --source registry --image my-nextjs-app:latest ...`
4. Use CLI: `adhara-engine env set ... ADHARA_API_URL=https://api.adharaweb.com`
5. Use CLI: `adhara-engine site deploy ...`
6. Browser: visit https://mysite.mydomain.com — Next.js app running, connected to Adhara Web
7. Grafana: view container logs at http://localhost:3001
8. Web UI: manage everything visually at http://localhost:3000
```

---

## Phase 2: Production Ready (Future)

After Phase 1 is solid:

- [ ] **Dev mode for sites** (enables AI builder integration):
  - [ ] `--mode dev` flag on site create/update
  - [ ] Dev mode runs framework dev server (`next dev`, `vite dev`) instead of production build
  - [ ] Code mounted as volume — file changes trigger hot-reload, no rebuild needed
  - [ ] AI builder or user writes files → changes appear in seconds, not minutes
  - [ ] `adhara-engine site set-mode production` triggers full build for production deploy
  - [ ] Streaming events API (`WS /api/v1/sites/{id}/events`) for build/deploy/health status
  - [ ] Webhook callbacks for deploy completion (machine-to-machine notification)
  - [ ] Service account API tokens (long-lived, scoped) for programmatic access
- [ ] Google Cloud Run deployment target
- [ ] Git webhook auto-deploy (push-to-deploy)
- [ ] Framework auto-detection (Next.js, Vite, Astro, Nuxt)
- [ ] Zero-downtime deployments (blue-green)
- [ ] Deployment rollback
- [ ] Advanced RBAC (custom roles per workspace, fine-grained resource permissions beyond Zitadel org roles)
- [ ] Extensible pipeline with custom pre/post hooks
- [ ] Billing integration (Adhara Web + native Stripe)
- [ ] Audit logging

## Phase 3: Scale (Future)

- [ ] AWS ECS/Fargate deployment target
- [ ] Deploy previews (per-branch URLs)
- [ ] Resource monitoring and alerts
- [ ] CDN integration (Bunny CDN)
- [ ] Webhook notifications (Slack, email)
- [ ] API rate limiting

## Phase 4: Enterprise / Kubernetes (Future)

- [ ] **Kubernetes deployment target (`KubernetesDeployTarget`)**:
  - [ ] Sites deploy as K8s Deployment + Service + Ingress resources
  - [ ] Traefik IngressRoute CRDs replace Docker label routing
  - [ ] K8s Secrets for env vars (both build and runtime tiers)
  - [ ] HPA (Horizontal Pod Autoscaler) for auto-scaling per site
  - [ ] Pod log streaming via K8s API
- [ ] **Helm chart** for deploying the entire engine on K8s (API, Zitadel, Traefik, Loki, PostgreSQL)
- [ ] **Engine API as K8s Deployment** — stateless, horizontally scalable
- [ ] SSO/SAML (via Zitadel enterprise features)
- [ ] White-label UI
- [ ] Terraform/Pulumi provider
- [ ] GitOps workflow (ArgoCD/Flux integration)
