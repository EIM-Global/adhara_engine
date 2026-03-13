#!/usr/bin/env bash
set -euo pipefail

# ── Adhara Engine — Zitadel OIDC Setup ────────────────────────────────
# This script waits for Zitadel to be healthy, then walks you through
# creating an OIDC application for the Adhara Engine SPA.

# Source .env if it exists, so ADHARA_HOST is available
ENV_FILE="$(dirname "$0")/../.env"
if [ -f "$ENV_FILE" ]; then
  set -a; source "$ENV_FILE"; set +a
fi

ADHARA_HOST="${ADHARA_HOST:-localhost}"
# Zitadel is routed through Traefik on port 80 (no separate port needed)
ZITADEL_URL="${ZITADEL_URL:-http://${ADHARA_HOST}}"
# Health check always uses localhost (script runs on the server)
ZITADEL_HEALTH_URL="http://localhost:8081"
UI_URL="http://${ADHARA_HOST}"

echo ""
echo "══════════════════════════════════════════════════════════════════"
echo "  Adhara Engine — Zitadel OIDC Setup"
echo "══════════════════════════════════════════════════════════════════"
echo ""

# ── Step 0: Wait for Zitadel ──────────────────────────────────────────
echo "⏳ Waiting for Zitadel to be healthy..."
echo "   (checking ${ZITADEL_HEALTH_URL}/debug/healthz)"
echo "   First boot can take 3-5 minutes while Zitadel initializes."
echo ""
MAX_WAIT=180  # 180 iterations x 2 seconds = 6 minutes
for i in $(seq 1 $MAX_WAIT); do
  if curl -sf "${ZITADEL_HEALTH_URL}/debug/healthz" > /dev/null 2>&1; then
    echo "✅ Zitadel is healthy!"
    break
  fi
  if [ "$i" -eq "$MAX_WAIT" ]; then
    echo "❌ Zitadel did not become healthy after $((MAX_WAIT * 2)) seconds."
    echo ""
    echo "   Troubleshooting:"
    echo "     1. Check Zitadel logs: docker compose logs zitadel --tail 30"
    echo "     2. Make sure all services are running: docker compose ps"
    echo "     3. Verify port 8081 is accessible: curl -sf http://localhost:8081/debug/healthz"
    exit 1
  fi
  # Show progress every 30 seconds
  if [ $((i % 15)) -eq 0 ]; then
    echo "   ⏳ Still waiting... ($((i * 2))s elapsed)"
  fi
  sleep 2
done

echo ""
echo "──────────────────────────────────────────────────────────────────"
echo "  Step 1: Open the Zitadel Console"
echo "──────────────────────────────────────────────────────────────────"
echo ""
echo "  Open this URL in your browser:"
echo "    ${ZITADEL_URL}/ui/console/"
echo ""
echo "  Log in with the default admin credentials:"
echo "    Email:    zitadel-admin@zitadel.${ADHARA_HOST}"
echo "    Password: Password1!"
echo ""
echo "  ℹ️  Zitadel runs through Traefik on port 80 — no extra ports needed."
echo ""

echo "──────────────────────────────────────────────────────────────────"
echo "  Step 2: Create a New Application"
echo "──────────────────────────────────────────────────────────────────"
echo ""
echo "  1. Click \"+ New\" in the top-right corner"
echo "  2. You'll see \"Select your project first\""
echo "     Project Name: Adhara Engine"
echo "     (Type the name — it will create a new project automatically)"
echo ""

echo "──────────────────────────────────────────────────────────────────"
echo "  Step 3: Select Framework"
echo "──────────────────────────────────────────────────────────────────"
echo ""
echo "  You'll see a \"Select Framework\" dropdown with options like"
echo "  PHP, Java, Go, Ruby, Python, etc."
echo ""
echo "  Select: \"Other (OIDC, SAML, API)\""
echo ""
echo "  (There's no React/SPA option listed, so \"Other\" lets us"
echo "   manually configure the OIDC settings we need.)"
echo ""
echo "  App Name: Adhara Dashboard"
echo ""
echo "  Click \"Continue\""
echo ""

echo "──────────────────────────────────────────────────────────────────"
echo "  Step 4: Select Application Type"
echo "──────────────────────────────────────────────────────────────────"
echo ""
echo "  Select: \"User Agent\""
echo ""
echo "  This is the correct type for Single Page Applications (SPAs)"
echo "  like our React dashboard that run entirely in the browser."
echo ""
echo "  DO NOT select Web, Native, or API."
echo ""
echo "  Click \"Continue\""
echo ""

