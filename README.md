# Adhara Engine

> Copyright (c) 2026 EIM Global Solutions, LLC. All rights reserved.
> Licensed under a proprietary license. See [LICENSE](LICENSE) for details.

A self-hosted, multi-tenant deployment platform for frontend websites. Manage tenants, workspaces, and sites through a web dashboard, CLI, or API — all backed by Docker containers with automatic routing, OIDC authentication, and observability.

## Architecture

```
                        ┌─────────────────────────────┐
                        │        Traefik :80/:443      │
                        │   (reverse proxy + auto SSL) │
                        └──────┬──────────────┬────────┘
                               │              │
                  ┌────────────▼──┐    ┌──────▼───────────────────┐
                  │   UI (React)  │    │  Deployed Site Containers │
                  │   :5173       │    │  :4001-5000 (auto-routed) │
                  └──────┬────────┘    └──────────────────────────┘
                         │
                  ┌──────▼────────┐
                  │  API (FastAPI) │
                  │  :8000         │
                  └──┬─────┬──────┘
                     │     │
          ┌──────────▼┐  ┌─▼──────────┐
          │ PostgreSQL │  │   Redis    │
          │ :5432      │  │   :6379    │
          └────────────┘  └────────────┘

   Supporting: Logto :3001 │ MinIO :9000 │ Grafana :3003 │ Loki :3100 │ Registry :5000
```

## Prerequisites

- **Docker** (any runtime: Docker Desktop, OrbStack, Colima, Podman)
- **Docker Compose** v2+ (included with Docker Desktop / OrbStack)
- **Git**
- **Make**

Optional (for CLI usage):
- **Python 3.11+** and **uv** (for the CLI tool)

## New Server Setup

Step-by-step guides for provisioning a server and installing Adhara Engine from scratch.

