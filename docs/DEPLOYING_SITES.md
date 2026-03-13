# Deploying Sites to Adhara Engine

This guide covers how to take any web application, containerize it, and deploy it through Adhara Engine's local infrastructure.

---

## Overview

Adhara Engine manages the full lifecycle of containerized web apps: building images, running containers, assigning ports, routing traffic via Traefik, and managing environment variables.

**Two deploy workflows:**

| Workflow | When to Use |
|----------|-------------|
| **Pre-built Image** | You build the Docker image yourself and push it to the local registry |
| **Git Repo** | Point Adhara at a repo with a Dockerfile and it builds + deploys for you |

Both result in a running container accessible via direct port and hostname routing.

---

## Prerequisites

Before deploying, ensure:

1. **Adhara Engine is running** — `make status` shows all services healthy
2. **CLI is installed** — `adhara-engine --help` works (see [LOCAL_SETUP.md](LOCAL_SETUP.md))
3. **Tenant + workspace exist** — create them if needed:

```bash
adhara-engine tenant create --name "My Company" --email admin@example.com --plan pro
adhara-engine workspace create --tenant my-company --name "Production"
```

---

## Writing a Dockerfile

Your app needs a Dockerfile that meets two requirements:

1. **Listens on a single HTTP port** (default: 3000)
2. **Respects the `PORT` environment variable** (Adhara injects this at runtime)

### Recommended: Multi-Stage Builds

Multi-stage builds keep production images small by separating build tools from the runtime:

```dockerfile
# Stage 1: Install deps + build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Production — only what's needed to run
FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/dist ./dist
ENV NODE_ENV=production PORT=3000
EXPOSE 3000
CMD ["node", "dist/index.cjs"]
```

### Templates

See `docs/examples/` for ready-to-use Dockerfiles:

| Template | Use Case |
|----------|----------|
| [`Dockerfile.vite-express`](examples/Dockerfile.vite-express) | Vite + Express full-stack (esbuild server bundle) |
| [`Dockerfile.nextjs`](examples/Dockerfile.nextjs) | Next.js with standalone output |
| [`Dockerfile.static-vite`](examples/Dockerfile.static-vite) | Static SPA served by nginx |

---

## Workflow 1: Pre-built Image

Build the image yourself, push to the local registry, then deploy.

### Step 1 — Build the image

```bash
cd /path/to/your-app
docker build -t my-app:latest .
```

### Step 2 — Tag and push to the local registry

Adhara Engine runs a Docker registry on `localhost:5000`:

```bash
docker tag my-app:latest localhost:5000/my-tenant/my-app:latest
docker push localhost:5000/my-tenant/my-app:latest
```

### Step 3 — Create the site

```bash
adhara-engine site create \
  --workspace my-tenant/production \
  --name "My App" \
  --source docker_image \
  --image "localhost:5000/my-tenant/my-app:latest" \
  --port 3000
```

### Step 4 — Deploy

```bash
adhara-engine site deploy my-tenant/production/my-app
```

### Step 5 — Verify

```bash
adhara-engine site status my-tenant/production/my-app
```

---

## Workflow 2: Git Repo

Point Adhara at a local repo that contains a Dockerfile. The engine builds the image for you.

### Step 1 — Ensure Dockerfile is at repo root

The Dockerfile must be at the root of the repository.

### Step 2 — Create the site

```bash
adhara-engine site create \
  --workspace my-tenant/production \
  --name "My App" \
  --source git_repo \
  --source-url /absolute/path/to/your-app \
  --port 3000
```

### Step 3 — Deploy

```bash
adhara-engine site deploy my-tenant/production/my-app
```

The engine will:
1. Copy/clone the repo
2. Run `docker build` using the Dockerfile
3. Start the container with the correct port and env vars

---

## Environment Variables

### Runtime vs Build Variables

| Scope | When Applied | Example |
|-------|-------------|---------|
| **Runtime** | On container start/restart | `DATABASE_URL`, `API_KEY`, secrets |
| **Build** | During `docker build` (requires redeploy) | `NEXT_PUBLIC_*`, compile-time constants |

### Setting Variables

```bash
# Runtime variable (takes effect on restart)
adhara-engine env set my-tenant/production/my-app API_URL=https://api.example.com

# Build variable (requires redeploy)
adhara-engine env set my-tenant/production/my-app NEXT_PUBLIC_SITE_URL=https://example.com --build

# List all variables
adhara-engine env list my-tenant/production/my-app
```

