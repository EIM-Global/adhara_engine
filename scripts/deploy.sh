#!/usr/bin/env bash
# ============================================================
# Adhara Engine — GCP VM Deploy Script
# ============================================================
# Automates the full deployment pipeline from a bare Ubuntu VM
# to a running Adhara Engine platform.
#
# Usage:
#   bash scripts/deploy.sh
#
# Safe to run multiple times — detects existing state and
# offers to skip completed steps.
# ============================================================

set -euo pipefail

# ── Colors & Output Helpers ──────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

info()    { echo -e "${BLUE}ℹ${NC}  $*"; }
success() { echo -e "${GREEN}✔${NC}  $*"; }
warn()    { echo -e "${YELLOW}⚠${NC}  $*"; }
error()   { echo -e "${RED}✖${NC}  $*" >&2; }
header()  { echo -e "\n${BOLD}═══ $* ═══${NC}\n"; }

# ── Interactive Helpers ──────────────────────────────────────

# confirm PROMPT DEFAULT
#   DEFAULT: y or n (controls what happens on Enter)
confirm() {
    local prompt="$1"
    local default="${2:-y}"
    local hint

    if [[ "$default" == "y" ]]; then
        hint="[Y/n]"
    else
        hint="[y/N]"
    fi

    while true; do
        echo -en "${BOLD}$prompt ${hint}:${NC} "
        read -r answer
        answer="${answer:-$default}"
        case "${answer,,}" in
            y|yes) return 0 ;;
            n|no)  return 1 ;;
            *)     echo "Please answer y or n." ;;
        esac
    done
}

# prompt_value PROMPT DEFAULT
#   Returns user input or default
prompt_value() {
    local prompt="$1"
    local default="$2"
    echo -en "${BOLD}$prompt${NC} [${default}]: "
    read -r value
    echo "${value:-$default}"
}

# check_command CMD
#   Returns 0 if command exists
check_command() {
    command -v "$1" &>/dev/null
}

# ── Engine Directory ─────────────────────────────────────────

# Determine the engine root directory.
# If we're already inside the repo, use that. Otherwise default to ~/adhara-engine.
if [[ -f "$(dirname "$0")/../docker-compose.yml" ]]; then
    ENGINE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
elif [[ -f "./docker-compose.yml" ]]; then
    ENGINE_DIR="$(pwd)"
else
    ENGINE_DIR="$HOME/adhara-engine"
fi

# ── Step 1: Install Docker ──────────────────────────────────

step_install_docker() {
    header "Step 1/5: Install Docker"

    if check_command docker; then
        local ver
        ver=$(docker --version 2>/dev/null || echo "unknown")
        success "Docker found: $ver"
        if confirm "Skip Docker install?" "y"; then
            return 0
        fi
    fi

    info "Installing Docker via get.docker.com..."
    curl -fsSL https://get.docker.com | sh

    if ! groups "$USER" | grep -q docker; then
        info "Adding $USER to docker group..."
        sudo usermod -aG docker "$USER"
        warn "Group change requires re-login. After this script finishes,"
        warn "log out and back in, then re-run the script to continue."
    fi

    success "Docker installed: $(docker --version)"
}

# ── Step 2: Install Docker Compose ───────────────────────────

step_install_compose() {
    header "Step 2/5: Install Docker Compose"

    if docker compose version &>/dev/null; then
        local ver
        ver=$(docker compose version 2>/dev/null || echo "unknown")
        success "Docker Compose found: $ver"
        if confirm "Skip Docker Compose install?" "y"; then
            return 0
        fi
    fi

    info "Installing Docker Compose plugin..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq docker-compose-plugin

    success "Docker Compose installed: $(docker compose version)"
}

# ── Step 3: Install Git & Clone Repo ─────────────────────────

step_clone_repo() {
    header "Step 3/5: Install Git & Clone Repo"

    # Ensure git is installed
    if ! check_command git; then
        info "Installing git..."
        sudo apt-get update -qq
        sudo apt-get install -y -qq git
        success "Git installed."
    else
        success "Git found: $(git --version)"
    fi

    # Check if engine directory already exists with docker-compose.yml
    if [[ -f "$ENGINE_DIR/docker-compose.yml" ]]; then
        success "Repo already exists at $ENGINE_DIR"
        if confirm "Skip clone?" "y"; then
            return 0
        fi
    fi

    local default_url="https://github.com/your-org/adhara-engine.git"
    local repo_url
    repo_url=$(prompt_value "Git repo URL" "$default_url")

    info "Cloning into $ENGINE_DIR..."
    git clone "$repo_url" "$ENGINE_DIR"
    success "Repo cloned to $ENGINE_DIR"
}