- [DigitalOcean](#digitalocean-setup) — Simplest path, recommended for most users
- [Google Cloud Platform](#google-cloud-platform-setup) — Additional firewall/IAM steps

Both guides end at the same place: a running Adhara Engine you can access in your browser.

---

### DigitalOcean Setup

#### 1. Create the Droplet

1. Go to **DigitalOcean → Create → Droplets**
2. Choose **Ubuntu 24.04 LTS**
3. Select a plan:

| Scale | Droplet | vCPU | RAM | Monthly | Sites |
|-------|---------|------|-----|---------|-------|
| Small (testing) | Basic, Regular | 2 | 4 GB | ~$24/mo | 5-15 |
| Standard | Basic, Regular | 4 | 8 GB | ~$48/mo | 15-50 |
| Large | Basic, Premium | 8 | 16 GB | ~$96/mo | 50-100+ |

4. Choose a datacenter region close to your users
5. Under **Authentication**, add your SSH key
6. Click **Create Droplet** and note the IP address

#### 2. Create a deploy user (don't run as root)

SSH in as root, then create a non-root user with sudo and Docker access:

```bash
ssh root@YOUR_DROPLET_IP

# Create your user
adduser deploy
usermod -aG sudo deploy

# Let them use Docker without sudo (installed next step)
usermod -aG docker deploy

# Set up SSH key for the new user
mkdir -p /home/deploy/.ssh
cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys

# Log out of root — from now on, always SSH as deploy
exit
```

#### 3. Install Docker

SSH in as your new user:

```bash
ssh deploy@YOUR_DROPLET_IP

# Install Docker (official method)
curl -fsSL https://get.docker.com | sh

# Verify Docker works without sudo
docker run --rm hello-world
```

> If `docker run` gives a permission error, log out and back in so the `docker` group takes effect.

#### 4. Install Make and clone the repo

```bash
sudo apt update && sudo apt install -y make git

mkdir -p ~/projects && cd ~/projects
git clone git@github.com:EIM-Global/adhara_engine.git
cd adhara_engine
```

> **Need SSH access to GitHub?** Generate a key with `ssh-keygen -t ed25519`, then add `~/.ssh/id_ed25519.pub` as a deploy key in the GitHub repo settings (read-only is fine).

#### 5. Start the engine

```bash
# Creates .env with auto-generated secrets, builds images, runs migrations
make init

# Create an API token to log in
make token
```

#### 6. Access the dashboard

Open `http://YOUR_DROPLET_IP` in your browser. Log in with the API token from step 5.

#### 7. (Optional) Set up SSO

See [Authentication Modes](#authentication-modes) below for Logto or Zitadel SSO setup.

#### 8. (Optional) Enable HTTPS

See [Enabling HTTPS](#enabling-https) below to set up a domain with auto-SSL.

#### 9. (Optional) Harden security

```bash
sudo bash scripts/adhara-secure.sh
```

This configures UFW firewall rules and locks down internal ports.

---

### Google Cloud Platform Setup

GCP requires additional firewall rules and uses `gcloud` for VM creation. For the full GCP-specific guide (VM sizing, firewall rules, IAP tunnels, service accounts), see **[docs/GCP_DEPLOYMENT.md](docs/GCP_DEPLOYMENT.md)**.

#### 1. Create the VM

```bash
gcloud compute instances create adhara-engine \
  --zone=us-central1-a \
  --machine-type=e2-standard-4 \
  --boot-disk-size=100GB \
  --boot-disk-type=pd-ssd \
  --image-family=ubuntu-2404-lts-amd64 \
  --image-project=ubuntu-os-cloud \
  --tags=adhara-engine
```

Or via the Console: **Compute Engine → VM Instances → Create** (Ubuntu 24.04 LTS, 100 GB SSD).

#### 2. Open firewall ports

GCP blocks all inbound traffic by default. You must create firewall rules:

```bash
# HTTP (required — Let's Encrypt + site traffic)
gcloud compute firewall-rules create adhara-allow-http \
  --allow=tcp:80 \
  --target-tags=adhara-engine \
  --description="Adhara Engine HTTP"

# HTTPS
gcloud compute firewall-rules create adhara-allow-https \
  --allow=tcp:443 \
  --target-tags=adhara-engine \
  --description="Adhara Engine HTTPS"
```

#### 3. Create a deploy user, install Docker, and clone

SSH into the VM:

```bash
gcloud compute ssh adhara-engine --zone=us-central1-a
```

Then follow the same steps as DigitalOcean:

```bash
# Create deploy user (if not using the default GCP user)
sudo adduser deploy
sudo usermod -aG sudo deploy
sudo usermod -aG docker deploy

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Make and clone
sudo apt update && sudo apt install -y make git
mkdir -p ~/projects && cd ~/projects
git clone git@github.com:EIM-Global/adhara_engine.git
cd adhara_engine
```

> **GCP SSH keys:** If you created a `deploy` user, add your SSH key via **Compute Engine → Metadata → SSH Keys**, or copy it manually as shown in the DigitalOcean section.

#### 4. Start the engine

```bash
make init
make token
```

Open `http://EXTERNAL_IP` in your browser (find the external IP with `gcloud compute instances describe adhara-engine --zone=us-central1-a --format='get(networkInterfaces[0].accessConfigs[0].natIP)'`).

#### 5. Next steps

- **HTTPS:** See [Enabling HTTPS](#enabling-https)
- **SSO:** See [Authentication Modes](#authentication-modes)
- **Full GCP guide:** See [docs/GCP_DEPLOYMENT.md](docs/GCP_DEPLOYMENT.md) for IAP tunnels, service accounts, and advanced networking

## Quickstart (Local Development)

```bash
# 1. Clone and enter the repo
git clone git@github.com:EIM-Global/adhara_engine.git && cd adhara_engine

# 2. First-time setup — copies .env, builds images, starts everything,
#    and runs database migrations automatically
make init

# 3. Create an API token to log in
make token

# 4. (Optional) Set up SSO instead of token auth
#    Logto (lightweight):  make init-auth
#    Zitadel (enterprise): make init-zitadel
```

That's it. Open **http://engine.localhost** in your browser.

## Deployment Profiles

Adhara Engine uses Docker Compose profiles to let you run only the services you need. The core profile is lightweight (~500MB) and uses API token auth — no SSO provider, Grafana, or MinIO required.

### Profile Overview

| Profile | Services Added | Extra RAM | Use Case |
|---------|---------------|-----------|----------|
| *(core — default)* | api, worker, ui, traefik, db, redis | ~500MB | Small servers, simple deployments |
| `auth` | + logto | +150MB | **SSO (default)** — lightweight OIDC |
| `zitadel` | + zitadel, zitadel-login | +800MB | SSO (enterprise) — advanced multi-tenancy |
| `observability` | + loki, alloy, grafana | +400MB | Log aggregation + dashboards |
| `registry` | + docker registry v2 | +30MB | Private image hosting |
| `storage` | + minio | +100MB | S3-compatible object storage |
| `all` | Everything (uses Logto for auth) | ~1.3GB total | Full-featured setup |

### Quick Start by Profile

```bash
# Core only — token auth, minimal resources
make init
make token            # generate an API token to log in

# Core + Logto SSO (recommended)
make init-auth

# Core + Zitadel SSO (enterprise — heavier)
make init-zitadel

# Full — Logto SSO + logging + storage + registry
make init-full

# Mix and match profiles
docker compose --profile auth --profile observability up -d
```

### Make Targets

| Command | Description |
|---------|-------------|
| `make init` | Core services only (~500MB, token auth) |
| `make init-auth` | Core + Logto SSO (~650MB) |
| `make init-zitadel` | Core + Zitadel SSO (~1.3GB) |
| `make init-full` | All services with Logto (~1.3GB) |
| `make up` | Start core services |
| `make up-auth` | Core + Logto SSO |
| `make up-zitadel` | Core + Zitadel SSO |
| `make up-full` | Start all services |
| `make up-obs` | Core + observability |
| `make token` | Create a platform-admin API token |

### Authentication Modes

**Token auth** (core profile — no SSO provider):
- Run `make token` to generate an `ae_*` API token
- Enter the token on the login page
- Stored in browser localStorage — no external auth service needed

**Logto SSO** (auth profile — default SSO):
- Run `make init-auth` or `make up-auth`
- Open Logto Admin Console at `http://localhost:3002`
- Create an application, copy the Client ID to `ui/.env` as `VITE_OIDC_CLIENT_ID`
- Rebuild the UI: `docker compose up -d --build ui`
- ~150MB overhead, single container, standard OIDC with PKCE

**Zitadel SSO** (zitadel profile — enterprise):
- Run `make init-zitadel` or `make up-zitadel`
- Run `bash scripts/setup-zitadel.sh` after first boot
- ~800MB overhead, two containers, enterprise multi-tenancy and audit logging

The UI automatically detects which mode to use based on whether `VITE_OIDC_CLIENT_ID` is set in `ui/.env`.

## Production Profiles

After completing the [server setup](#new-server-setup) above (which uses `make init` for the core profile), you can add more services:

```bash
# Add Logto SSO
make init-auth

# Or add everything (Logto SSO + logging + storage + registry)
make init-full

# Or mix profiles manually
docker compose --profile auth --profile observability up -d
```

See [Deployment Profiles](#deployment-profiles) for the full list of profiles and what each adds.

### Enabling HTTPS

HTTPS uses Let's Encrypt via Traefik's built-in ACME support. The certificate is issued automatically — you just need a domain pointing to your server.

#### Step 1: Get your server's IP

```bash
curl -s ifconfig.me
# Example output: 165.245.135.53
```

#### Step 2: Create a DNS record

Go to your domain registrar or DNS provider (Cloudflare, Namecheap, Route 53, DigitalOcean DNS, etc.) and create an **A record**:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| **A** | `engine` | `165.245.135.53` (your server IP) | 300 |

This makes `engine.yourdomain.com` point to your server.

**Which record type to use:**
- **A record** (recommended) — Points directly to an IP address. Use this for VPS/droplet deployments.
- **CNAME record** — Points to another domain name. Use this only if your server has a stable hostname (e.g. a load balancer). Cannot be used on the root/apex domain (`yourdomain.com`), only subdomains (`engine.yourdomain.com`).

**Example configurations by provider:**

| Provider | Where to add records |
|----------|---------------------|
| **Cloudflare** | DNS → Add Record. **Disable the orange proxy cloud** (set to DNS only) so Traefik can get the cert directly. |
| **Namecheap** | Advanced DNS → Add New Record |
| **DigitalOcean** | Networking → Domains → Add Record |
| **Route 53** | Hosted Zones → your domain → Create Record |
| **Google Domains** | DNS → Custom Records → Manage |

#### Step 3: Verify DNS propagation

Wait for the DNS record to propagate (usually 1-5 minutes, up to 48 hours):

```bash
# Check if the record resolves to your server
dig +short engine.yourdomain.com
# Should return: 165.245.135.53

# Or use nslookup
nslookup engine.yourdomain.com
```

**Do not proceed until the domain resolves to your server's IP.** Let's Encrypt will fail to issue a certificate if the domain doesn't point to the right server, and too many failed attempts will rate-limit you.

#### Step 4: Configure and activate HTTPS

```bash
# Add domain and email to .env
echo "ADHARA_DOMAIN=engine.yourdomain.com" >> .env
echo "ACME_EMAIL=you@yourdomain.com" >> .env

# Run the secure script — generates Traefik HTTPS config
sudo bash scripts/adhara-secure.sh

# Restart Traefik to request the certificate
docker compose restart traefik
```

Traefik will automatically:
1. Respond to Let's Encrypt's HTTP-01 challenge on port 80
2. Obtain and store the TLS certificate
3. Redirect all HTTP traffic to HTTPS
4. Auto-renew the certificate before expiry

#### Step 5: Verify the certificate

```bash
# Check that HTTPS works (may take 30-60 seconds on first request)
curl -v https://engine.yourdomain.com/ 2>&1 | grep "SSL certificate"

# Or just open in your browser — you should see the lock icon
```

If the certificate fails, check Traefik logs:
```bash
docker logs adhara-engine-traefik-1 --tail 30 | grep -i acme
```

Common issues:
- **Domain doesn't resolve** — DNS not propagated yet. Wait and retry.
- **Port 80 blocked** — UFW or cloud firewall blocking HTTP. Ensure port 80 is open.
- **Cloudflare proxy enabled** — Disable the orange cloud (proxy) so Traefik handles TLS directly.
- **Rate limited** — Too many failed attempts. Wait 1 hour and retry.

#### Step 6: Update Zitadel for HTTPS

Once HTTPS is confirmed working, update Zitadel to use the secure domain:

```bash
# Update .env — Zitadel now uses the domain instead of IP
sed -i 's/^ADHARA_HOST=.*/ADHARA_HOST=engine.yourdomain.com/' .env

# Wipe Zitadel state (it bakes the domain into its database on first init)
docker compose down zitadel zitadel-login
docker volume rm adhara-engine_zitadel-bootstrap
# Note: Only remove pgdata if you haven't created users/apps you need to keep
docker volume rm adhara-engine_pgdata

# Restart everything
docker compose up -d

# Re-run Zitadel setup with the new domain
bash scripts/setup-zitadel.sh
```

Your Zitadel console will now be at `https://engine.yourdomain.com/ui/console/` and all OIDC flows will use HTTPS.

### Remote Admin Access

Internal services (Grafana, Traefik Dashboard, MinIO Console, etc.) are bound to localhost only. Access them via SSH tunnel:

```bash
ssh -L 8080:localhost:8080 -L 3003:localhost:3003 -L 9001:localhost:9001 user@your-server
```

Then open `http://localhost:8080` (Traefik), `http://localhost:3003` (Grafana), etc. locally.

## Zitadel Authentication Setup

Adhara Engine uses [Zitadel](https://zitadel.com) for OIDC authentication with PKCE flow.

### Step 1: Start the stack

```bash
make init    # or `make up` if already initialized
```

Wait for all services to be healthy:

```bash
make status
```

### Step 2: Run the Zitadel setup wizard

```bash
bash scripts/setup-zitadel.sh
```

This interactive script will:

1. Wait for Zitadel to become healthy
2. Open the Zitadel Console at **http://\<ADHARA_HOST\>/ui/console/** (routed through Traefik on port 80)
3. Walk you through creating an OIDC project and application
4. Collect the generated **Client ID**
5. Write the Client ID to `.env` and `ui/.env`

**Default Zitadel admin credentials:**
| Field | Value |
|-------|-------|
| Email | `zitadel-admin@zitadel.<ADHARA_HOST>` (e.g. `zitadel-admin@zitadel.localhost`) |
| Password | `Password1!` |

### Step 3: Configure the OIDC application in Zitadel Console

When the wizard prompts you, create the application with these settings:

| Setting | Value |
|---------|-------|
| **App Type** | User Agent |
| **Authentication Method** | PKCE |
| **Redirect URIs** | `http://<ADHARA_HOST>/auth/callback` |
|                    | `http://localhost/auth/callback` (for local dev) |
| **Post-Logout URIs** | `http://<ADHARA_HOST>` |
|                       | `http://localhost` (for local dev) |

> **Note:** Everything routes through Traefik on port 80. The redirect URIs must match `window.location.origin` exactly — no port number for port 80. Enable **Development Mode** in Zitadel to allow `http://` redirect URIs.

### Step 4: Create users

```bash
# Interactive mode
bash scripts/create-user.sh

# Batch mode
bash scripts/create-user.sh \
  --email user@example.com \
  --first John \
  --last Doe \
  --password 'SecurePass1!' \
  --role admin
```

Password requirements: min 8 characters, at least one uppercase, one number, one special character.

### Step 5: Restart the UI to pick up the new config

```bash
docker compose restart ui
```

Now visit **http://engine.localhost** — you'll be redirected to Zitadel login.

## Environment Variables

Copy the example and edit:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `ADHARA_HOST` | `localhost` | Server IP or hostname (used by Zitadel, API) |
| `ADHARA_DOMAIN` | *(unset)* | Domain for HTTPS (e.g. `engine.example.com`) |
| `ENGINE_SECRET_KEY` | `change-me-to-a-random-string` | API secret key |
| `POSTGRES_PASSWORD` | `engine` | PostgreSQL password |
| `MINIO_ACCESS_KEY` | `engine` | MinIO access key |
| `MINIO_SECRET_KEY` | `engine-secret` | MinIO secret key |
| `OIDC_INTERNAL_URL` | `http://logto:3001` | OIDC provider internal URL |
| `OIDC_ISSUER` | `http://localhost:3001` | OIDC issuer (external URL) |
| `ZITADEL_MASTERKEY` | *(32 chars required)* | Zitadel encryption key (zitadel profile only) |
| `ZITADEL_DB_PASSWORD` | `zitadel` | Zitadel database password (zitadel profile only) |
| `GRAFANA_PASSWORD` | `admin` | Grafana admin password |
| `ACME_EMAIL` | `admin@adharaweb.com` | Let's Encrypt email |
| `DOCKER_HOST_SOCKET` | `/var/run/docker.sock` | Docker socket path |
| `API_BACKEND` | `http://api:8000` | UI → API proxy target |

The UI also has its own env file at `ui/.env`:

| Variable | Description |
|----------|-------------|
| `VITE_OIDC_ISSUER` | OIDC issuer URL (e.g. `http://localhost:3001` for Logto) |
| `VITE_OIDC_CLIENT_ID` | OIDC Client ID (leave empty for token-only auth) |

## Make Targets

### Lifecycle

| Command | Description |
|---------|-------------|
| `make init` | Core services only (~500MB, token auth) |
| `make init-auth` | Core + Logto SSO (~650MB) |
| `make init-zitadel` | Core + Zitadel SSO (~1.3GB, enterprise) |
| `make init-full` | All services with Logto (~1.3GB) |
| `make up` / `up-auth` / `up-zitadel` / `up-full` | Start services (matching profile) |
| `make up-obs` | Core + observability (Grafana, Loki, Alloy) |
| `make down` | Stop all services (engine only) |
| `make restart` | Restart all services |
| `make clean` | Stop everything and remove volumes (**destructive**) |
| `make token` | Create a platform-admin API token and save to .env |

### Development

| Command | Description |
|---------|-------------|
| `make dev` | Start in dev mode (API hot-reloads on file changes) |
| `make build` | Rebuild all images with no cache |

### Database

| Command | Description |
|---------|-------------|
| `make db-migrate` | Run Alembic database migrations |
| `make db-seed` | Seed database with sample data |
| `make db-reset` | Reset database (**destructive**) |

### CLI (`adhara-engine`)

The CLI lets you manage tenants, workspaces, sites, and deployments from the command line.

**Install (requires Python 3.11+ and [uv](https://docs.astral.sh/uv/)):**

```bash
# Option 1: Install globally (adds adhara-engine to your PATH)
make install

# Option 2: Install in a local venv
make cli-install
source cli/.venv/bin/activate
```

**Configure the CLI to talk to your engine:**

```bash
# Local development
export ADHARA_ENGINE_URL=http://localhost:8000
export ADHARA_ENGINE_TOKEN=<your-api-token>

# Remote server
export ADHARA_ENGINE_URL=http://<your-server-ip>:8000
export ADHARA_ENGINE_TOKEN=<your-api-token>
```

Generate an API token from the dashboard: **API Tokens** (sidebar) → **+ New Token**.

**Usage:**

```bash
adhara-engine --help
adhara-engine tenant list
adhara-engine site create --workspace my-tenant/my-workspace --name "My Site" --source docker_image
adhara-engine site deploy my-tenant/my-workspace/my-site
```

### Monitoring

| Command | Description |
|---------|-------------|
| `make status` | Show status of all services |
| `make logs` | Tail logs from all services |
| `make logs-api` | Tail API logs only |
| `make logs-service SVC=traefik` | Tail logs for a specific service |

### Deployed Sites

| Command | Description |
|---------|-------------|
| `make sites-status` | Show all deployed site containers |
| `make sites-up` | Start previously stopped site containers |
| `make sites-down` | Stop and remove all deployed site containers |
| `make sites-restart` | Restart all deployed site containers |

## Service URLs

Once running, these services are available:

| Service | Local URL | Production | Access |
|---------|-----------|------------|--------|
| **Web UI** | http://localhost | http://\<ADHARA_HOST\> | Public (port 80) |
| **API** | http://localhost:8000 | via Traefik `/api/*` | Localhost only |
| **API Docs** | http://localhost:8000/docs | via Traefik `/docs` | Localhost only |
| **Zitadel Console** | http://localhost/ui/console/ | http://\<ADHARA_HOST\>/ui/console/ | Via Traefik (port 80) |
| **Traefik Dashboard** | http://localhost:8080 | SSH tunnel required | Localhost only |
| **Grafana** | http://localhost:3003 | SSH tunnel required | Localhost only |
| **MinIO Console** | http://localhost:9001 | SSH tunnel required | Localhost only |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19, TypeScript, Vite 7, Tailwind CSS 4, TanStack Query |
| **Backend** | FastAPI, SQLAlchemy, Alembic, Python 3.12 |
| **Auth** | API tokens (built-in), Logto OIDC, or Zitadel OIDC — PyJWT |
| **Database** | PostgreSQL 16, Redis 7 |
| **Proxy** | Traefik v3 (file-based routing + Let's Encrypt) |
| **Storage** | MinIO (S3-compatible) |
| **Logging** | Grafana Loki + Alloy → Grafana dashboards |
| **Registry** | Docker Registry v2 (local) |
| **CLI** | Typer + httpx + Rich |

## Further Documentation

| Guide | Description |
|-------|-------------|
| [Local Setup](docs/LOCAL_SETUP.md) | Detailed local development guide |
| [Deploying Sites](docs/DEPLOYING_SITES.md) | End-to-end deployment workflows |
| [Engine Integration](docs/ENGINE_INTEGRATION_GUIDE.md) | How to Dockerize apps for the engine |
| [GCP Deployment](docs/GCP_DEPLOYMENT.md) | Cloud deployment to Google Cloud |
| [Security Hardening](scripts/adhara-secure.sh) | UFW, HTTPS, port lockdown script |

## Troubleshooting

### Zitadel won't start

Zitadel needs the PostgreSQL `zitadel` database and user (created by `scripts/init-db.sql`). If the DB was initialized without this script:

```bash
docker compose exec db psql -U engine -c "CREATE USER zitadel WITH PASSWORD 'zitadel';"
docker compose exec db psql -U engine -c "CREATE DATABASE zitadel OWNER zitadel;"
docker compose restart zitadel
```

### "engine.localhost" doesn't resolve

Most modern browsers resolve `*.localhost` automatically. If yours doesn't, add to `/etc/hosts`:

```
127.0.0.1  engine.localhost
```

### OIDC login redirects fail

1. Verify `ZITADEL_CLIENT_ID` is set in both `.env` and `ui/.env`
2. Confirm redirect URIs match exactly in the Zitadel Console application settings
3. Restart the UI: `docker compose restart ui`

### Port conflicts

The default ports are: 80 (Traefik), 443, 5173 (UI), 8000 (API), 8080 (Traefik dash), 5432 (Postgres), 6379 (Redis), 3001/3002 (Logto OIDC/Admin), 3003 (Grafana), 3100 (Loki), 9000/9001 (MinIO), 5000 (Registry). Zitadel (if used) is routed through Traefik on port 80 (8081 localhost only).

Stop conflicting services or adjust ports in `docker-compose.yml`.

### Docker socket path (Colima / Podman)

Set `DOCKER_HOST_SOCKET` in `.env`:

```bash
# Colima
DOCKER_HOST_SOCKET=/Users/<you>/.colima/default/docker.sock

# Podman
DOCKER_HOST_SOCKET=/run/user/1000/podman/podman.sock
```

## License

Copyright (c) 2026 EIM Global Solutions, LLC. All rights reserved.

This is proprietary software. Unauthorized copying, distribution, modification, or use of this software, via any medium, is strictly prohibited without prior written consent from EIM Global Solutions, LLC.

See [LICENSE](LICENSE) for the full license text.
