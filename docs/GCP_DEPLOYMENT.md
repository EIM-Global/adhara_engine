# Adhara Engine — GCP VM Deployment Guide

Deploy the Adhara Engine to a Google Cloud Platform VM with real domains and SSL.

---

## VM Sizing

| Scale | VM Type | vCPU | RAM | Monthly Cost | Sites |
|-------|---------|------|-----|-------------|-------|
| Small (testing) | `e2-standard-2` | 2 | 8 GB | ~$49/mo | 5-15 |
| Standard | `e2-standard-4` | 4 | 16 GB | ~$97/mo | 15-50 |
| Large | `e2-standard-8` | 8 | 32 GB | ~$194/mo | 50-100+ |

**Disk:** 50 GB SSD minimum (100 GB recommended for image storage).

---

## Step 1: Create the VM

### Via gcloud CLI

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

### Via Console

1. Go to **Compute Engine > VM Instances > Create**
2. Name: `adhara-engine`
3. Region: Choose closest to your users
4. Machine type: `e2-standard-4`
5. Boot disk: Ubuntu 24.04 LTS, 100 GB SSD
6. Network tags: `adhara-engine`

---

## Step 2: Firewall Rules

```bash
# HTTP (required for Let's Encrypt ACME challenge + site traffic)
gcloud compute firewall-rules create adhara-allow-http \
  --allow=tcp:80 \
  --target-tags=adhara-engine \
  --description="Adhara Engine HTTP"

# HTTPS (site traffic with SSL)
gcloud compute firewall-rules create adhara-allow-https \
  --allow=tcp:443 \
  --target-tags=adhara-engine \
  --description="Adhara Engine HTTPS"

# API (optional — or route through Traefik instead)
gcloud compute firewall-rules create adhara-allow-api \
  --allow=tcp:8000 \
  --target-tags=adhara-engine \
  --description="Adhara Engine API"

# Traefik Dashboard (optional — restrict to your IP)
gcloud compute firewall-rules create adhara-allow-traefik \
  --allow=tcp:8080 \
  --target-tags=adhara-engine \
  --source-ranges="YOUR_IP/32" \
  --description="Adhara Engine Traefik Dashboard"

# Grafana (optional — restrict to your IP)
gcloud compute firewall-rules create adhara-allow-grafana \
  --allow=tcp:3001 \
  --target-tags=adhara-engine \
  --source-ranges="YOUR_IP/32" \
  --description="Adhara Engine Grafana"
```

**Important:** Do NOT expose ports 5432 (Postgres), 6379 (Redis), 9000/9001 (MinIO), or 8081 (Zitadel) to the internet.

---

## Step 3: Install Docker

SSH into the VM:

```bash
gcloud compute ssh adhara-engine --zone=us-central1-a
```

Install Docker:

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Log out and back in for group change
exit
gcloud compute ssh adhara-engine --zone=us-central1-a

# Verify
docker --version
docker compose version
```

Install Git:

```bash
sudo apt-get update && sudo apt-get install -y git
```

---

## Step 4: DNS Setup

Point your domain(s) to the VM's external IP:

```bash
# Get the VM's external IP
gcloud compute instances describe adhara-engine \
  --zone=us-central1-a \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```

Create DNS records at your registrar:

| Type | Name | Value |
|------|------|-------|
| A | `engine.adharaweb.com` | `<VM_IP>` |
| A | `*.engine.adharaweb.com` | `<VM_IP>` |

The wildcard record allows deployed sites to use subdomains like `mysite.engine.adharaweb.com`.

For custom site domains (e.g., `app.example.com`), the site owner adds a CNAME:

| Type | Name | Value |
|------|------|-------|
| CNAME | `app.example.com` | `engine.adharaweb.com` |

---

## Step 5: Deploy the Engine

```bash
# Clone the repo
git clone <repo-url> adhara-engine
cd adhara-engine

