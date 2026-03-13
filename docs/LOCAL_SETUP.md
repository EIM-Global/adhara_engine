# Adhara Engine — Local Setup Guide

Get the Adhara Engine running on your Mac for local development and testing.

## Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Docker runtime | Any (OrbStack, Docker Desktop, Colima, Podman) | `docker --version` |
| Docker Compose | v2+ (included with modern Docker) | `docker compose version` |
| Node.js | 20+ (for the Web UI dev server) | `node --version` |
| pnpm | 9+ (UI package manager) | `pnpm --version` |
| Python | 3.11+ (for the CLI) | `python3 --version` |
| uv | Latest (Python package manager) | `uv --version` |
| Git | Any | `git --version` |

**Recommended runtime:** [OrbStack](https://orbstack.dev/) — fast, lightweight Docker runtime for macOS.

---

## Quick Start (5 minutes)

```bash
# 1. Clone the repository
git clone <repo-url> adhara-engine
cd adhara-engine

# 2. Start everything
make init

# 3. Wait for services to be healthy (~30-60 seconds)
make status

# 4. Run database migrations
make db-migrate

# 5. Seed with sample data (optional)
make db-seed
```

That's it. The engine is running.

---

## What's Running

After `make init`, these services are available:

| Service | URL | Purpose |
|---------|-----|---------|
| **API** | http://localhost:8000 | FastAPI backend |
| **API Docs** | http://localhost:8000/docs | Swagger/OpenAPI UI |
| **Traefik Dashboard** | http://localhost:8080 | Reverse proxy admin |
| **Grafana** | http://localhost:3001 | Log viewer (admin/admin) |
| **MinIO Console** | http://localhost:9001 | Object storage (engine/engine-secret) |
| **Zitadel Console** | http://localhost:8081 | Auth admin |
| **PostgreSQL** | localhost:5432 | Database (engine/engine) |
| **Redis** | localhost:6379 | Cache |
| **Docker Registry** | localhost:5000 | Local image registry |

Deployed sites get ports in the **4001-5000** range and are also accessible via hostname routing through Traefik on port 80:
- Pattern: `http://{site}.{workspace}.{tenant}.localhost`

---

## Install the CLI

```bash
make cli-install
# or manually:
cd cli && uv venv .venv && source .venv/bin/activate && uv pip install -e .
```

After installing, activate the CLI venv before use:

```bash
source cli/.venv/bin/activate
adhara-engine --help
```

---

## Install the Web UI (Development)

```bash
cd ui
pnpm install
pnpm dev
```

Open http://localhost:5173 — the UI proxies API calls to `localhost:8000` automatically.

---

## CLI Walkthrough

### View system status

```bash
adhara-engine status
```

### Create a tenant

```bash
adhara-engine tenant create --name "My Company" --email admin@example.com --plan pro
adhara-engine tenant list
```

### Create a workspace

```bash
adhara-engine workspace create --tenant my-company --name "Production" \
  --adhara-api-url "https://api.adharaweb.com"
adhara-engine workspace list --tenant my-company
```

### Create and deploy a site

```bash
# Create a site using a Docker image
adhara-engine site create \
  --workspace my-company/production \
  --name "Main Site" \
  --source docker_image \
  --image "nginx:alpine" \
  --port 80

# Deploy it
adhara-engine site deploy my-company/production/main-site

# Check status
adhara-engine site status my-company/production/main-site

# View logs
adhara-engine site logs my-company/production/main-site
```

### Manage environment variables

```bash
# Set a runtime env var (takes effect on restart)
adhara-engine env set my-company/production/main-site API_URL=https://api.example.com

# Set a build-time env var (requires redeploy)
adhara-engine env set my-company/production/main-site NEXT_PUBLIC_SITE_URL=https://example.com --build

# List all env vars
adhara-engine env list my-company/production/main-site
```

### Manage custom domains

```bash
adhara-engine domain add my-company/production/main-site app.example.com
adhara-engine domain list my-company/production/main-site
adhara-engine domain verify my-company/production/main-site app.example.com
```

### View port routing table

```bash
adhara-engine ports
```

### JSON output (for scripting)

```bash
adhara-engine --json tenant list
adhara-engine --json site status my-company/production/main-site
```

---

## Deploy Your Own App

Ready to deploy a real application (not just `nginx:alpine`)? See the full guide:

- **[Deploying Sites](DEPLOYING_SITES.md)** — end-to-end walkthrough for both pre-built image and git repo workflows
- **[Dockerfile Templates](examples/)** — ready-to-use Dockerfiles for Vite+Express, Next.js, and static SPAs

---

## Accessing Deployed Sites

Sites are accessible two ways:

### 1. Direct port access
```
http://localhost:{host_port}
```
Check the assigned port with `adhara-engine ports` or `adhara-engine site info {path}`.

### 2. Hostname routing (via Traefik)
```
http://{site-slug}.{workspace-slug}.{tenant-slug}.localhost
```
This works automatically on macOS — `*.localhost` resolves to `127.0.0.1` by default. Traefik on port 80 routes by hostname to the correct container.

Example: `http://main-site.production.my-company.localhost`

---

## Development Mode

For hot-reloading the API on code changes:

```bash
make dev
```

This mounts `./api` as a volume and enables uvicorn's `--reload` flag.

---

## Common Operations

| Task | Command |
|------|---------|
| Start all services | `make up` |
| Stop all services | `make down` |
| Restart all services | `make restart` |
| View all logs | `make logs` |
| View API logs | `make logs-api` |
| View specific service logs | `make logs-service SVC=traefik` |
| Check service health | `make status` |
| Run migrations | `make db-migrate` |
| Seed sample data | `make db-seed` |
| Reset database (destructive) | `make db-reset` |
| Rebuild all images | `make build` |
| Full cleanup (destructive) | `make clean` |

---

## Environment Variables

Copy `.env.example` to `.env` (done automatically by `make init`):

| Variable | Default | Description |
|----------|---------|-------------|
| `ENGINE_SECRET_KEY` | `change-me-to-a-random-string` | API secret key |
| `POSTGRES_PASSWORD` | `engine` | PostgreSQL password |
| `MINIO_ACCESS_KEY` | `engine` | MinIO access key |
| `MINIO_SECRET_KEY` | `engine-secret` | MinIO secret key |
| `ZITADEL_MASTERKEY` | (32 chars) | Zitadel encryption key |
| `ZITADEL_DB_PASSWORD` | `zitadel` | Zitadel DB password |
| `GRAFANA_PASSWORD` | `admin` | Grafana admin password |
| `ACME_EMAIL` | `admin@adharaweb.com` | Let's Encrypt email |
| `DOCKER_HOST_SOCKET` | `/var/run/docker.sock` | Docker socket path |

---

## Two-Tier Environment Variables

Sites support two scopes of environment variables:

| Scope | When Applied | Use For |
|-------|-------------|---------|
| **Runtime** | On container restart | `API_URL`, `DATABASE_URL`, secrets |
| **Build** | On image rebuild (redeploy) | `NEXT_PUBLIC_*`, compile-time constants |

`NEXT_PUBLIC_*` variables are auto-detected as build scope because Next.js bakes them into static JS at build time.

---

## Troubleshooting

### Services not starting
```bash
make status                  # Check which services are unhealthy
make logs-service SVC=api    # Check specific service logs
docker compose ps -a         # See all containers including stopped ones
```

### Port conflicts
The engine uses these ports: 80, 443, 3001, 3100, 5000, 5432, 6379, 8000, 8080, 8081, 9000, 9001. If any are in use, stop the conflicting service or modify `docker-compose.yml`.

Deployed sites use ports 4001-5000. If a deploy fails with a port conflict, check `adhara-engine ports`.

### Zitadel slow to start
Zitadel takes 1-3 minutes on first boot to initialize database projections. This is normal. Check progress at http://localhost:8081/debug/healthz.

### Docker socket path
If you're not using OrbStack or Docker Desktop, set `DOCKER_HOST_SOCKET` in `.env`:
- **Colima:** `/Users/<you>/.colima/default/docker.sock`
- **Podman:** `/run/user/1000/podman/podman.sock`

### Reset everything
```bash
make clean    # Removes all containers and volumes
make init     # Start fresh
make db-migrate
make db-seed  # Optional
```

---

## Architecture Overview

```
┌─────────────┐     ┌──────────┐     ┌──────────────┐
│  Web UI     │────>│  API     │────>│  PostgreSQL   │
│  :5173      │     │  :8000   │     │  :5432        │
└─────────────┘     └────┬─────┘     └──────────────┘
                         │
┌─────────────┐     ┌────┴─────┐     ┌──────────────┐
│  CLI        │────>│  Docker  │────>│  Containers   │
│  (local)    │     │  Socket  │     │  :4001-5000   │
└─────────────┘     └──────────┘     └──────┬───────┘
                                            │
                    ┌──────────┐     ┌──────┴───────┐
                    │  Traefik │<────│  Labels      │
                    │  :80/:443│     │  (auto-disc) │
                    └──────────┘     └──────────────┘
```

Traefik discovers containers on `adhara-engine-net` via Docker labels and routes traffic by hostname. No manual config needed — deploy a site and Traefik picks it up automatically.
