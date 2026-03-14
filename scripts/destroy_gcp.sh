#!/usr/bin/env bash
set -euo pipefail

# ── Adhara Engine — GCP Teardown ─────────────────────────────────────
# Destroys all GCP resources created by deploy_gcp.sh.
# Requires DOUBLE CONFIRMATION before any destructive action.
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Same GCP project used during deployment
#
# Usage:
#   bash scripts/destroy_gcp.sh
#   bash scripts/destroy_gcp.sh --vm-name adhara-engine --zone us-central1-a

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

# ── Parse CLI args (optional) ────────────────────────────────────────

VM_NAME=""
VM_ZONE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --vm-name) VM_NAME="$2"; shift 2 ;;
    --zone)    VM_ZONE="$2"; shift 2 ;;
    *)         err "Unknown arg: $1"; exit 1 ;;
  esac
done

# ── Banner ───────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}${RED}══════════════════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}${RED}  Adhara Engine — GCP Teardown (DESTRUCTIVE)${RESET}"
echo -e "${BOLD}${RED}══════════════════════════════════════════════════════════════════${RESET}"
echo ""

# ── Preflight ────────────────────────────────────────────────────────

if ! command -v gcloud &>/dev/null; then
  err "gcloud CLI not found."
  exit 1
fi

GCP_PROJECT=$(gcloud config get-value project 2>/dev/null || true)
if [ -z "$GCP_PROJECT" ] || [ "$GCP_PROJECT" = "(unset)" ]; then
  err "No GCP project set. Run: gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi
info "GCP project: ${GCP_PROJECT}"

# ── Identify resources ───────────────────────────────────────────────

if [ -z "$VM_NAME" ]; then
  echo -en "${BOLD}VM name to destroy${RESET} ${DIM}[adhara-engine]${RESET}: "
  read -r VM_NAME
  VM_NAME="${VM_NAME:-adhara-engine}"
fi

if [ -z "$VM_ZONE" ]; then
  # Try to auto-detect zone
  DETECTED_ZONE=$(gcloud compute instances list \
    --filter="name=${VM_NAME}" \
    --format="value(zone)" 2>/dev/null | head -1)

  if [ -n "$DETECTED_ZONE" ]; then
    info "Auto-detected zone: ${DETECTED_ZONE}"
    VM_ZONE="$DETECTED_ZONE"
  else
    echo -en "${BOLD}Zone${RESET} ${DIM}[us-central1-a]${RESET}: "
    read -r VM_ZONE
    VM_ZONE="${VM_ZONE:-us-central1-a}"
  fi
fi

# ── Discover what exists ─────────────────────────────────────────────

echo ""
info "Scanning for resources to destroy..."
echo ""

VM_EXISTS=false
if gcloud compute instances describe "$VM_NAME" --zone="$VM_ZONE" &>/dev/null 2>&1; then
  VM_IP=$(gcloud compute instances describe "$VM_NAME" \
    --zone="$VM_ZONE" \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)' 2>/dev/null || echo "unknown")
  VM_TYPE=$(gcloud compute instances describe "$VM_NAME" \
    --zone="$VM_ZONE" \
    --format='get(machineType)' 2>/dev/null | awk -F/ '{print $NF}')
  VM_EXISTS=true
fi

FW_HTTP=false
FW_HTTPS=false
if gcloud compute firewall-rules describe adhara-allow-http &>/dev/null 2>&1; then
  FW_HTTP=true
fi
if gcloud compute firewall-rules describe adhara-allow-https &>/dev/null 2>&1; then
  FW_HTTPS=true
fi

# ── Show what will be destroyed ──────────────────────────────────────

echo -e "${BOLD}${RED}The following resources will be PERMANENTLY DELETED:${RESET}"
echo ""

if [ "$VM_EXISTS" = true ]; then
  echo -e "  ${RED}▸${RESET} VM instance:    ${BOLD}${VM_NAME}${RESET} (${VM_TYPE}, ${VM_ZONE})"
  echo -e "  ${RED}▸${RESET} External IP:    ${VM_IP}"
  echo -e "  ${RED}▸${RESET} Boot disk:      ${VM_NAME} (all data on this disk will be lost)"
else
  echo -e "  ${DIM}  VM '${VM_NAME}' not found in ${VM_ZONE} — skipping${RESET}"
fi

if [ "$FW_HTTP" = true ]; then
  echo -e "  ${RED}▸${RESET} Firewall rule:  adhara-allow-http (tcp:80)"
fi
if [ "$FW_HTTPS" = true ]; then
  echo -e "  ${RED}▸${RESET} Firewall rule:  adhara-allow-https (tcp:443)"
fi

if [ "$VM_EXISTS" = false ] && [ "$FW_HTTP" = false ] && [ "$FW_HTTPS" = false ]; then
  echo -e "  ${DIM}No Adhara Engine resources found. Nothing to destroy.${RESET}"
  echo ""
  exit 0
fi

echo ""
warn "This action is IRREVERSIBLE. All data on the VM will be permanently lost."
warn "This includes databases, deployed sites, uploaded images, and configuration."
echo ""

# ── Confirmation 1 ───────────────────────────────────────────────────

echo -en "${BOLD}${RED}Are you sure you want to destroy these resources? (yes/no)${RESET}: "
read -r CONFIRM1

if [ "$CONFIRM1" != "yes" ]; then
  echo ""
  info "Aborted. No resources were deleted."
  exit 0
fi

# ── Confirmation 2 ───────────────────────────────────────────────────

echo ""
echo -e "${BOLD}${RED}FINAL CONFIRMATION — type the VM name to confirm: ${VM_NAME}${RESET}"
echo -en "${BOLD}${RED}VM name${RESET}: "
read -r CONFIRM2

if [ "$CONFIRM2" != "$VM_NAME" ]; then
  echo ""
  err "Name did not match. Aborted. No resources were deleted."
  exit 1
fi

echo ""

# ── Destroy VM ───────────────────────────────────────────────────────

if [ "$VM_EXISTS" = true ]; then
  info "Deleting VM: ${VM_NAME} (${VM_ZONE})..."
  gcloud compute instances delete "$VM_NAME" \
    --zone="$VM_ZONE" \
    --delete-disks=all \
    --quiet
  ok "VM deleted: ${VM_NAME}"
fi

# ── Destroy firewall rules ──────────────────────────────────────────

if [ "$FW_HTTP" = true ]; then
  info "Deleting firewall rule: adhara-allow-http..."
  gcloud compute firewall-rules delete adhara-allow-http --quiet
  ok "Firewall rule deleted: adhara-allow-http"
fi

if [ "$FW_HTTPS" = true ]; then
  info "Deleting firewall rule: adhara-allow-https..."
  gcloud compute firewall-rules delete adhara-allow-https --quiet
  ok "Firewall rule deleted: adhara-allow-https"
fi

# ── Done ─────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}${GREEN}══════════════════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}${GREEN}  Teardown Complete${RESET}"
echo -e "${BOLD}${GREEN}══════════════════════════════════════════════════════════════════${RESET}"
echo ""
echo -e "  ${DIM}Destroyed:${RESET}"
[ "$VM_EXISTS" = true ]  && echo "    - VM: ${VM_NAME} (${VM_ZONE})"
[ "$FW_HTTP" = true ]    && echo "    - Firewall: adhara-allow-http"
[ "$FW_HTTPS" = true ]   && echo "    - Firewall: adhara-allow-https"
echo ""
echo -e "  ${DIM}If you had DNS records pointing to ${VM_IP:-the VM}, remove them manually.${RESET}"
echo ""
