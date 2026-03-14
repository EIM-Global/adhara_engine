#!/usr/bin/env bash
set -euo pipefail

# ── Adhara Engine — GCP Deployment Wizard ────────────────────────────
# Fully automated deployment to a Google Cloud Platform VM.
# Creates the VM, installs Docker, clones the repo, and starts the engine.
#
# Prerequisites:
#   - gcloud CLI installed and authenticated (gcloud auth login)
#   - A GCP project selected (gcloud config set project PROJECT_ID)
#   - SSH key configured (gcloud compute config-ssh)
#
# Usage:
#   bash scripts/deploy_gcp.sh
#
# The script will walk you through all options interactively.

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
err()   { echo -e "${RED}✘${RESET} $1"; }
step()  { echo -e "\n${BOLD}${CYAN}── Step $1: $2 ${RESET}"; echo ""; }
banner() {
  echo ""
  echo -e "${BOLD}══════════════════════════════════════════════════════════════════${RESET}"
  echo -e "${BOLD}  Adhara Engine — GCP Deployment Wizard${RESET}"
  echo -e "${BOLD}══════════════════════════════════════════════════════════════════${RESET}"
  echo ""
}

ask() {
  local prompt="$1"
  local default="${2:-}"
  if [ -n "$default" ]; then
    echo -en "${BOLD}${prompt}${RESET} ${DIM}[${default}]${RESET}: "
    read -r answer
    echo "${answer:-$default}"
  else
    echo -en "${BOLD}${prompt}${RESET}: "
    read -r answer
    echo "$answer"
  fi
}

ask_yn() {
  local prompt="$1"
  local default="${2:-y}"
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
  local prompt="$1"
  shift
  local options=("$@")
  echo -e "${BOLD}${prompt}${RESET}"
  for i in "${!options[@]}"; do
    echo -e "  ${CYAN}$((i+1)))${RESET} ${options[$i]}"
  done
  echo -en "${BOLD}Choice${RESET} ${DIM}[1]${RESET}: "
  read -r choice
  choice="${choice:-1}"
  echo "${options[$((choice-1))]}"
}

# ── Preflight Checks ────────────────────────────────────────────────

banner

info "Checking prerequisites..."

if ! command -v gcloud &>/dev/null; then
  err "gcloud CLI not found. Install it: https://cloud.google.com/sdk/docs/install"
  exit 1
fi
ok "gcloud CLI found"

GCP_PROJECT=$(gcloud config get-value project 2>/dev/null || true)
if [ -z "$GCP_PROJECT" ] || [ "$GCP_PROJECT" = "(unset)" ]; then
  err "No GCP project set. Run: gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi
ok "GCP project: ${GCP_PROJECT}"

GCP_ACCOUNT=$(gcloud config get-value account 2>/dev/null || true)
if [ -z "$GCP_ACCOUNT" ] || [ "$GCP_ACCOUNT" = "(unset)" ]; then
  err "Not authenticated. Run: gcloud auth login"
  exit 1
fi
ok "Authenticated as: ${GCP_ACCOUNT}"

echo ""

# ── Step 1: VM Configuration ────────────────────────────────────────

step 1 "VM Configuration"

VM_NAME=$(ask "VM name" "adhara-engine")

echo ""
ZONE_CHOICE=$(ask_choice "Select a zone:" \
  "us-central1-a (Iowa)" \
  "us-east1-b (South Carolina)" \
  "us-west1-a (Oregon)" \
  "europe-west1-b (Belgium)" \
  "asia-east1-a (Taiwan)" \
  "Enter custom zone")

if [[ "$ZONE_CHOICE" == "Enter custom zone" ]]; then
  VM_ZONE=$(ask "Custom zone")
else
  VM_ZONE=$(echo "$ZONE_CHOICE" | cut -d' ' -f1)
fi

echo ""
SIZE_CHOICE=$(ask_choice "Select VM size:" \
  "e2-standard-2  — 2 vCPU, 8 GB RAM (~\$49/mo, 5-15 sites)" \
  "e2-standard-4  — 4 vCPU, 16 GB RAM (~\$97/mo, 15-50 sites)" \
  "e2-standard-8  — 8 vCPU, 32 GB RAM (~\$194/mo, 50-100+ sites)")

VM_TYPE=$(echo "$SIZE_CHOICE" | awk '{print $1}')

DISK_SIZE=$(ask "Boot disk size (GB)" "100")

# ── Step 2: Authentication Mode ─────────────────────────────────────

step 2 "Authentication"

echo -e "Adhara Engine supports three authentication modes:"
echo ""
AUTH_CHOICE=$(ask_choice "Select authentication mode:" \
  "Token only   — Simple API tokens, no SSO (lightest, ~500MB)" \
  "Logto SSO    — Lightweight OIDC with admin console (~650MB)" \
  "Zitadel SSO  — Enterprise OIDC with multi-tenancy (~1.3GB)")