# ── Step 4: Configure Environment ────────────────────────────

step_configure_env() {
    header "Step 4/5: Configure Environment"

    cd "$ENGINE_DIR"

    if [[ -f ".env" ]]; then
        success "Existing .env found."
        if ! confirm "Reconfigure .env?" "n"; then
            return 0
        fi
        local backup=".env.backup.$(date +%Y%m%d%H%M%S)"
        cp .env "$backup"
        info "Backed up existing .env to $backup"
    fi

    echo ""
    info "Let's configure your environment."
    echo ""

    # User-facing config
    local domain
    domain=$(prompt_value "Domain (e.g. engine.adharaweb.com)" "engine.adharaweb.com")

    local acme_email
    acme_email=$(prompt_value "ACME email for Let's Encrypt" "admin@adharaweb.com")

    local docker_socket
    docker_socket=$(prompt_value "Docker socket path" "/var/run/docker.sock")

    # Auto-generate secrets
    info "Generating secrets..."
    local engine_secret minio_secret postgres_pw zitadel_mk zitadel_db_pw grafana_pw
    engine_secret=$(openssl rand -hex 32)
    postgres_pw=$(openssl rand -hex 16)
    minio_secret=$(openssl rand -hex 16)
    zitadel_mk=$(openssl rand -hex 16)       # exactly 32 hex chars
    zitadel_db_pw=$(openssl rand -hex 16)
    grafana_pw=$(openssl rand -hex 16)

    # Write .env
    cat > .env <<ENVEOF
# ============================================================
# Adhara Engine - Environment Variables
# Generated by deploy.sh on $(date -u +"%Y-%m-%d %H:%M:%S UTC")
# ============================================================

# ── Core ─────────────────────────────────────────────────────
ENGINE_SECRET_KEY=${engine_secret}

# ── PostgreSQL ───────────────────────────────────────────────
POSTGRES_PASSWORD=${postgres_pw}

# ── MinIO (Object Storage) ──────────────────────────────────
MINIO_ACCESS_KEY=engine-prod
MINIO_SECRET_KEY=${minio_secret}

# ── Zitadel (Authentication) ────────────────────────────────
ZITADEL_MASTERKEY=${zitadel_mk}
ZITADEL_DB_PASSWORD=${zitadel_db_pw}

# ── Grafana ──────────────────────────────────────────────────
GRAFANA_PASSWORD=${grafana_pw}

# ── Traefik / SSL ────────────────────────────────────────────
ACME_EMAIL=${acme_email}

# ── Docker Socket ────────────────────────────────────────────
DOCKER_HOST_SOCKET=${docker_socket}

# ── Domain ───────────────────────────────────────────────────
DOMAIN=${domain}
ENVEOF

    success ".env written."
    echo ""
    info "Generated credentials (save these somewhere safe!):"
    echo "  ENGINE_SECRET_KEY  = ${engine_secret}"
    echo "  POSTGRES_PASSWORD  = ${postgres_pw}"
    echo "  MINIO_SECRET_KEY   = ${minio_secret}"
    echo "  ZITADEL_MASTERKEY  = ${zitadel_mk}"
    echo "  ZITADEL_DB_PASSWORD= ${zitadel_db_pw}"
    echo "  GRAFANA_PASSWORD   = ${grafana_pw}"
    echo ""

    # Generate Traefik dynamic config for API routing
    info "Generating Traefik API routing config..."
    mkdir -p traefik/dynamic

    cat > traefik/dynamic/engine.yml <<TRAEFIKEOF
# Auto-generated by deploy.sh — routes API + UI through Traefik with SSL
http:
  routers:
    # API routes (higher priority — PathPrefix is more specific)
    api:
      rule: "Host(\`${domain}\`) && PathPrefix(\`/api\`)"
      entrypoints:
        - websecure
      service: api
      tls:
        certResolver: letsencrypt

    api-docs:
      rule: "Host(\`${domain}\`) && PathPrefix(\`/docs\`)"
      entrypoints:
        - websecure
      service: api
      tls:
        certResolver: letsencrypt

    # UI catches everything else on the domain
    ui:
      rule: "Host(\`${domain}\`)"
      entrypoints:
        - websecure
      service: ui
      tls:
        certResolver: letsencrypt
      priority: 1

  services:
    api:
      loadBalancer:
        servers:
          - url: "http://api:8000"
    ui:
      loadBalancer:
        servers:
          - url: "http://ui:5173"
TRAEFIKEOF

    success "traefik/dynamic/engine.yml generated for ${domain}"
}

