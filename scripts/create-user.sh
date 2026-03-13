#!/usr/bin/env bash
set -euo pipefail

# ── Adhara Engine — Create Zitadel User ───────────────────────────────
# Interactive wizard to create admin or normal users in Zitadel.
#
# Usage:
#   Interactive:  bash scripts/create-user.sh
#   Batch:        bash scripts/create-user.sh --email user@example.com \
#                   --first John --last Doe --password 'SecurePass1!' --role admin
#
# Requires a Personal Access Token (PAT) from Zitadel.
# Set ZITADEL_PAT env var or the script will prompt for it.

# Source .env if it exists, so ADHARA_HOST is available
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"
if [ -f "$ENV_FILE" ]; then
  set -a; source "$ENV_FILE"; set +a
fi

ADHARA_HOST="${ADHARA_HOST:-localhost}"
# Zitadel API is routed through Traefik on port 80
ZITADEL_URL="${ZITADEL_URL:-http://${ADHARA_HOST}}"

# ── Colors ────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ── Helpers ───────────────────────────────────────────────────────────
info()  { echo -e "  ${BLUE}ℹ${NC}  $1"; }
ok()    { echo -e "  ${GREEN}✅${NC} $1"; }
warn()  { echo -e "  ${YELLOW}⚠${NC}  $1"; }
fail()  { echo -e "  ${RED}❌${NC} $1"; exit 1; }

# ── Parse CLI args (batch mode) ──────────────────────────────────────
ARG_EMAIL=""
ARG_FIRST=""
ARG_LAST=""
ARG_PASSWORD=""
ARG_ROLE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --email)    ARG_EMAIL="$2";    shift 2 ;;
    --first)    ARG_FIRST="$2";    shift 2 ;;
    --last)     ARG_LAST="$2";     shift 2 ;;
    --password) ARG_PASSWORD="$2"; shift 2 ;;
    --role)     ARG_ROLE="$2";     shift 2 ;;
    --help|-h)
      echo ""
      echo "Usage: bash scripts/create-user.sh [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --email       User email address"
      echo "  --first       First name"
      echo "  --last        Last name"
      echo "  --password    Initial password (min 8 chars, uppercase, number, special)"
      echo "  --role        Role: admin or user (default: user)"
      echo ""
      echo "Environment:"
      echo "  ZITADEL_URL   Zitadel URL (default: http://localhost)"
      echo "  ZITADEL_PAT   Personal Access Token for Zitadel admin"
      echo ""
      echo "If any option is omitted, the script will prompt interactively."
      echo ""
      exit 0
      ;;
    *) fail "Unknown option: $1. Use --help for usage." ;;
  esac
done

# ── Header ────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}══════════════════════════════════════════════════════════════════${NC}"
echo -e "  ${CYAN}Adhara Engine${NC} — Create User"
echo -e "${BOLD}══════════════════════════════════════════════════════════════════${NC}"
echo ""

# ── Step 0: Wait for Zitadel ─────────────────────────────────────────
echo -e "  ${DIM}Checking Zitadel at ${ZITADEL_URL}...${NC}"
for i in $(seq 1 30); do
  if curl -sf "${ZITADEL_URL}/debug/healthz" > /dev/null 2>&1; then
    ok "Zitadel is healthy"
    break
  fi
  if [ "$i" -eq 30 ]; then
    fail "Zitadel not reachable at ${ZITADEL_URL}. Is Docker Compose running?"
  fi
  sleep 2
done

# ── Step 1: Get PAT ──────────────────────────────────────────────────
echo ""
if [ -z "${ZITADEL_PAT:-}" ]; then
  echo -e "  ${BOLD}Authentication${NC}"
  echo -e "  ${DIM}A Personal Access Token (PAT) is required to create users.${NC}"
  echo ""
  echo -e "  ${DIM}To create a PAT:${NC}"
  echo -e "  ${DIM}  1. Open ${ZITADEL_URL}/ui/console/${NC}"
  echo -e "  ${DIM}  2. Go to Users → Service Users tab${NC}"
  echo -e "  ${DIM}  3. Click \"+ New\" to create a service user:${NC}"
  echo -e "  ${DIM}       User Name:    adhara-admin${NC}"
  echo -e "  ${DIM}       Name:         Adhara Admin Service${NC}"
  echo -e "  ${DIM}       Access Type:  Bearer${NC}"
  echo -e "  ${DIM}  4. Click the new user → Personal Access Tokens${NC}"
  echo -e "  ${DIM}       Click \"+ New\" → Copy the token${NC}"
  echo -e "  ${DIM}  5. Grant admin permissions (from the Organization page):${NC}"
  echo -e "  ${DIM}       Go to Organization (top nav bar)${NC}"
  echo -e "  ${DIM}       Scroll to the Administrators/Members section${NC}"
  echo -e "  ${DIM}       Click \"+\" → search for \"adhara-admin\"${NC}"
  echo -e "  ${DIM}       Select ORG_OWNER role → Save${NC}"
  echo ""
  read -rp "  Paste your PAT: " ZITADEL_PAT
  echo ""
  echo ""