echo "──────────────────────────────────────────────────────────────────"
echo "  Step 5: Authentication Method"
echo "──────────────────────────────────────────────────────────────────"
echo ""
echo "  Select: \"PKCE\""
echo ""
echo "  Click \"Continue\""
echo ""

echo "──────────────────────────────────────────────────────────────────"
echo "  Step 6: Set Redirect URIs"
echo "──────────────────────────────────────────────────────────────────"
echo ""
echo "  Add these Redirect URIs:"
echo "    ${UI_URL}/auth/callback"
if [ "$ADHARA_HOST" != "localhost" ]; then
  echo "    http://localhost/auth/callback  (for local dev)"
fi
echo ""
echo "  Add these Post-Logout Redirect URIs:"
echo "    ${UI_URL}"
if [ "$ADHARA_HOST" != "localhost" ]; then
  echo "    http://localhost  (for local dev)"
fi
echo ""
echo "  ⚠️  You may see a warning about http:// not being allowed."
echo "     That's OK — we'll fix it in the next step with Dev Mode."
echo ""
echo "  Click \"Create\""
echo ""

echo "──────────────────────────────────────────────────────────────────"
echo "  Step 7: Enable Development Mode  ⚠️  CRITICAL"
echo "──────────────────────────────────────────────────────────────────"
echo ""
echo "  After creating the app, you'll land on its configuration page."
echo "  You'll see an orange OIDC COMPLIANCE warning about http redirects."
echo ""
echo "  To fix this:"
echo ""
echo "  1. Scroll down to \"Redirect Settings\" in the left sidebar"
echo "  2. Toggle ON the \"Development Mode\" switch"
echo "  3. Click \"Save\""
echo ""
echo "  Development Mode allows http:// redirect URIs for localhost."
echo "  This is required because we're running locally without HTTPS."
echo "  The OIDC compliance warning should disappear after saving."
echo ""

echo "──────────────────────────────────────────────────────────────────"
echo "  Step 8: Copy the Client ID"
echo "──────────────────────────────────────────────────────────────────"
echo ""
echo "  On the app configuration page, find the Client ID."
echo "  It's displayed at the top-right and in the OIDC Configuration"
echo "  section (looks like: 362203209604898312)"
echo ""
echo "  ⚠️  There is NO client secret — that's expected for PKCE apps."
echo ""
echo "──────────────────────────────────────────────────────────────────"
echo ""

read -rp "  Paste your Client ID here: " CLIENT_ID

if [ -z "$CLIENT_ID" ]; then
  echo "❌ No Client ID provided. Aborting."
  exit 1
fi

# Write to root .env
ENV_FILE="$(dirname "$0")/../.env"
if [ -f "$ENV_FILE" ]; then
  if grep -q "^ZITADEL_CLIENT_ID=" "$ENV_FILE"; then
    sed -i "s/^ZITADEL_CLIENT_ID=.*/ZITADEL_CLIENT_ID=${CLIENT_ID}/" "$ENV_FILE"
  else
    echo "" >> "$ENV_FILE"
    echo "ZITADEL_CLIENT_ID=${CLIENT_ID}" >> "$ENV_FILE"
  fi
else
  echo "ZITADEL_CLIENT_ID=${CLIENT_ID}" > "$ENV_FILE"
fi

# Write ADHARA_HOST to root .env if not already present
if [ "$ADHARA_HOST" != "localhost" ]; then
  if ! grep -q "^ADHARA_HOST=" "$ENV_FILE" 2>/dev/null; then
    echo "ADHARA_HOST=${ADHARA_HOST}" >> "$ENV_FILE"
  fi
fi

# Write to ui/.env
UI_ENV_FILE="$(dirname "$0")/../ui/.env"
mkdir -p "$(dirname "$UI_ENV_FILE")"
cat > "$UI_ENV_FILE" <<EOF
VITE_ZITADEL_ISSUER=${ZITADEL_URL}
VITE_ZITADEL_CLIENT_ID=${CLIENT_ID}
EOF

echo ""
echo "══════════════════════════════════════════════════════════════════"
echo "  ✅ Configuration saved!"
echo "══════════════════════════════════════════════════════════════════"
echo ""
echo "  .env:    ZITADEL_CLIENT_ID=${CLIENT_ID}"
echo "  ui/.env: VITE_ZITADEL_ISSUER=${ZITADEL_URL}"
echo "           VITE_ZITADEL_CLIENT_ID=${CLIENT_ID}"
echo ""
echo "  Next step — rebuild the UI to bake in the new config:"
echo "    docker compose up -d --build ui"
echo ""
echo "  (A simple 'restart' won't work — Vite bakes VITE_* env vars"
echo "   into the JS bundle at build time, so a rebuild is required.)"
echo ""
echo "  Then open: ${UI_URL}"
echo ""