# ── Step 5: Start Adhara Engine ──────────────────────────────

wait_healthy() {
    local max_wait="${1:-120}"
    local elapsed=0
    local interval=5

    info "Waiting for services to become healthy (up to ${max_wait}s)..."

    while (( elapsed < max_wait )); do
        # Count unhealthy/starting containers
        local not_ready
        not_ready=$(docker compose ps --format json 2>/dev/null \
            | grep -c -v '"healthy"' || true)

        if (( not_ready == 0 )); then
            return 0
        fi

        sleep "$interval"
        elapsed=$((elapsed + interval))
        echo -ne "\r  ⏳ ${elapsed}s / ${max_wait}s — waiting..."
    done

    echo ""
    warn "Some services may not be fully healthy yet. Check with: make status"
    return 1
}

step_start_engine() {
    header "Step 5/5: Start Adhara Engine"

    cd "$ENGINE_DIR"

    # Check if containers are already running
    local running
    running=$(docker compose ps -q 2>/dev/null | wc -l | tr -d ' ')

    if (( running > 0 )); then
        success "$running containers already running."
        docker compose ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null || true
        echo ""
        if confirm "Restart engine?" "n"; then
            info "Restarting..."
            docker compose down
        else
            info "Skipping engine start."
            # Still run migrations in case they're pending
            if confirm "Run database migrations?" "y"; then
                info "Running migrations..."
                docker compose exec api alembic upgrade head
                success "Migrations complete."
            fi
            return 0
        fi
    fi

    info "Starting Adhara Engine (this may take a few minutes on first run)..."
    make init

    wait_healthy 180 || true

    echo ""
    info "Running database migrations..."
    docker compose exec api alembic upgrade head
    success "Migrations complete."

    # Install CLI
    if [[ -d "cli" ]]; then
        echo ""
        if confirm "Install adhara-engine CLI?" "y"; then
            info "Installing CLI..."
            if check_command uv; then
                (cd cli && uv venv .venv && . .venv/bin/activate && uv pip install -e .)
            elif check_command python3; then
                (cd cli && python3 -m venv .venv && . .venv/bin/activate && pip install -e .)
            else
                warn "Neither uv nor python3 found. Skipping CLI install."
                warn "Install manually: cd cli && python3 -m venv .venv && pip install -e ."
                return 0
            fi
            success "CLI installed. Activate with: source cli/.venv/bin/activate"
        fi
    fi
}

# ── Main ─────────────────────────────────────────────────────

main() {
    echo ""
    echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║          Adhara Engine — GCP VM Deploy Script           ║${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    info "Engine directory: $ENGINE_DIR"
    echo ""

    step_install_docker
    step_install_compose
    step_clone_repo
    step_configure_env
    step_start_engine

    echo ""
    header "Platform Deployment Complete!"
    success "Adhara Engine is running at $ENGINE_DIR"
    if [[ -f "$ENGINE_DIR/.env" ]]; then
        local domain
        domain=$(grep '^DOMAIN=' "$ENGINE_DIR/.env" 2>/dev/null | cut -d= -f2 || true)
        if [[ -n "$domain" ]]; then
            info "API:     https://${domain}/api/v1/"
            info "Health:  https://${domain}/health"
        fi
    fi
    echo ""
    info "Useful commands:"
    echo "  cd $ENGINE_DIR"
    echo "  make status        # Check service health"
    echo "  make logs          # Tail all logs"
    echo "  make logs-api      # Tail API logs"
    echo ""
}

main "$@"
