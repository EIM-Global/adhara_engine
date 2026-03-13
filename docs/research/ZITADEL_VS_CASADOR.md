Zitadel vs Casdoor — Comparison & Implementation Plan

  Resource Comparison

  ┌──────────────────┬──────────────────────────────────────────┬────────────────────────────────────┬─────────────────────┐
  │      Metric      │                 Zitadel                  │              Casdoor               │       Savings       │
  ├──────────────────┼──────────────────────────────────────────┼────────────────────────────────────┼─────────────────────┤
  │ Containers       │ 2 (zitadel + zitadel-login)              │ 1 (casdoor)                        │ -1 container        │
  ├──────────────────┼──────────────────────────────────────────┼────────────────────────────────────┼─────────────────────┤
  │ RAM              │ ~350-500MB combined                      │ ~100-150MB                         │ ~300MB freed        │
  ├──────────────────┼──────────────────────────────────────────┼────────────────────────────────────┼─────────────────────┤
  │ Image size       │ ~800MB (two images)                      │ ~100MB (one image)                 │ ~700MB disk         │
  ├──────────────────┼──────────────────────────────────────────┼────────────────────────────────────┼─────────────────────┤
  │ Database         │ Dedicated zitadel DB + event sourcing    │ Reuses existing Postgres           │ Simpler             │
  ├──────────────────┼──────────────────────────────────────────┼────────────────────────────────────┼─────────────────────┤
  │ First boot time  │ 3-5 minutes (schema init + event replay) │ 10-30 seconds                      │ Much faster         │
  ├──────────────────┼──────────────────────────────────────────┼────────────────────────────────────┼─────────────────────┤
  │ Setup automation │ Semi-manual wizard (setup-zitadel.sh)    │ Fully automated via init_data.json │ Zero-touch possible │
  └──────────────────┴──────────────────────────────────────────┴────────────────────────────────────┴─────────────────────┘

  Feature Comparison

  ┌────────────────────────┬──────────────────────────────────────────┬─────────────────────────────────────────┐
  │        Feature         │                 Zitadel                  │                 Casdoor                 │
  ├────────────────────────┼──────────────────────────────────────────┼─────────────────────────────────────────┤
  │ OIDC + PKCE            │ Full support                             │ Full support                            │
  ├────────────────────────┼──────────────────────────────────────────┼─────────────────────────────────────────┤
  │ Built-in login UI      │ Separate container (Next.js)             │ Built into main container               │
  ├────────────────────────┼──────────────────────────────────────────┼─────────────────────────────────────────┤
  │ User management API    │ gRPC + REST gateway                      │ Simple REST + Swagger                   │
  ├────────────────────────┼──────────────────────────────────────────┼─────────────────────────────────────────┤
  │ Multi-tenancy          │ Enterprise-grade org isolation           │ Basic org model                         │
  ├────────────────────────┼──────────────────────────────────────────┼─────────────────────────────────────────┤
  │ Event sourcing / audit │ Full CQRS event store                    │ Standard CRUD (no event log)            │
  ├────────────────────────┼──────────────────────────────────────────┼─────────────────────────────────────────┤
  │ Security maturity      │ Strong — Swiss company, enterprise focus │ Weaker — several CVEs in 2024-2025      │
  ├────────────────────────┼──────────────────────────────────────────┼─────────────────────────────────────────┤
  │ Community              │ ~13K stars, English-first                │ ~10.5K stars, Chinese-origin docs       │
  ├────────────────────────┼──────────────────────────────────────────┼─────────────────────────────────────────┤
  │ Social login providers │ 15+                                      │ 50+ (wider provider support)            │
  ├────────────────────────┼──────────────────────────────────────────┼─────────────────────────────────────────┤
  │ Subpath routing        │ Works with path-based Traefik rules      │ Needs subdomain or root path            │
  ├────────────────────────┼──────────────────────────────────────────┼─────────────────────────────────────────┤
  │ SDKs                   │ Go, gRPC clients                         │ Go, Python, Node, Java, PHP, .NET, Rust │
  └────────────────────────┴──────────────────────────────────────────┴─────────────────────────────────────────┘

  When to Use Which

  ┌───────────────────────────────────────────┬────────────────┐
  │                 Scenario                  │ Recommendation │
  ├───────────────────────────────────────────┼────────────────┤
  │ Small server, few users, cost-sensitive   │ Casdoor        │
  ├───────────────────────────────────────────┼────────────────┤
  │ Enterprise/compliance, audit trail needed │ Zitadel        │
  ├───────────────────────────────────────────┼────────────────┤
  │ Developer tool / internal platform        │ Casdoor        │
  ├───────────────────────────────────────────┼────────────────┤
  │ Customer-facing SaaS with sensitive data  │ Zitadel        │
  ├───────────────────────────────────────────┼────────────────┤
  │ Minimal ops, want zero-touch setup        │ Casdoor        │
  ├───────────────────────────────────────────┼────────────────┤
  │ Already running Zitadel and it works      │ Keep Zitadel   │
  └───────────────────────────────────────────┴────────────────┘

  What Changes Per Layer

  Here's the concrete work to add Casdoor as an auth-casdoor Docker Compose profile:

  1. Docker Compose (docker-compose.yml)

  Add: New casdoor service under auth-casdoor profile.

  casdoor:
    image: casbin/casdoor:latest
    profiles: [auth-casdoor]
    environment:
      - RUNNING_IN_DOCKER=true
      - driverName=postgres
      - dataSourceName=user=engine password=${POSTGRES_PASSWORD:-engine} host=db port=5432 sslmode=disable dbname=casdoor
      - origin=http://${ADHARA_HOST:-localhost}
    volumes:
      - ./casdoor/app.conf:/conf/app.conf:ro
      - ./casdoor/init_data.json:/init_data.json:ro
    depends_on:
      db:
        condition: service_healthy
    networks:
      - adhara-engine-net
    restart: unless-stopped

  Keep: Existing Zitadel services under auth profile (unchanged).

  Result: --profile auth = Zitadel, --profile auth-casdoor = Casdoor, no profile = token auth.

  2. Database Init (scripts/init-db.sql)

  Add: CREATE DATABASE casdoor OWNER engine; alongside the existing Zitadel DB init.

  No new user needed — reuse the engine Postgres user.

  3. Casdoor Config Files (new)

  Create: casdoor/app.conf — Casdoor configuration:
  - DB connection (Postgres, same db container)
  - origin = http://${ADHARA_HOST}
  - enableGzip = true
  - httpport = 8000 (internal)

  Create: casdoor/init_data.json — Pre-configured first-boot data:
  - Organization: adhara
  - Application: adhara-engine (SPA, PKCE, redirect URIs)
  - Default admin user
  - Roles: admin, user
  - Certificate for JWT signing

  This is the big win — no manual setup wizard needed. docker compose --profile auth-casdoor up -d and auth is ready.

  4. Traefik Routing (traefik/dynamic/services.yml)

  Current Zitadel routing uses 11 path prefixes (/oauth, /oidc, /.well-known, /ui/console, etc.).

  Casdoor routing would be simpler — Casdoor serves everything from one container:

  casdoor-web:
    rule: "PathPrefix(`/login/oauth`) || PathPrefix(`/api/login`) ||
          PathPrefix(`/.well-known`) || PathPrefix(`/casdoor`)"
    entryPoints: [web]
    service: casdoor
    priority: 200

  Challenge: Casdoor doesn't natively support subpath routing. Two options:
  - Option A (recommended): Route Casdoor paths on the same domain — its OAuth/API endpoints have distinct prefixes that won't conflict with the UI
  - Option B: Use a subdomain (auth.{ADHARA_HOST}) — cleanest but requires wildcard DNS

  5. API JWT Validation (api/app/core/auth.py)

  Current code fetches JWKS from http://zitadel:8080/oauth/v2/keys.

  Change needed: Make the JWKS endpoint configurable:

  ┌───────────────┬──────────────────────────────────────┬──────────────────────────────────────┐
  │ Auth Provider │               JWKS URI               │             Userinfo URI             │
  ├───────────────┼──────────────────────────────────────┼──────────────────────────────────────┤
  │ Zitadel       │ http://zitadel:8080/oauth/v2/keys    │ http://zitadel:8080/oidc/v1/userinfo │
  ├───────────────┼──────────────────────────────────────┼──────────────────────────────────────┤
  │ Casdoor       │ http://casdoor:8000/.well-known/jwks │ http://casdoor:8000/api/userinfo     │
  └───────────────┴──────────────────────────────────────┴──────────────────────────────────────┘

  This is a ~20-line change — read the provider from env var, adjust the URLs.

  Role mapping also differs:
  - Zitadel: urn:zitadel:iam:org:project:roles claim
  - Casdoor: Standard roles claim or custom claim via Casdoor config

  6. UI OIDC Config (ui/src/auth/config.ts)

  Already provider-agnostic. The OIDC config only needs:
  - authority (issuer URL) — set via VITE_ZITADEL_ISSUER (we'd rename to VITE_OIDC_ISSUER)
  - client_id — set via VITE_ZITADEL_CLIENT_ID (we'd rename to VITE_OIDC_CLIENT_ID)

  Scope change: Remove Zitadel-specific scopes (urn:zitadel:iam:org:projects:roles, urn:zitadel:iam:org:project:id:zitadel:aud) and use standard OIDC scopes (openid
  profile email).

  The oidc-client-ts library handles everything else — discovery, PKCE, token exchange. It doesn't care whether the provider is Zitadel or Casdoor.

  7. Setup Scripts

  ┌──────────────────────────────┬───────────────────────────┬─────────────────────────────────────────────────────────┐
  │            Script            │          Zitadel          │                         Casdoor                         │
  ├──────────────────────────────┼───────────────────────────┼─────────────────────────────────────────────────────────┤
  │ setup-zitadel.sh (380 lines) │ Keep as-is                │ Not needed — init_data.json handles it                  │
  ├──────────────────────────────┼───────────────────────────┼─────────────────────────────────────────────────────────┤
  │ create-user.sh (350 lines)   │ Keep for Zitadel          │ New create-user-casdoor.sh (~50 lines, simple REST API) │
  ├──────────────────────────────┼───────────────────────────┼─────────────────────────────────────────────────────────┤
  │ adhara-secure.sh             │ Keep Zitadel HTTPS routes │ Add Casdoor HTTPS route variant                         │
  └──────────────────────────────┴───────────────────────────┴─────────────────────────────────────────────────────────┘

  8. Environment Variables

  Rename for provider-agnosticism:

  ┌────────────────────────┬─────────────────────┬────────────────────────────────────────┐
  │        Current         │      Proposed       │                 Notes                  │
  ├────────────────────────┼─────────────────────┼────────────────────────────────────────┤
  │ VITE_ZITADEL_ISSUER    │ VITE_OIDC_ISSUER    │ Works for both providers               │
  ├────────────────────────┼─────────────────────┼────────────────────────────────────────┤
  │ VITE_ZITADEL_CLIENT_ID │ VITE_OIDC_CLIENT_ID │ Still the OIDC feature flag            │
  ├────────────────────────┼─────────────────────┼────────────────────────────────────────┤
  │ ZITADEL_DOMAIN         │ OIDC_INTERNAL_URL   │ Internal Docker URL for API validation │
  ├────────────────────────┼─────────────────────┼────────────────────────────────────────┤
  │ ZITADEL_ISSUER         │ OIDC_ISSUER         │ External issuer URL                    │
  └────────────────────────┴─────────────────────┴────────────────────────────────────────┘

  Keep ZITADEL_MASTERKEY, ZITADEL_DB_PASSWORD etc. only for the Zitadel profile.

  Implementation Phases

  ┌───────────────────────────────┬───────────────────────────────────────────────────────────────────────────────┬──────────┬──────────────────────────────────┐
  │             Phase             │                                     Work                                      │  Effort  │               Risk               │
  ├───────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┼──────────┼──────────────────────────────────┤
  │ 1. Provider-agnostic refactor │ Rename env vars, make JWKS/userinfo URLs configurable, genericize OIDC scopes │ ~2 hours │ Low — no behavior change         │
  ├───────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┼──────────┼──────────────────────────────────┤
  │ 2. Casdoor Docker setup       │ Add service to compose, create app.conf, create init_data.json, add DB init   │ ~2 hours │ Low                              │
  ├───────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┼──────────┼──────────────────────────────────┤
  │ 3. Traefik routing            │ Add Casdoor routes to services.yml and adhara-secure.sh                       │ ~1 hour  │ Medium — path conflicts possible │
  ├───────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┼──────────┼──────────────────────────────────┤
  │ 4. User management script     │ Write create-user-casdoor.sh using Casdoor REST API                           │ ~1 hour  │ Low                              │
  ├───────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┼──────────┼──────────────────────────────────┤
  │ 5. Makefile + README          │ Add make up-casdoor, update docs with provider choice                         │ ~1 hour  │ Low                              │
  ├───────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┼──────────┼──────────────────────────────────┤
  │ 6. Testing                    │ End-to-end: login, logout, token refresh, user creation                       │ ~2 hours │ Medium                           │
  └───────────────────────────────┴───────────────────────────────────────────────────────────────────────────────┴──────────┴──────────────────────────────────┘

  Total estimate: ~9 hours of implementation work.

  Recommended Approach

  1. Don't remove Zitadel — keep it as --profile auth for enterprise deployments
  2. Add Casdoor as --profile auth-casdoor for lightweight deployments
  3. Refactor to provider-agnostic env vars first (Phase 1) — this benefits both providers
  4. Ship init_data.json with sensible defaults so Casdoor is zero-config
  5. Make the choice clear in README: "Small server? Use make up-casdoor. Enterprise? Use make up-auth."

  Final Profile Matrix

  make init              → Core only (~500MB, token auth)
  make up-casdoor        → Core + Casdoor (~650MB, OIDC SSO)
  make up-auth           → Core + Zitadel (~1.3GB, enterprise OIDC SSO)
  make up-full           → Everything (~2GB)

  ---
  ━━━ 📚  L E A R N ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 7/7

  📋 SUMMARY: Complete analysis of Zitadel vs Casdoor with 6-phase implementation plan (~9 hours work) to add Casdoor as a lightweight auth alternative.
  📁 CAPTURE: Casdoor saves ~300MB RAM and eliminates the manual setup wizard via init_data.json. Main trade-off is weaker security maturity.
