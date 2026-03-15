#!/usr/bin/env bash
set -euo pipefail

# ── Adhara Engine — Ubuntu Server Deploy Script ──────────────────────
# Run this on a fresh Ubuntu server (DigitalOcean, Hetzner, any VPS)
# to go from a bare OS to a running Adhara Engine in one command.
#
# What it does:
#   1. Creates a deploy user (if running as root)
#   2. Installs Docker, Docker Compose, Make, Git
#   3. Clones the Adhara Engine repo
#   4. Configures auth mode (token / Logto / Zitadel)
#   5. Generates secure secrets and starts the engine
#   6. Creates an API token for login
#   7. Optionally hardens security (UFW firewall)
#
# Usage (as root on a fresh server):
#   curl -fsSL https://raw.githubusercontent.com/EIM-Global/adhara_engine/main/scripts/deploy_ubuntu.sh | bash
#
# Or clone first, then run:
#   bash scripts/deploy_ubuntu.sh
#
# Tested on: Ubuntu 22.04 LTS, 24.04 LTS

# ── Colors & Helpers ─────────────────────────────────────────────────

BOLD="\033[1m"
DIM="\033[2m"
BLUE="\033[34m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
CYAN="\033[36m"
RESET="\033[0m"

info()  { echo -e "${BLUE}▸${RESET} $1"; }
ok()    { echo -e "${GREEN}✔${RESET} $1"; }
warn()  { echo -e "${YELLOW}⚠${RESET} $1"; }
err()   { echo -e "${RED}✘${RESET} $1"; exit 1; }
step()  { echo -e "\n${BOLD}${CYAN}── Step $1: $2 ${RESET}\n"; }

ask() {
  local prompt="$1" default="${2:-}"
  if [ -n "$default" ]; then
    echo -en "${BOLD}${prompt}${RESET} ${DIM}[${default}]${RESET}: " >&2
    read -r answer
    echo "${answer:-$default}"
  else
    echo -en "${BOLD}${prompt}${RESET}: " >&2
    read -r answer
    echo "$answer"
  fi
}

ask_yn() {
  local prompt="$1" default="${2:-y}"
  if [ "$default" = "y" ]; then
    echo -en "${BOLD}${prompt}${RESET} ${DIM}[Y/n]${RESET}: "
  else
    echo -en "${BOLD}${prompt}${RESET} ${DIM}[y/N]${RESET}: "
  fi
  read -r answer
  answer="${answer:-$default}"
  [[ "$answer" =~ ^[Yy] ]]
}

ask_choice() {
  local prompt="$1"; shift
  local options=("$@")
  echo -e "${BOLD}${prompt}${RESET}" >&2
  for i in "${!options[@]}"; do
    echo -e "  ${CYAN}$((i+1)))${RESET} ${options[$i]}" >&2
  done
  echo -en "${BOLD}Choice${RESET} ${DIM}[1]${RESET}: " >&2
  read -r choice
  choice="${choice:-1}"
  echo "${options[$((choice-1))]}"
}

# ── Banner ───────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}══════════════════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  Adhara Engine — Ubuntu Server Setup${RESET}"
echo -e "${BOLD}══════════════════════════════════════════════════════════════════${RESET}"
echo ""

# ── Preflight ────────────────────────────────────────────────────────

info "Checking system..."

# Must be Ubuntu/Debian
if ! command -v apt-get &>/dev/null; then
  err "This script requires an Ubuntu/Debian system (apt-get not found)."
fi

# Detect Ubuntu version
if [ -f /etc/os-release ]; then
  . /etc/os-release
  ok "OS: ${PRETTY_NAME:-Ubuntu}"
else
  warn "Could not detect OS version"
fi

# Detect if running as root
RUNNING_AS_ROOT=false
if [ "$(id -u)" -eq 0 ]; then
  RUNNING_AS_ROOT=true
  ok "Running as root"
else
  ok "Running as: $(whoami)"
fi

