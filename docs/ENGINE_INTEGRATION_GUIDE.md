# Engine Integration Guide

How to Dockerize any project and deploy it through Adhara Engine.

---

## Step 1: Identify Your Project Type

| Type | Indicators | Docker Pattern |
|------|-----------|----------------|
| **Next.js** | `next.config.*`, `pages/` or `app/` dir | 3-stage build → standalone Node server |
| **Vite SPA** | `vite.config.*`, no server-side rendering | 2-stage build → nginx static serving |
| **Express / Node API** | `server.js` or `index.js` entry, no framework | Single-stage or 2-stage Node |

---

## Step 2: Create Dockerfile

### Next.js (pnpm)

```dockerfile
# ── Stage 1: Install dependencies ────────────────────────────────────────────
FROM node:20-alpine AS deps
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@10 --activate
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# ── Stage 2: Build ───────────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@10 --activate
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build-time env vars (NEXT_PUBLIC_* are baked into the client bundle)
ARG NEXT_PUBLIC_ADHARA_WORKSPACE_ID
ENV NEXT_PUBLIC_ADHARA_WORKSPACE_ID=$NEXT_PUBLIC_ADHARA_WORKSPACE_ID

RUN pnpm build

# ── Stage 3: Run ─────────────────────────────────────────────────────────────
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs && \
    adduser  --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000 HOSTNAME="0.0.0.0"
CMD ["node", "server.js"]
```

**Requirements:**
- `next.config.js` must have `output: 'standalone'`
- If missing, add it:
  ```js
  /** @type {import('next').NextConfig} */
  const nextConfig = { output: 'standalone' };
  module.exports = nextConfig;
  ```

### Next.js (npm)

Same as above but replace pnpm lines:

```dockerfile
# ── Stage 1: Install dependencies ────────────────────────────────────────────
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ── Stage 2: Build ───────────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG NEXT_PUBLIC_ADHARA_WORKSPACE_ID
ENV NEXT_PUBLIC_ADHARA_WORKSPACE_ID=$NEXT_PUBLIC_ADHARA_WORKSPACE_ID

RUN npm run build

# ── Stage 3: Run (same as pnpm version) ─────────────────────────────────────
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs && \
    adduser  --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000 HOSTNAME="0.0.0.0"
CMD ["node", "server.js"]
```

### Vite SPA (with API proxy through nginx)

Use when the site needs to proxy API calls through nginx (e.g., to hide API keys from the client).

```dockerfile
# ── Stage 1: Build ───────────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

# Build-time env vars (VITE_* are baked into the client bundle)
ARG VITE_ADHARA_WORKSPACE_ID
ENV VITE_ADHARA_WORKSPACE_ID=$VITE_ADHARA_WORKSPACE_ID

RUN npm run build

# ── Stage 2: Serve with nginx ────────────────────────────────────────────────
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
```

Create `nginx.conf.template` alongside the Dockerfile:

```nginx
server {
    listen 3000;
    root /usr/share/nginx/html;
    index index.html;

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy — keeps secrets server-side
    location /api/ {
        proxy_pass ${ADHARA_BASE_URL}/;
        proxy_set_header Host $host;
        proxy_set_header X-Adhara-Api-Key ${ADHARA_API_KEY};
    }
}
```

> The `nginx:alpine` image auto-runs `envsubst` on files in `/etc/nginx/templates/` at startup, replacing `${VAR}` with environment values.

### Vite SPA (direct API calls from client)

Use when the client calls the Adhara API directly (API key is public/workspace-scoped).

```dockerfile
# ── Stage 1: Build ───────────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

# Vite reads .env.production at build time
ARG ADHARA_API_BASE=https://api.adharaweb.com
ARG ADHARA_WORKSPACE_ID
ARG ADHARA_API_CREDENTIAL

RUN if [ -n "$ADHARA_WORKSPACE_ID" ]; then \
      printf "ADHARA_API_BASE=%s\nADHARA_WORKSPACE_ID=%s\nADHARA_API_KEY=%s\n" \
        "$ADHARA_API_BASE" "$ADHARA_WORKSPACE_ID" "$ADHARA_API_CREDENTIAL" \
        > .env.production; \
    fi

RUN npm run build

# ── Stage 2: Serve with nginx ────────────────────────────────────────────────
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
```

Create `nginx.conf` (no template needed since there are no runtime vars):

```nginx
server {
    listen 3000;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

---

## Step 3: Create .dockerignore

Use this for all projects:

```
node_modules
dist
.next
.git
.gitignore
.vscode
.DS_Store
*.md
.env
.env.local
```

---

## Step 4: Environment Variables

### Build-Time vs Runtime

| Scope | When it's read | How to pass | Examples |
|-------|---------------|-------------|---------|
| **Build-time** | During `docker build` | `--build-arg VAR=value` | `NEXT_PUBLIC_*`, `VITE_*` |
| **Runtime** | When container starts | `adhara env set` or `-e` flag | `ADHARA_API_KEY`, `DATABASE_URL` |

**Key rules:**
- `NEXT_PUBLIC_*` vars are baked into the JS bundle at build time — they cannot change at runtime
- `VITE_*` vars (or whatever `envPrefix` is set to) work the same way — build-time only
- Server-side secrets (API keys, DB passwords) should be runtime env vars, not build args

### Avoiding Docker Secret Warnings

Docker warns if a build `ARG` name contains `KEY`, `SECRET`, or `PASSWORD`:

```
SecretsUsedInArgOrEnv: Do not use ARG or ENV instructions for sensitive data
```

**Fix:** Rename the ARG to avoid trigger words, then write the value into a config file:

```dockerfile
# BAD — triggers warning
ARG ADHARA_API_KEY

