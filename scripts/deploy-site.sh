#!/usr/bin/env bash
# ============================================================
# Adhara Engine — Site Deploy Script
# ============================================================
# Builds a Dockerized frontend, pushes it to the engine's
# local registry, creates tenant/workspace/site resources,
# and deploys.
#
# Usage:
#   bash scripts/deploy-site.sh [path-to-site-source]
#
# If no path is given, prompts interactively.
#
# Prerequisite: Adhara Engine must be running (see deploy.sh).
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

prompt_value() {
    local prompt="$1"
    local default="$2"
    echo -en "${BOLD}$prompt${NC} [${default}]: "
    read -r value
    echo "${value:-$default}"
}

check_command() {
    command -v "$1" &>/dev/null
}

# ── Resolve Engine Directory ─────────────────────────────────

if [[ -f "$(dirname "$0")/../docker-compose.yml" ]]; then
    ENGINE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
elif [[ -f "./docker-compose.yml" ]]; then
    ENGINE_DIR="$(pwd)"
else
    ENGINE_DIR="$HOME/adhara-engine"
fi

# ── Preflight ────────────────────────────────────────────────

preflight() {
    header "Preflight Checks"

    # Verify engine is running
    if ! docker compose -f "$ENGINE_DIR/docker-compose.yml" ps -q api &>/dev/null; then
        error "Adhara Engine does not appear to be running."
        error "Start it first: bash scripts/deploy.sh"
        exit 1
    fi
    success "Engine is running at $ENGINE_DIR"

    # Verify registry is accessible
    if ! curl -sf http://localhost:5000/v2/ &>/dev/null; then
        error "Docker registry not reachable at localhost:5000."
        error "Ensure the engine is running: make status"
        exit 1
    fi
    success "Registry reachable at localhost:5000"

    # Activate CLI
    if [[ -f "$ENGINE_DIR/cli/.venv/bin/activate" ]]; then
        # shellcheck disable=SC1091
        source "$ENGINE_DIR/cli/.venv/bin/activate"
    fi

    if ! check_command adhara-engine; then
        error "adhara-engine CLI not found."
        error "Install it: cd $ENGINE_DIR && make cli-install"
        exit 1
    fi
    success "CLI available: $(adhara-engine --help 2>&1 | head -1 || echo 'adhara-engine')"

    # Determine API URL
    API_URL="http://localhost:8000"
    if [[ -f "$ENGINE_DIR/.env" ]]; then
        local domain
        domain=$(grep '^DOMAIN=' "$ENGINE_DIR/.env" 2>/dev/null | cut -d= -f2 || true)
        if [[ -n "$domain" ]]; then
            API_URL="https://$domain"
        fi
    fi
    API_URL=$(prompt_value "Engine API URL" "$API_URL")
    export ADHARA_ENGINE_URL="$API_URL"
    info "Using API: $API_URL"
}

# ── Step 1: Build & Push Image ───────────────────────────────

step_build_push() {
    header "Step 1/3: Build & Push Docker Image"

    # Resolve site source path
    local site_path="${SITE_SOURCE_PATH:-}"
    if [[ -z "$site_path" ]]; then
        site_path=$(prompt_value "Path to site source (with Dockerfile)" "$HOME/jungle_habitas/jungle_habitas")
    fi

    if [[ ! -d "$site_path" ]]; then
        warn "Directory not found: $site_path"
        if confirm "Clone from git?" "y"; then
            local repo_url
            repo_url=$(prompt_value "Git repo URL" "")
            if [[ -z "$repo_url" ]]; then
                error "No repo URL provided."
                return 1
            fi
            git clone "$repo_url" "$site_path"
            success "Cloned to $site_path"
        else
            error "No source directory. Cannot build image."
            return 1
        fi
    fi

    # Find Dockerfile
    if [[ ! -f "$site_path/Dockerfile" ]]; then
        error "No Dockerfile found in $site_path"
        return 1
    fi
    success "Dockerfile found: $site_path/Dockerfile"

    # Image naming
    IMAGE_NAME=$(prompt_value "Image name" "jungle-habitas")
    IMAGE_TAG=$(prompt_value "Image tag" "latest")

    local registry="localhost:5000"
    REGISTRY_IMAGE="$registry/$IMAGE_NAME:$IMAGE_TAG"

    # Check if image already exists in registry
    if curl -sf "http://$registry/v2/$IMAGE_NAME/tags/list" 2>/dev/null | grep -q "\"$IMAGE_TAG\""; then
        success "Image $REGISTRY_IMAGE already exists in registry."
        if ! confirm "Rebuild and push?" "n"; then
            return 0
        fi
    fi

    info "Building $IMAGE_NAME:$IMAGE_TAG from $site_path..."
    docker build -t "$IMAGE_NAME:$IMAGE_TAG" "$site_path"
    success "Image built."

    info "Tagging for registry..."
    docker tag "$IMAGE_NAME:$IMAGE_TAG" "$REGISTRY_IMAGE"

    info "Pushing to $registry..."
    docker push "$REGISTRY_IMAGE"
    success "Pushed $REGISTRY_IMAGE"
}