fi

if [ -z "$ZITADEL_PAT" ]; then
  fail "No PAT provided."
fi

# Verify PAT works
HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer ${ZITADEL_PAT}" \
  "${ZITADEL_URL}/auth/v1/users/me" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" != "200" ]; then
  fail "PAT authentication failed (HTTP ${HTTP_CODE}). Check your token."
fi
ok "Authenticated with Zitadel"

# ── Step 2: Collect user info ─────────────────────────────────────────
echo ""
echo -e "  ${BOLD}User Details${NC}"
echo ""

# Email
if [ -n "$ARG_EMAIL" ]; then
  USER_EMAIL="$ARG_EMAIL"
else
  read -rp "  Email: " USER_EMAIL
fi
if [ -z "$USER_EMAIL" ]; then
  fail "Email is required."
fi
# Basic email validation
if [[ ! "$USER_EMAIL" =~ ^[^@]+@[^@]+\.[^@]+$ ]]; then
  fail "Invalid email format: ${USER_EMAIL}"
fi

# First name
if [ -n "$ARG_FIRST" ]; then
  USER_FIRST="$ARG_FIRST"
else
  read -rp "  First name: " USER_FIRST
fi
if [ -z "$USER_FIRST" ]; then
  fail "First name is required."
fi

# Last name
if [ -n "$ARG_LAST" ]; then
  USER_LAST="$ARG_LAST"
else
  read -rp "  Last name: " USER_LAST
fi
if [ -z "$USER_LAST" ]; then
  fail "Last name is required."
fi

# Password
if [ -n "$ARG_PASSWORD" ]; then
  USER_PASSWORD="$ARG_PASSWORD"
else
  echo ""
  echo -e "  ${DIM}Password requirements: min 8 chars, 1 uppercase, 1 number, 1 special char${NC}"
  while true; do
    read -rsp "  Password: " USER_PASSWORD
    echo ""
    read -rsp "  Confirm password: " USER_PASSWORD_CONFIRM
    echo ""
    if [ "$USER_PASSWORD" = "$USER_PASSWORD_CONFIRM" ]; then
      break
    fi
    warn "Passwords don't match. Try again."
  done
fi
if [ ${#USER_PASSWORD} -lt 8 ]; then
  fail "Password must be at least 8 characters."
fi

# Role
echo ""
echo -e "  ${BOLD}Role${NC}"
if [ -n "$ARG_ROLE" ]; then
  USER_ROLE="$ARG_ROLE"
else
  echo -e "  ${DIM}1) admin  — Full access to all engine operations${NC}"
  echo -e "  ${DIM}2) user   — Standard access${NC}"
  echo ""
  read -rp "  Select role [1/2] (default: 2): " ROLE_CHOICE
  case "${ROLE_CHOICE:-2}" in
    1|admin)  USER_ROLE="admin" ;;
    2|user|*) USER_ROLE="user" ;;
  esac
fi

# Normalize
case "$USER_ROLE" in
  admin|Admin|ADMIN) USER_ROLE="admin" ;;
  *)                 USER_ROLE="user" ;;
esac

# ── Confirm ───────────────────────────────────────────────────────────
echo ""
echo -e "  ${BOLD}Summary${NC}"
echo -e "  ────────────────────────────────"
echo -e "  Name:     ${USER_FIRST} ${USER_LAST}"
echo -e "  Email:    ${USER_EMAIL}"
echo -e "  Role:     ${USER_ROLE}"
echo -e "  ────────────────────────────────"
echo ""

# Only prompt for confirmation in interactive mode
if [ -z "$ARG_EMAIL" ]; then
  read -rp "  Create this user? [Y/n] " CONFIRM
  if [[ "${CONFIRM:-Y}" =~ ^[Nn] ]]; then
    echo ""
    info "Cancelled."
    exit 0
  fi