# GOOD — no warning
ARG ADHARA_API_CREDENTIAL
RUN printf "ADHARA_API_KEY=%s\n" "$ADHARA_API_KEY_VALUE" > .env.production
```

---

## Step 5: Build & Push the Image

Adhara Engine runs a local Docker registry at `localhost:5000`.

```bash
# Build the image (add --build-arg for each build-time var)
docker build \
  --build-arg NEXT_PUBLIC_ADHARA_WORKSPACE_ID=your-workspace-id \
  -t localhost:5000/my-site:latest \
  /path/to/project

# Push to the local registry
docker push localhost:5000/my-site:latest
```

### Image Naming Convention

```
localhost:5000/{site-slug}:latest
```

Examples:
- `localhost:5000/iampatrickfarrell:latest`
- `localhost:5000/djloversclub:latest`

---

## Step 6: Create Tenant, Workspace & Site

If this is a brand new client, create the tenant and workspace first:

```bash
# Create tenant (one per client/organization)
adhara tenant create --name "Client Name" --email client@example.com

# Create workspace (one per project/brand)
adhara workspace create --tenant client-name --name "Project Name"
```

Then create the site:

```bash
# Create site pointing to the registry image
adhara site create \
  --workspace "client-name/project-name" \
  --name "project-name" \
  --source docker_registry \
  --image localhost:5000/project-name:latest
```

---

## Step 7: Set Runtime Environment Variables

For sites that need runtime env vars (API proxy pattern):

```bash
# Set runtime env vars
adhara env set client-name/project-name/project-name ADHARA_BASE_URL=https://api.adharaweb.com
adhara env set client-name/project-name/project-name ADHARA_API_KEY=your-api-key
```

---

## Step 8: Deploy

```bash
adhara site deploy client-name/project-name/project-name
```

On success, the CLI prints the site URL:

```
Site URL: http://project-name.project-name.client-name.localhost
```

The site is accessible via Traefik routing on port 80.

---

## Quick Reference: Full Example

### Deploying a Next.js site (e.g., "Angela Papa")

```bash
# 1. Build & push
docker build \
  --build-arg NEXT_PUBLIC_ADHARA_WORKSPACE_ID=ws_abc123 \
  -t localhost:5000/angelapapa:latest \
  /path/to/angela_papa/angelapapa

docker push localhost:5000/angelapapa:latest

# 2. Create resources (skip if tenant/workspace exist)
adhara tenant create --name "Angela Papa" --email angela@example.com
adhara workspace create --tenant angela-papa --name "Angela Papa"

# 3. Create & deploy site
adhara site create \
  --workspace "angela-papa/angela-papa" \
  --name "angelapapa" \
  --source docker_registry \
  --image localhost:5000/angelapapa:latest

adhara site deploy angela-papa/angela-papa/angelapapa
```

### Deploying a Vite SPA with API proxy (e.g., "DJ Lovers Club")

```bash
# 1. Build & push
docker build \
  --build-arg VITE_ADHARA_WORKSPACE_ID=ws_xyz789 \
  -t localhost:5000/djloversclub:latest \
  /path/to/djloversclub/djloversclub-website

docker push localhost:5000/djloversclub:latest

# 2. Create resources
adhara tenant create --name "DJ Lovers Club" --email dj@example.com
adhara workspace create --tenant dj-lovers-club --name "DJ Lovers Club"

# 3. Create site
adhara site create \
  --workspace "dj-lovers-club/dj-lovers-club" \
  --name "djloversclub" \
  --source docker_registry \
  --image localhost:5000/djloversclub:latest

# 4. Set runtime env vars (for nginx API proxy)
adhara env set dj-lovers-club/dj-lovers-club/djloversclub ADHARA_BASE_URL=https://api.adharaweb.com
adhara env set dj-lovers-club/dj-lovers-club/djloversclub ADHARA_API_KEY=your-api-key

# 5. Deploy
adhara site deploy dj-lovers-club/dj-lovers-club/djloversclub
```

---

## Updating a Deployed Site

After making changes to the source code:

```bash
# Rebuild and push
docker build -t localhost:5000/my-site:latest /path/to/project
docker push localhost:5000/my-site:latest

# Redeploy (pulls the new image)
adhara site deploy tenant/workspace/site
```

---

## Useful Commands

```bash
# Check site status
adhara site status tenant/workspace/site

# View site logs
adhara site logs tenant/workspace/site --tail 100 --follow

# Stop a site
adhara site stop tenant/workspace/site

# Restart a site
adhara site restart tenant/workspace/site

# List all sites in a workspace
adhara site list --workspace tenant/workspace

# View port routing table
adhara ports

# System health
adhara status
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `standalone` directory missing in Next.js build | Add `output: 'standalone'` to `next.config.js` |
| `ENOENT server.js` at container start | Standalone not enabled, or `.next/standalone` not copied correctly |
| `SecretsUsedInArgOrEnv` Docker warning | Rename ARG to avoid `KEY`/`SECRET`/`PASSWORD`/`TOKEN` anywhere in the name (use `CREDENTIAL` instead) |
| Site shows "not_found" after engine restart | Run `adhara site deploy` again to recreate the container |
| `pnpm: not found` in Docker build | Add `RUN corepack enable && corepack prepare pnpm@10 --activate` |
| nginx 502 Bad Gateway (API proxy) | Check runtime env vars are set: `adhara env list tenant/ws/site` |
| Vite env vars not in bundle | Ensure vars use the correct prefix (`VITE_` by default) and are set at **build time** |
| Port conflict | Check `adhara ports` — engine auto-assigns from range 4001-5000 |