# ── Step 2: Create Tenant / Workspace / Site ─────────────────

step_create_resources() {
    header "Step 2/3: Create Tenant, Workspace & Site"

    # Tenant
    TENANT_NAME=$(prompt_value "Tenant name" "jungle-habitas")
    local tenant_email
    tenant_email=$(prompt_value "Tenant email" "admin@junglehabitas.com")

    info "Creating tenant '$TENANT_NAME'..."
    adhara-engine tenant create --name "$TENANT_NAME" --email "$tenant_email" 2>/dev/null || {
        warn "Tenant may already exist — continuing."
    }

    # Workspace
    WORKSPACE_NAME=$(prompt_value "Workspace name" "production")

    info "Creating workspace '$WORKSPACE_NAME'..."
    adhara-engine workspace create --tenant "$TENANT_NAME" --name "$WORKSPACE_NAME" 2>/dev/null || {
        warn "Workspace may already exist — continuing."
    }

    # Site
    SITE_NAME=$(prompt_value "Site name" "jungle-habitas")
    local container_port
    container_port=$(prompt_value "Container port" "3000")

    info "Creating site '$SITE_NAME'..."
    adhara-engine site create \
        --workspace "$TENANT_NAME/$WORKSPACE_NAME" \
        --name "$SITE_NAME" \
        --source docker_image \
        --image "${REGISTRY_IMAGE:-localhost:5000/$SITE_NAME:latest}" \
        --port "$container_port" 2>/dev/null || {
        warn "Site may already exist — continuing."
    }

    SITE_PATH="$TENANT_NAME/$WORKSPACE_NAME/$SITE_NAME"
    success "Resources ready: $SITE_PATH"
}

# ── Step 3: Deploy ───────────────────────────────────────────

step_deploy() {
    header "Step 3/3: Deploy Site"

    local site_path="${SITE_PATH:-}"
    if [[ -z "$site_path" ]]; then
        site_path=$(prompt_value "Site path (tenant/workspace/site)" "")
        if [[ -z "$site_path" ]]; then
            error "No site path provided."
            return 1
        fi
    fi

    info "Deploying $site_path..."
    adhara-engine site deploy "$site_path"

    echo ""
    success "Site deployed!"

    # Show status
    info "Checking status..."
    adhara-engine site info "$site_path" 2>/dev/null || true

    # Print expected URL
    if [[ -f "$ENGINE_DIR/.env" ]]; then
        local domain
        domain=$(grep '^DOMAIN=' "$ENGINE_DIR/.env" 2>/dev/null | cut -d= -f2 || true)
        if [[ -n "$domain" ]]; then
            local tenant workspace site
            IFS='/' read -r tenant workspace site <<< "$site_path"
            echo ""
            info "Expected URL: https://${site}.${workspace}.${tenant}.${domain}"
            info "Add a custom domain: adhara-engine domain add $site_path <domain>"
        fi
    fi
}

# ── Main ─────────────────────────────────────────────────────

main() {
    echo ""
    echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║          Adhara Engine — Site Deploy Script              ║${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Accept optional source path as first argument
    if [[ -n "${1:-}" ]]; then
        SITE_SOURCE_PATH="$1"
        info "Site source: $SITE_SOURCE_PATH"
    fi
    echo ""

    preflight
    step_build_push
    step_create_resources
    step_deploy

    echo ""
    header "Site Deployment Complete!"
    info "Useful commands:"
    echo "  adhara-engine site status $SITE_PATH"
    echo "  adhara-engine site logs $SITE_PATH --follow"
    echo "  adhara-engine site restart $SITE_PATH"
    echo "  adhara-engine domain add $SITE_PATH <custom-domain>"
    echo ""
}

main "$@"