fi

# ── Step 3: Create user via Zitadel v2 API ───────────────────────────
echo ""
echo -e "  ${DIM}Creating user...${NC}"

# Build JSON payload — using a heredoc to handle special chars in password
USER_JSON=$(cat <<EOF
{
  "userName": "${USER_EMAIL}",
  "profile": {
    "givenName": "${USER_FIRST}",
    "familyName": "${USER_LAST}",
    "displayName": "${USER_FIRST} ${USER_LAST}"
  },
  "email": {
    "email": "${USER_EMAIL}",
    "isVerified": true
  },
  "password": {
    "password": $(printf '%s' "$USER_PASSWORD" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
    "changeRequired": false
  }
}
EOF
)

RESPONSE=$(curl -sf -w "\n%{http_code}" \
  -X POST \
  -H "Authorization: Bearer ${ZITADEL_PAT}" \
  -H "Content-Type: application/json" \
  -d "$USER_JSON" \
  "${ZITADEL_URL}/v2/users/human" 2>&1) || true

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" != "200" ] && [ "$HTTP_CODE" != "201" ]; then
  echo ""
  ERROR_MSG=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('message', d.get('msg', str(d))))" 2>/dev/null || echo "$BODY")
  fail "Failed to create user (HTTP ${HTTP_CODE}): ${ERROR_MSG}"
fi

USER_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['userId'])" 2>/dev/null || echo "")

if [ -z "$USER_ID" ]; then
  fail "User created but could not parse user ID from response."
fi

ok "User created: ${USER_FIRST} ${USER_LAST} (${USER_ID})"

# ── Step 4: Get project ID and assign role ────────────────────────────
echo -e "  ${DIM}Looking up Adhara Engine project...${NC}"

PROJECTS_RESPONSE=$(curl -sf \
  -X POST \
  -H "Authorization: Bearer ${ZITADEL_PAT}" \
  -H "Content-Type: application/json" \
  -d '{"queries":[{"nameQuery":{"name":"Adhara Engine","method":"TEXT_QUERY_METHOD_EQUALS"}}]}' \
  "${ZITADEL_URL}/management/v1/projects/_search" 2>&1) || true

PROJECT_ID=$(echo "$PROJECTS_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
projects = data.get('result', [])
if projects:
    print(projects[0]['id'])
else:
    print('')
" 2>/dev/null || echo "")

if [ -z "$PROJECT_ID" ]; then
  warn "Could not find 'Adhara Engine' project. Role not assigned."
  warn "Create the project first (bash scripts/setup-zitadel.sh) then assign roles manually."
else
  # Assign role grant
  ROLE_KEYS='["'"$USER_ROLE"'"]'

  GRANT_RESPONSE=$(curl -sf -w "\n%{http_code}" \
    -X POST \
    -H "Authorization: Bearer ${ZITADEL_PAT}" \
    -H "Content-Type: application/json" \
    -d "{\"projectId\": \"${PROJECT_ID}\", \"userId\": \"${USER_ID}\", \"roleKeys\": ${ROLE_KEYS}}" \
    "${ZITADEL_URL}/management/v1/users/${USER_ID}/grants" 2>&1) || true

  GRANT_HTTP=$(echo "$GRANT_RESPONSE" | tail -1)

  if [ "$GRANT_HTTP" = "200" ] || [ "$GRANT_HTTP" = "201" ]; then
    ok "Role '${USER_ROLE}' assigned via project grant"
  else
    GRANT_BODY=$(echo "$GRANT_RESPONSE" | sed '$d')
    GRANT_ERR=$(echo "$GRANT_BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('message', str(d)))" 2>/dev/null || echo "$GRANT_BODY")
    warn "Could not assign role (HTTP ${GRANT_HTTP}): ${GRANT_ERR}"
    warn "You can assign the role manually in the Zitadel console."
  fi
fi

# ── Done ──────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}══════════════════════════════════════════════════════════════════${NC}"
echo ""
ok "User ${BOLD}${USER_FIRST} ${USER_LAST}${NC} ${GREEN}created successfully!${NC}"
echo ""
echo -e "  Email:    ${USER_EMAIL}"
echo -e "  Role:     ${USER_ROLE}"
echo -e "  User ID:  ${USER_ID}"
echo ""
echo -e "  ${DIM}They can now sign in at the Adhara Engine dashboard.${NC}"
echo ""