# Get server IP
SERVER_IP=$(curl -s --connect-timeout 5 ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
ok "Server IP: ${SERVER_IP}"

echo ""

# ══════════════════════════════════════════════════════════════════════
# Step 1: Deploy User
# ══════════════════════════════════════════════════════════════════════

DEPLOY_USER="$(whoami)"
ENGINE_DIR=""

if [ "$RUNNING_AS_ROOT" = true ]; then
  step 1 "Create Deploy User"

  info "A non-root user is needed to run the engine. Enter a username below."
  info "Press Enter to use the default 'deploy', or type a custom name."
  echo ""
  DEPLOY_USER=$(ask "Enter deploy username" "deploy")

  if id "$DEPLOY_USER" &>/dev/null; then
    ok "User '${DEPLOY_USER}' already exists"
  else
    info "Creating user '${DEPLOY_USER}'..."
    adduser --gecos "" "$DEPLOY_USER"
    ok "User '${DEPLOY_USER}' created"
  fi

  # Ensure sudo group
  if ! groups "$DEPLOY_USER" | grep -q sudo; then
    usermod -aG sudo "$DEPLOY_USER"
    ok "Added to sudo group"
  else
    ok "Already in sudo group"
  fi

  # Copy SSH keys from root
  if [ -f /root/.ssh/authorized_keys ]; then
    mkdir -p "/home/${DEPLOY_USER}/.ssh"
    cp /root/.ssh/authorized_keys "/home/${DEPLOY_USER}/.ssh/"
    chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "/home/${DEPLOY_USER}/.ssh"
    chmod 700 "/home/${DEPLOY_USER}/.ssh"
    chmod 600 "/home/${DEPLOY_USER}/.ssh/authorized_keys"
    ok "SSH keys copied from root"
  else
    warn "No SSH keys found at /root/.ssh/authorized_keys"
    warn "You'll need to set up SSH access for '${DEPLOY_USER}' manually"
  fi

  ENGINE_DIR="/home/${DEPLOY_USER}/projects/adhara_engine"
else
  step 1 "Deploy User"
  ok "Using current user: ${DEPLOY_USER}"
  ENGINE_DIR="${HOME}/projects/adhara_engine"
fi

# ══════════════════════════════════════════════════════════════════════
# Step 2: Install Docker
# ══════════════════════════════════════════════════════════════════════

step 2 "Install Docker"

if command -v docker &>/dev/null; then
  ok "Docker already installed: $(docker --version | head -1)"
else
  info "Installing Docker..."
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl gnupg >/dev/null 2>&1

  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null
  chmod a+r /etc/apt/keyrings/docker.gpg

  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list

  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null 2>&1

  ok "Docker installed: $(docker --version | head -1)"
fi

# Add deploy user to docker group
if ! groups "$DEPLOY_USER" 2>/dev/null | grep -q docker; then
  usermod -aG docker "$DEPLOY_USER"
  ok "Added '${DEPLOY_USER}' to docker group"
else
  ok "'${DEPLOY_USER}' already in docker group"
fi

# ══════════════════════════════════════════════════════════════════════
# Step 3: Install Make & Git
# ══════════════════════════════════════════════════════════════════════

step 3 "Install Make & Git"

apt-get update -qq
apt-get install -y -qq make git >/dev/null 2>&1
ok "Make and Git installed"

# ══════════════════════════════════════════════════════════════════════
# Step 4: Clone Repository
# ══════════════════════════════════════════════════════════════════════

step 4 "Clone Repository"

REPO_URL=$(ask "Git clone URL" "git@github.com:EIM-Global/adhara_engine.git")

# If SSH repo, ensure SSH key exists for deploy user
if [[ "$REPO_URL" == git@* ]]; then
  DEPLOY_HOME=$(eval echo "~${DEPLOY_USER}")
  SSH_KEY="${DEPLOY_HOME}/.ssh/id_ed25519"

  if [ ! -f "$SSH_KEY" ]; then
    info "Generating SSH key for GitHub access..."

    if [ "$RUNNING_AS_ROOT" = true ]; then
      su - "$DEPLOY_USER" -c "ssh-keygen -t ed25519 -C '${DEPLOY_USER}@adhara-engine' -f '${SSH_KEY}' -N ''"
    else
      ssh-keygen -t ed25519 -C "${DEPLOY_USER}@adhara-engine" -f "$SSH_KEY" -N ""
    fi

    echo ""
    echo -e "${BOLD}══════════════════════════════════════════════════════════════════${RESET}"
    echo -e "${BOLD}  Add this deploy key to GitHub:${RESET}"
    echo -e "${BOLD}══════════════════════════════════════════════════════════════════${RESET}"
    echo ""
    cat "${SSH_KEY}.pub"
    echo ""
    echo -e "  1. Go to ${CYAN}github.com/EIM-Global/adhara_engine/settings/keys${RESET}"
    echo -e "  2. Click ${BOLD}Add deploy key${RESET}"
    echo -e "  3. Paste the key above, check ${BOLD}Allow read access${RESET}"
    echo -e "  4. Click ${BOLD}Add key${RESET}"
    echo ""
    echo -en "${BOLD}Press Enter after adding the deploy key to GitHub...${RESET}"
    read -r
  else
    ok "SSH key already exists: ${SSH_KEY}"
  fi

  # Add GitHub to known hosts
  KNOWN_HOSTS="${DEPLOY_HOME}/.ssh/known_hosts"
  if ! grep -q "github.com" "$KNOWN_HOSTS" 2>/dev/null; then
    if [ "$RUNNING_AS_ROOT" = true ]; then
      su - "$DEPLOY_USER" -c "ssh-keyscan -t ed25519 github.com >> '${KNOWN_HOSTS}' 2>/dev/null"
    else
      ssh-keyscan -t ed25519 github.com >> "$KNOWN_HOSTS" 2>/dev/null
    fi
  fi
fi

# Clone the repo as the deploy user
if [ -d "$ENGINE_DIR" ]; then
  ok "Repository already exists at ${ENGINE_DIR}"
  if [ "$RUNNING_AS_ROOT" = true ]; then
    su - "$DEPLOY_USER" -c "cd '${ENGINE_DIR}' && git pull"
  else
    cd "$ENGINE_DIR" && git pull
  fi
else
  info "Cloning repository..."
  PARENT_DIR=$(dirname "$ENGINE_DIR")
  if [ "$RUNNING_AS_ROOT" = true ]; then
    su - "$DEPLOY_USER" -c "mkdir -p '${PARENT_DIR}' && cd '${PARENT_DIR}' && git clone '${REPO_URL}' adhara_engine"
  else
    mkdir -p "$PARENT_DIR"
    cd "$PARENT_DIR"
    git clone "$REPO_URL" adhara_engine
  fi
  ok "Repository cloned to ${ENGINE_DIR}"
fi

# ══════════════════════════════════════════════════════════════════════
# Step 5: Authentication Mode
# ══════════════════════════════════════════════════════════════════════

step 5 "Authentication Mode"

AUTH_CHOICE=$(ask_choice "Select authentication mode:" \
  "Token only   — Simple API tokens, no SSO (lightest, ~500MB)" \
  "Logto SSO    — Lightweight OIDC with admin console (~650MB)" \
  "Zitadel SSO  — Enterprise OIDC with multi-tenancy (~1.3GB)")

case "$AUTH_CHOICE" in
  Token*)    MAKE_TARGET="init";         PROFILE_DESC="core (token auth)" ;;
  Logto*)    MAKE_TARGET="init-auth";    PROFILE_DESC="core + Logto SSO" ;;
  Zitadel*)  MAKE_TARGET="init-zitadel"; PROFILE_DESC="core + Zitadel SSO" ;;