case "$AUTH_CHOICE" in
  Token*)    AUTH_MODE="token";   MAKE_TARGET="init";         PROFILE_DESC="core (token auth)" ;;
  Logto*)    AUTH_MODE="logto";   MAKE_TARGET="init-auth";    PROFILE_DESC="core + Logto SSO" ;;
  Zitadel*)  AUTH_MODE="zitadel"; MAKE_TARGET="init-zitadel"; PROFILE_DESC="core + Zitadel SSO" ;;
esac

# ── Step 3: Optional Services ───────────────────────────────────────

step 3 "Optional Services"

ENABLE_REGISTRY=false
ENABLE_OBS=false
ENABLE_STORAGE=false

if ask_yn "Enable Docker Registry (private image hosting, +30MB)" "y"; then
  ENABLE_REGISTRY=true
fi

if ask_yn "Enable Observability (Grafana + Loki + Alloy, +400MB)" "n"; then
  ENABLE_OBS=true
fi

if ask_yn "Enable MinIO storage (S3-compatible object storage, +100MB)" "n"; then
  ENABLE_STORAGE=true
fi

# ── Step 4: Domain & HTTPS ──────────────────────────────────────────

step 4 "Domain & HTTPS (optional)"

DOMAIN=""
ACME_EMAIL=""

if ask_yn "Configure a domain with auto-SSL (Let's Encrypt)" "n"; then
  DOMAIN=$(ask "Domain (e.g., engine.yourdomain.com)")
  ACME_EMAIL=$(ask "Email for Let's Encrypt notifications")
  echo ""
  warn "Make sure an A record for ${DOMAIN} points to the VM's IP before HTTPS will work."
  warn "You can set this up after the VM is created — the script will show you the IP."
fi

# ── Step 5: GitHub Access ───────────────────────────────────────────

step 5 "Repository Access"

REPO_URL=$(ask "Git clone URL" "git@github.com:EIM-Global/adhara_engine.git")

# ── Confirmation ─────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}══════════════════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  Deployment Summary${RESET}"
echo -e "${BOLD}══════════════════════════════════════════════════════════════════${RESET}"
echo ""
echo -e "  ${BOLD}GCP Project:${RESET}    ${GCP_PROJECT}"
echo -e "  ${BOLD}VM Name:${RESET}        ${VM_NAME}"
echo -e "  ${BOLD}Zone:${RESET}           ${VM_ZONE}"
echo -e "  ${BOLD}Machine Type:${RESET}   ${VM_TYPE}"
echo -e "  ${BOLD}Disk:${RESET}           ${DISK_SIZE} GB SSD"
echo -e "  ${BOLD}Auth Mode:${RESET}      ${AUTH_MODE} (${PROFILE_DESC})"
echo -e "  ${BOLD}Registry:${RESET}       ${ENABLE_REGISTRY}"
echo -e "  ${BOLD}Observability:${RESET}  ${ENABLE_OBS}"
echo -e "  ${BOLD}Storage:${RESET}        ${ENABLE_STORAGE}"
if [ -n "$DOMAIN" ]; then
  echo -e "  ${BOLD}Domain:${RESET}         ${DOMAIN}"
  echo -e "  ${BOLD}ACME Email:${RESET}     ${ACME_EMAIL}"
else
  echo -e "  ${BOLD}Domain:${RESET}         (none — HTTP only)"
fi
echo -e "  ${BOLD}Repo:${RESET}           ${REPO_URL}"
echo ""

if ! ask_yn "Proceed with deployment?" "y"; then
  echo "Aborted."
  exit 0
fi

# ── Step 6: Create Firewall Rules ────────────────────────────────────

step 6 "Creating Firewall Rules"

# Check if rules already exist before creating
if ! gcloud compute firewall-rules describe adhara-allow-http &>/dev/null 2>&1; then
  info "Creating HTTP firewall rule..."
  gcloud compute firewall-rules create adhara-allow-http \
    --allow=tcp:80 \
    --target-tags=adhara-engine \
    --description="Adhara Engine HTTP" \
    --quiet
  ok "HTTP (port 80) — open"
else
  ok "HTTP firewall rule already exists"
fi

if ! gcloud compute firewall-rules describe adhara-allow-https &>/dev/null 2>&1; then
  info "Creating HTTPS firewall rule..."
  gcloud compute firewall-rules create adhara-allow-https \
    --allow=tcp:443 \
    --target-tags=adhara-engine \
    --description="Adhara Engine HTTPS" \
    --quiet
  ok "HTTPS (port 443) — open"
else
  ok "HTTPS firewall rule already exists"
fi

# ── Step 7: Create VM ───────────────────────────────────────────────

step 7 "Creating VM"