### Auto-Injected Variables

Adhara Engine automatically injects these into every container:

| Variable | Value |
|----------|-------|
| `ADHARA_TENANT_ID` | Tenant UUID |
| `ADHARA_WORKSPACE_ID` | Workspace UUID |
| `ADHARA_SITE_ID` | Site UUID |
| `ADHARA_SITE_SLUG` | Site slug |
| `PORT` | Assigned container port |

---

## Traefik Routing

Every deployed site is automatically accessible via hostname routing through Traefik on port 80:

```
http://{site-slug}.{workspace-slug}.{tenant-slug}.localhost
```

This works out of the box on macOS because `*.localhost` resolves to `127.0.0.1`.

Sites are also accessible via their assigned host port:

```
http://localhost:{host_port}
```

Check assigned ports with:

```bash
adhara-engine ports
# or
adhara-engine site status my-tenant/production/my-app
```

---

## Real-World Example: Jungle Habitas

Jungle Habitas is a Vite + Express full-stack app. Here's how to deploy it both ways.

### Project Structure

```
jungle_habitas/
├── client/           # Vite React frontend
├── server/           # Express API + SSR
├── shared/           # Shared types
├── script/build.ts   # Build script (Vite + esbuild)
├── Dockerfile        # Multi-stage build
├── .dockerignore
└── package.json      # "build" → Vite client + esbuild server bundle
```

The build produces:
- `dist/public/` — Vite client assets
- `dist/index.cjs` — esbuild server bundle (all server deps inlined, no `node_modules` needed)

### Deploy via Pre-built Image

```bash
# Build
cd /path/to/jungle_habitas
docker build -t jungle-habitas:latest .

# Test locally first
docker run -p 3000:3000 -e SITE_URL=http://localhost:3000 jungle-habitas:latest

# Push to Adhara registry
docker tag jungle-habitas:latest localhost:5000/eim/jungle-habitas:latest
docker push localhost:5000/eim/jungle-habitas:latest

# Create + deploy
adhara-engine site create \
  --workspace eim/production \
  --name "Jungle Habitas" \
  --source docker_image \
  --image "localhost:5000/eim/jungle-habitas:latest" \
  --port 3000

adhara-engine site deploy eim/production/jungle-habitas
```

### Deploy via Git Repo

```bash
adhara-engine site create \
  --workspace eim/production \
  --name "Jungle Habitas" \
  --source git_repo \
  --source-url /Users/pfarrell/projects/eim_clients/jungle_habitas/jungle_habitas \
  --port 3000

adhara-engine site deploy eim/production/jungle-habitas
```

### Access the site

```bash
# Hostname routing
open http://jungle-habitas.production.eim.localhost

# Direct port
adhara-engine site status eim/production/jungle-habitas
# → host_port: 4001
open http://localhost:4001
```

---

## Troubleshooting

### Build fails with "npm ci" errors

- Ensure `package-lock.json` is committed and up to date
- Check that `node_modules` is in `.dockerignore`
- Run `npm ci` locally first to verify it works

### Container starts but returns 502/503

- Check container logs: `adhara-engine site logs my-tenant/production/my-app`
- Verify the app listens on the correct port (must match `--port` in site create)
- Ensure the app binds to `0.0.0.0`, not `127.0.0.1` (containers need external binding)

### "Image not found" on deploy

- Verify the image is in the local registry: `curl http://localhost:5000/v2/_catalog`
- Check the tag: `curl http://localhost:5000/v2/my-tenant/my-app/tags/list`
- Ensure you pushed to `localhost:5000/...`, not Docker Hub

### Port conflict

- Check what's using the port range: `adhara-engine ports`
- The engine assigns ports from the 4001-5000 range automatically

### Hostname routing not working

- Verify Traefik is running: `make status` → check traefik service
- Check Traefik dashboard at http://localhost:8080 for the route
- Ensure no DNS override for `.localhost` (macOS resolves it natively)

### Environment variables not taking effect

- **Runtime vars:** Restart the container — `adhara-engine site deploy` (redeploy picks up new env)
- **Build vars:** Require a full rebuild — rebuild the image and redeploy
- Check current values: `adhara-engine env list my-tenant/production/my-app`