esac

# ══════════════════════════════════════════════════════════════════════
# Step 6: Optional Services
# ══════════════════════════════════════════════════════════════════════

step 6 "Optional Services"

EXTRA_PROFILES=""

if ask_yn "Enable Docker Registry (private image hosting, +30MB)" "y"; then
  EXTRA_PROFILES+=" --profile registry"
fi

if ask_yn "Enable Observability (Grafana + Loki + Alloy, +400MB)" "n"; then
  EXTRA_PROFILES+=" --profile observability"
fi

if ask_yn "Enable MinIO storage (S3-compatible object storage, +100MB)" "n"; then
  EXTRA_PROFILES+=" --profile storage"
fi

# ══════════════════════════════════════════════════════════════════════
# Step 7: Domain & HTTPS
# ══════════════════════════════════════════════════════════════════════

step 7 "Domain & HTTPS (optional)"

DOMAIN=""
ACME_EMAIL=""

if ask_yn "Configure a domain with auto-SSL (Let's Encrypt)" "n"; then
  DOMAIN=$(ask "Domain (e.g., engine.yourdomain.com)")
  ACME_EMAIL=$(ask "Email for Let's Encrypt notifications")
  echo ""
  warn "Make sure an A record for ${DOMAIN} points to ${SERVER_IP}"
fi

# ══════════════════════════════════════════════════════════════════════
# Confirmation
# ══════════════════════════════════════════════════════════════════════

echo ""
echo -e "${BOLD}══════════════════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  Deployment Summary${RESET}"
echo -e "${BOLD}══════════════════════════════════════════════════════════════════${RESET}"
echo ""
echo -e "  ${BOLD}Server IP:${RESET}      ${SERVER_IP}"
echo -e "  ${BOLD}Deploy user:${RESET}    ${DEPLOY_USER}"
echo -e "  ${BOLD}Engine dir:${RESET}     ${ENGINE_DIR}"
echo -e "  ${BOLD}Auth mode:${RESET}      ${PROFILE_DESC}"
[ -n "$EXTRA_PROFILES" ] && echo -e "  ${BOLD}Extra:${RESET}          ${EXTRA_PROFILES}"
if [ -n "$DOMAIN" ]; then
  echo -e "  ${BOLD}Domain:${RESET}         ${DOMAIN}"
else
  echo -e "  ${BOLD}Domain:${RESET}         (none — HTTP only)"
fi
echo ""