if gcloud compute instances describe "$VM_NAME" --zone="$VM_ZONE" &>/dev/null 2>&1; then
  warn "VM '${VM_NAME}' already exists in ${VM_ZONE}"
  if ! ask_yn "Use existing VM and skip creation?" "y"; then
    err "Aborting. Delete the existing VM first or choose a different name."
    exit 1
  fi
else
  info "Creating VM: ${VM_NAME} (${VM_TYPE}) in ${VM_ZONE}..."
  gcloud compute instances create "$VM_NAME" \
    --zone="$VM_ZONE" \
    --machine-type="$VM_TYPE" \
    --boot-disk-size="${DISK_SIZE}GB" \
    --boot-disk-type=pd-ssd \
    --image-family=ubuntu-2404-lts-amd64 \
    --image-project=ubuntu-os-cloud \
    --tags=adhara-engine \
    --quiet
  ok "VM created"
fi

# Get the external IP
VM_IP=$(gcloud compute instances describe "$VM_NAME" \
  --zone="$VM_ZONE" \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
ok "External IP: ${VM_IP}"

if [ -n "$DOMAIN" ]; then
  echo ""
  warn "Point an A record for ${DOMAIN} → ${VM_IP} now (if you haven't already)."
  echo ""
fi

# ── Step 8: Provision the VM ────────────────────────────────────────

step 8 "Provisioning VM (Docker, Git, Make, clone repo)"

# Build the provisioning script to run on the VM
PROVISION_SCRIPT=$(cat <<'REMOTE_SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

echo "── Installing Docker ──"
if command -v docker &>/dev/null; then
  echo "Docker already installed: $(docker --version)"
else
  curl -fsSL https://get.docker.com | sh
  echo "Docker installed: $(docker --version)"
fi

# Add current user to docker group
if ! groups | grep -q docker; then
  sudo usermod -aG docker "$USER"
  echo "Added $USER to docker group (will take effect on next login)"
fi

echo "── Installing Make and Git ──"
sudo apt-get update -qq
sudo apt-get install -y -qq make git > /dev/null

echo "── Cloning repository ──"
REMOTE_SCRIPT
)

# Append repo-specific commands with variable substitution
PROVISION_SCRIPT+="
REPO_URL=\"${REPO_URL}\"
"

PROVISION_SCRIPT+='
mkdir -p ~/projects
cd ~/projects

if [ -d "adhara_engine" ]; then
  echo "Repository already exists, pulling latest..."
  cd adhara_engine && git pull
else
  # If using SSH, check for key
  if [[ "$REPO_URL" == git@* ]]; then
    if [ ! -f ~/.ssh/id_ed25519 ]; then
      echo "── Generating SSH key for GitHub access ──"
      ssh-keygen -t ed25519 -C "deploy@adhara-engine" -f ~/.ssh/id_ed25519 -N ""
      echo ""
      echo "═══════════════════════════════════════════════════════════════"
      echo "  ADD THIS DEPLOY KEY TO GITHUB:"
      echo "═══════════════════════════════════════════════════════════════"
      echo ""
      cat ~/.ssh/id_ed25519.pub
      echo ""
      echo "═══════════════════════════════════════════════════════════════"
      echo "  Go to: GitHub repo → Settings → Deploy keys → Add deploy key"
      echo "  Paste the key above and click Add"
      echo "═══════════════════════════════════════════════════════════════"
      echo ""
      read -p "Press Enter after adding the deploy key to GitHub..."
      # Add GitHub to known hosts
      ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts 2>/dev/null
    fi
  fi
  git clone "$REPO_URL" adhara_engine
  cd adhara_engine
fi

echo "── Repository ready ──"
'

info "Running provisioning script on VM..."
echo "$PROVISION_SCRIPT" | gcloud compute ssh "$VM_NAME" --zone="$VM_ZONE" --command="bash -s"
ok "VM provisioned"

# ── Step 9: Configure & Start Engine ────────────────────────────────

step 9 "Configuring and Starting Adhara Engine"

# Build the startup script
STARTUP_SCRIPT="#!/usr/bin/env bash
set -euo pipefail
cd ~/projects/adhara_engine

# Ensure docker group is active (newgrp doesn't work in non-interactive, so use sg)
# If docker works, great. If not, use sudo for this session.
if ! docker info &>/dev/null 2>&1; then
  echo 'Docker group not yet active — using sudo for this session.'
  echo 'Next SSH login will work without sudo.'
  DOCKER_CMD='sudo docker'
  COMPOSE_CMD='sudo docker compose'
else
  DOCKER_CMD='docker'
  COMPOSE_CMD='docker compose'
fi

# Generate .env if it doesn't exist
if [ ! -f .env ]; then
  echo '── Creating .env with secure random secrets ──'
  make .env
fi
"

# Set ADHARA_HOST
if [ -n "$DOMAIN" ]; then
  STARTUP_SCRIPT+="
# Set domain and ACME email
sed -i 's|^ADHARA_HOST=.*|ADHARA_HOST=${DOMAIN}|' .env 2>/dev/null || echo 'ADHARA_HOST=${DOMAIN}' >> .env
if ! grep -q '^ADHARA_DOMAIN=' .env; then
  echo 'ADHARA_DOMAIN=${DOMAIN}' >> .env
fi
if ! grep -q '^ACME_EMAIL=' .env; then
  echo 'ACME_EMAIL=${ACME_EMAIL}' >> .env
else
  sed -i 's|^ACME_EMAIL=.*|ACME_EMAIL=${ACME_EMAIL}|' .env
fi
"
else
  STARTUP_SCRIPT+="
# Set host to VM IP
sed -i 's|^ADHARA_HOST=.*|ADHARA_HOST=${VM_IP}|' .env 2>/dev/null || true
"
fi

# Build the make command with profiles
STARTUP_SCRIPT+="
echo '── Starting Adhara Engine (${PROFILE_DESC}) ──'
make ${MAKE_TARGET}
"

# Add optional profiles
EXTRA_PROFILES=""
if [ "$ENABLE_REGISTRY" = true ]; then
  EXTRA_PROFILES+=" --profile registry"
fi
if [ "$ENABLE_OBS" = true ]; then
  EXTRA_PROFILES+=" --profile observability"
fi
if [ "$ENABLE_STORAGE" = true ]; then
  EXTRA_PROFILES+=" --profile storage"
fi

if [ -n "$EXTRA_PROFILES" ]; then
  STARTUP_SCRIPT+="
echo '── Starting optional services ──'
\$COMPOSE_CMD ${EXTRA_PROFILES} up -d
"
fi

# Generate API token
STARTUP_SCRIPT+='
echo "── Creating API token ──"
make token

echo ""
echo "══════════════════════════════════════════════════════════════════"
echo "  Adhara Engine is running!"
echo "══════════════════════════════════════════════════════════════════"
echo ""
'

if [ -n "$DOMAIN" ]; then
  STARTUP_SCRIPT+="
echo \"  Dashboard: https://${DOMAIN}\"
echo \"  API:       https://${DOMAIN}/api\"
"
else
  STARTUP_SCRIPT+="
echo \"  Dashboard: http://${VM_IP}\"
echo \"  API:       http://${VM_IP}/api\"
"
fi

if [ "$AUTH_MODE" = "logto" ]; then
  STARTUP_SCRIPT+='
echo "  Logto Admin: http://localhost:3002 (SSH tunnel required)"
echo ""
echo "  Next: Open Logto Admin, create an application, and set"
echo "  VITE_OIDC_CLIENT_ID in ui/.env, then run:"
echo "    docker compose up -d --build ui"
'
elif [ "$AUTH_MODE" = "zitadel" ]; then
  STARTUP_SCRIPT+="
echo \"  Zitadel:   http://${VM_IP}/ui/console/\"
echo \"\"
echo \"  Next: Run 'bash scripts/setup-zitadel.sh' to configure OIDC.\"
echo \"  First boot takes 3-5 minutes — check with: docker compose logs zitadel --tail 10\"
"
fi

STARTUP_SCRIPT+='
echo ""
echo "  Log in with the API token printed above."
echo ""
echo "══════════════════════════════════════════════════════════════════"
'

info "Starting Adhara Engine on the VM..."
echo "$STARTUP_SCRIPT" | gcloud compute ssh "$VM_NAME" --zone="$VM_ZONE" --command="bash -s"

# ── Done ─────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}${GREEN}══════════════════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}${GREEN}  Deployment Complete!${RESET}"
echo -e "${BOLD}${GREEN}══════════════════════════════════════════════════════════════════${RESET}"
echo ""
echo -e "  ${BOLD}VM:${RESET}          ${VM_NAME} (${VM_ZONE})"
echo -e "  ${BOLD}IP:${RESET}          ${VM_IP}"
if [ -n "$DOMAIN" ]; then
  echo -e "  ${BOLD}Dashboard:${RESET}   https://${DOMAIN}"
else
  echo -e "  ${BOLD}Dashboard:${RESET}   http://${VM_IP}"
fi
echo -e "  ${BOLD}Auth:${RESET}        ${AUTH_MODE}"
echo -e "  ${BOLD}SSH:${RESET}         gcloud compute ssh ${VM_NAME} --zone=${VM_ZONE}"
echo ""
echo -e "  ${DIM}To access admin services (Grafana, etc.) via SSH tunnel:${RESET}"
echo -e "  ${DIM}gcloud compute ssh ${VM_NAME} --zone=${VM_ZONE} -- -L 3003:localhost:3003 -L 9001:localhost:9001${RESET}"
echo ""