# Create and configure .env
cp .env.example .env
```

Edit `.env` with production values:

```bash
# IMPORTANT: Change all passwords for production!
ENGINE_SECRET_KEY=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 16)
MINIO_ACCESS_KEY=engine-prod
MINIO_SECRET_KEY=$(openssl rand -hex 16)
ZITADEL_MASTERKEY=$(openssl rand -hex 16)   # Must be exactly 32 chars
ZITADEL_DB_PASSWORD=$(openssl rand -hex 16)
GRAFANA_PASSWORD=$(openssl rand -hex 16)
ACME_EMAIL=admin@adharaweb.com
DOCKER_HOST_SOCKET=/var/run/docker.sock
```

Start the engine:

```bash
make init
```

Wait for all services to start:

```bash
make status
```

Run migrations and seed (optional):

```bash
make db-migrate
make db-seed   # Optional: creates sample tenant
```

---

## Step 6: Configure Traefik for Production

The default `traefik.yml` is already configured for Let's Encrypt. SSL certificates are automatically obtained for any custom domain that points to your VM.

### Route the API through Traefik (optional)

Create `traefik/dynamic/api.yml`:

```yaml
http:
  routers:
    api:
      rule: "Host(`engine.adharaweb.com`) && PathPrefix(`/api`)"
      entrypoints:
        - websecure
      service: api
      tls:
        certResolver: letsencrypt

    api-docs:
      rule: "Host(`engine.adharaweb.com`) && PathPrefix(`/docs`)"
      entrypoints:
        - websecure
      service: api
      tls:
        certResolver: letsencrypt

  services:
    api:
      loadBalancer:
        servers:
          - url: "http://api:8000"
```

This gives you `https://engine.adharaweb.com/api/v1/...` with automatic SSL.

### Route the Web UI through Traefik (when production-ready)

Build the UI and serve it via nginx or add another dynamic config for the UI container.

---

## Step 7: Verify

```bash
# Check services
make status

# Test API
curl https://engine.adharaweb.com/health

# Test via CLI (from your local machine)
adhara-engine --api-url https://engine.adharaweb.com status
adhara-engine --api-url https://engine.adharaweb.com tenant list
```

Deploy a test site:

```bash
export ADHARA_ENGINE_URL=https://engine.adharaweb.com

adhara-engine tenant create --name "Test" --email test@example.com
adhara-engine workspace create --tenant test --name "Production"
adhara-engine site create --workspace test/production --name "Hello" \
  --source docker_image --image nginx:alpine --port 80
adhara-engine site deploy test/production/hello
```

The site should be accessible at `https://hello.production.test.engine.adharaweb.com` (if you set up the wildcard DNS).

---

## Security Checklist

Before going live:

- [ ] Changed all default passwords in `.env`
- [ ] Firewall rules restrict admin ports (8080, 3001, 8081, 9001) to your IP
- [ ] PostgreSQL (5432), Redis (6379), MinIO (9000) are NOT exposed to internet
- [ ] `ACME_EMAIL` is set to a real email for Let's Encrypt notifications
- [ ] Zitadel is configured with real OAuth providers (Google, etc.)
- [ ] Traefik dashboard (`insecure: true`) is disabled or IP-restricted
- [ ] Regular database backups are configured (see Backup section)

---

## Backups

### Database

```bash
# Manual backup
docker compose exec db pg_dump -U engine adhara_engine > backup-$(date +%Y%m%d).sql

# Restore
docker compose exec -T db psql -U engine adhara_engine < backup-20260218.sql
```

### Automated daily backup (cron)

```bash
# Add to crontab: crontab -e
0 3 * * * cd /home/$USER/adhara-engine && docker compose exec -T db pg_dump -U engine adhara_engine | gzip > /home/$USER/backups/adhara-$(date +\%Y\%m\%d).sql.gz
```

### MinIO data

MinIO stores uploaded source archives. Back up the `minio-data` volume:

```bash
docker run --rm -v adhara-engine_minio-data:/data -v $(pwd):/backup alpine \
  tar czf /backup/minio-backup-$(date +%Y%m%d).tar.gz /data
```

---

## Monitoring

### Grafana (Log Viewer)

Access at `http://<VM_IP>:3001` (or through Traefik with SSL).

1. Log in: admin / (your GRAFANA_PASSWORD)
2. Add Loki data source: `http://loki:3100`
3. Explore > Select Loki > Query: `{container_name=~"ae-.*"}`

This shows logs from all deployed site containers.

### Resource monitoring

```bash
# Check Docker resource usage
docker stats

# Check disk usage
df -h
docker system df
```

---

## Updating

```bash
cd adhara-engine

# Pull latest code
git pull

# Rebuild and restart
make build
make up

# Run any new migrations
make db-migrate
```

---

## Scaling Considerations

### When to upgrade the VM
- CPU consistently above 70%
- Memory usage above 80%
- More than 30 concurrent running containers

### When to move to Kubernetes (Phase 4)
- Need auto-scaling based on traffic
- Need zero-downtime deployments
- Running 50+ sites
- Need multi-region deployment
- Need resource isolation between tenants

The engine is designed for this transition — the `DeployTarget` interface abstracts the deployment backend, so adding a Kubernetes target is a code change, not an architecture change.