if ! ask_yn "Proceed with deployment?" "y"; then
  echo "Aborted."
  exit 0
fi

# ══════════════════════════════════════════════════════════════════════
# Step 8: Configure & Start Engine
# ══════════════════════════════════════════════════════════════════════

step 8 "Starting Adhara Engine"

# Build the startup commands to run as the deploy user
STARTUP_CMDS="cd '${ENGINE_DIR}'

# Generate .env with secure random secrets
if [ ! -f .env ]; then
  make .env
fi
"

# Set ADHARA_HOST
if [ -n "$DOMAIN" ]; then
  STARTUP_CMDS+="
sed -i 's|^# ADHARA_HOST=.*|ADHARA_HOST=${DOMAIN}|' .env
grep -q '^ADHARA_HOST=' .env || echo 'ADHARA_HOST=${DOMAIN}' >> .env
grep -q '^ADHARA_DOMAIN=' .env || echo 'ADHARA_DOMAIN=${DOMAIN}' >> .env
if [ -n '${ACME_EMAIL}' ]; then
  grep -q '^ACME_EMAIL=' .env && sed -i 's|^ACME_EMAIL=.*|ACME_EMAIL=${ACME_EMAIL}|' .env || echo 'ACME_EMAIL=${ACME_EMAIL}' >> .env
fi
"
else
  STARTUP_CMDS+="
grep -q '^ADHARA_HOST=' .env && sed -i 's|^ADHARA_HOST=.*|ADHARA_HOST=${SERVER_IP}|' .env || echo 'ADHARA_HOST=${SERVER_IP}' >> .env
"
fi

# Start engine
STARTUP_CMDS+="
echo ''
echo 'Starting Adhara Engine (${PROFILE_DESC})...'
make ${MAKE_TARGET}
"

# Start optional profiles
if [ -n "$EXTRA_PROFILES" ]; then
  STARTUP_CMDS+="
echo 'Starting optional services...'
docker compose ${EXTRA_PROFILES} up -d
"
fi

# Generate token
STARTUP_CMDS+="
echo ''
echo 'Creating API token...'
make token
"

# Run everything as the deploy user
info "Building and starting services (this may take a few minutes)..."
echo ""

if [ "$RUNNING_AS_ROOT" = true ]; then
  # Use sg to activate docker group in the same session
  su - "$DEPLOY_USER" -c "sg docker -c \"$STARTUP_CMDS\""
else
  eval "$STARTUP_CMDS"
fi

# ══════════════════════════════════════════════════════════════════════
# Step 9: Security Hardening (optional)
# ══════════════════════════════════════════════════════════════════════

step 9 "Security Hardening (optional)"

if ask_yn "Run security hardening (UFW firewall + port lockdown)?" "n"; then
  if [ -f "${ENGINE_DIR}/scripts/adhara-secure.sh" ]; then
    if [ "$RUNNING_AS_ROOT" = true ]; then
      bash "${ENGINE_DIR}/scripts/adhara-secure.sh"
    else
      sudo bash "${ENGINE_DIR}/scripts/adhara-secure.sh"
    fi
    ok "Security hardening complete"
  else
    warn "adhara-secure.sh not found — skipping"
  fi
fi

# ══════════════════════════════════════════════════════════════════════
# Done
# ══════════════════════════════════════════════════════════════════════

echo ""
echo -e "${BOLD}${GREEN}══════════════════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}${GREEN}  Adhara Engine is running!${RESET}"
echo -e "${BOLD}${GREEN}══════════════════════════════════════════════════════════════════${RESET}"
echo ""

if [ -n "$DOMAIN" ]; then
  echo -e "  ${BOLD}Dashboard:${RESET}  https://${DOMAIN}"
else
  echo -e "  ${BOLD}Dashboard:${RESET}  http://${SERVER_IP}"
fi
echo -e "  ${BOLD}Auth:${RESET}       ${PROFILE_DESC}"
echo -e "  ${BOLD}User:${RESET}       ${DEPLOY_USER}"
echo -e "  ${BOLD}Engine:${RESET}     ${ENGINE_DIR}"
echo ""
echo -e "  Log in with the API token printed above."
echo ""

if [ "$RUNNING_AS_ROOT" = true ]; then
  echo -e "  ${BOLD}Next steps:${RESET}"
  echo -e "    1. Log out of root: ${CYAN}exit${RESET}"
  echo -e "    2. SSH as deploy:   ${CYAN}ssh ${DEPLOY_USER}@${SERVER_IP}${RESET}"
  echo -e "    3. Open dashboard:  ${CYAN}http://${SERVER_IP}${RESET}"
  echo ""
  warn "Always SSH as '${DEPLOY_USER}' from now on — not root."
fi

echo ""
