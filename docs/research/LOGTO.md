Lightweight OIDC Providers — Ranked for Adhara Engine                                                                                                                 
                                                                                                                                                                        
  The Short Answer                                                                                                                                                      
                                                                                                                                                                        
  Logto is the best fit. Single container, ~100-200MB RAM, full OIDC+PKCE, built-in login UI, REST user management API, reuses your existing Postgres. US-based company,
   11.7K stars, English-first docs.                                                                                                                                     
                                                                          
  Full Comparison                                                         
                                                                          
  ┌──────────────────┬───────────┬────────────┬─────────┬──────────┬────────────┬──────────────────┬────────────────────────────────────┐
  │     Provider     │    RAM    │ Containers │  PKCE   │ Login UI │  User API  │      Origin      │              Verdict               │
  ├──────────────────┼───────────┼────────────┼─────────┼──────────┼────────────┼──────────────────┼────────────────────────────────────┤
  │ Logto            │ 100-200MB │ 1          │ Yes     │ Yes      │ Yes (REST) │ USA              │ Best fit                           │
  ├──────────────────┼───────────┼────────────┼─────────┼──────────┼────────────┼──────────────────┼────────────────────────────────────┤
  │ Kanidm           │ 50-128MB  │ 1          │ Yes     │ Yes      │ CLI/HTTP   │ Australia (Rust) │ Lightest, but immature             │
  ├──────────────────┼───────────┼────────────┼─────────┼──────────┼────────────┼──────────────────┼────────────────────────────────────┤                               
  │ Authelia         │ 30MB      │ 1          │ Yes     │ Yes      │ No         │ Australia        │ No user API — disqualified         │                               
  ├──────────────────┼───────────┼────────────┼─────────┼──────────┼────────────┼──────────────────┼────────────────────────────────────┤                               
  │ Dex              │ 20-50MB   │ 1          │ Partial │ Minimal  │ No         │ USA (CNCF)       │ Not an IdP — disqualified          │                               
  ├──────────────────┼───────────┼────────────┼─────────┼──────────┼────────────┼──────────────────┼────────────────────────────────────┤                               
  │ Ory Hydra+Kratos │ ~500MB    │ 3-4        │ Yes     │ No       │ Yes        │ Germany          │ Too many containers, no login UI   │                               
  ├──────────────────┼───────────┼────────────┼─────────┼──────────┼────────────┼──────────────────┼────────────────────────────────────┤                               
  │ SuperTokens      │ 200-400MB │ 1+         │ Yes     │ Embedded │ Yes        │ USA/India        │ Embedded SDK model, not standalone │
  ├──────────────────┼───────────┼────────────┼─────────┼──────────┼────────────┼──────────────────┼────────────────────────────────────┤
  │ Keycloak         │ 750MB-2GB │ 1          │ Yes     │ Yes      │ Yes        │ USA (Red Hat)    │ Heavier than Zitadel               │
  ├──────────────────┼───────────┼────────────┼─────────┼──────────┼────────────┼──────────────────┼────────────────────────────────────┤
  │ Authentik        │ 2-4GB     │ 2-3        │ Yes     │ Yes      │ Yes        │ Germany          │ Heavier than Zitadel               │
  ├──────────────────┼───────────┼────────────┼─────────┼──────────┼────────────┼──────────────────┼────────────────────────────────────┤
  │ Zitadel Cloud    │ 0         │ 0          │ Yes     │ Yes      │ Yes        │ Switzerland      │ SaaS — free tier 100 DAU           │
  └──────────────────┴───────────┴────────────┴─────────┴──────────┴────────────┴──────────────────┴────────────────────────────────────┘

  Why Logto Wins

  ┌───────────────────────┬────────────────────────┬─────────────────────────────┬───────────────────────────────┐
  │       Attribute       │         Logto          │           Casdoor           │            Zitadel            │
  ├───────────────────────┼────────────────────────┼─────────────────────────────┼───────────────────────────────┤
  │ RAM                   │ ~100-200MB             │ ~100-150MB                  │ ~350-500MB                    │
  ├───────────────────────┼────────────────────────┼─────────────────────────────┼───────────────────────────────┤
  │ Containers            │ 1                      │ 1                           │ 2                             │
  ├───────────────────────┼────────────────────────┼─────────────────────────────┼───────────────────────────────┤
  │ Database              │ Reuses Postgres        │ Reuses Postgres             │ Own Postgres DB + event store │
  ├───────────────────────┼────────────────────────┼─────────────────────────────┼───────────────────────────────┤
  │ Login UI              │ Built-in, modern       │ Built-in                    │ Separate container            │
  ├───────────────────────┼────────────────────────┼─────────────────────────────┼───────────────────────────────┤
  │ User API              │ REST (well-documented) │ REST (Swagger)              │ gRPC + REST gateway           │
  ├───────────────────────┼────────────────────────┼─────────────────────────────┼───────────────────────────────┤
  │ First-boot            │ DB seed CLI + env vars │ init_data.json              │ Manual wizard + PAT bootstrap │
  ├───────────────────────┼────────────────────────┼─────────────────────────────┼───────────────────────────────┤
  │ OIDC compliance       │ OAuth 2.1 compliant    │ Standard OIDC               │ Fully certified               │
  ├───────────────────────┼────────────────────────┼─────────────────────────────┼───────────────────────────────┤
  │ Security track record │ Clean (young project)  │ Multiple CVEs 2024-2025     │ Strong (enterprise focus)     │
  ├───────────────────────┼────────────────────────┼─────────────────────────────┼───────────────────────────────┤
  │ Community             │ 11.7K stars, US-based  │ 10.5K stars, Chinese-origin │ 13K stars, Swiss              │
  ├───────────────────────┼────────────────────────┼─────────────────────────────┼───────────────────────────────┤
  │ License               │ MPL-2.0                │ Apache 2.0                  │ Apache 2.0                    │
  ├───────────────────────┼────────────────────────┼─────────────────────────────┼───────────────────────────────┤
  │ Admin console         │ Built-in (port 3002)   │ Built-in                    │ Separate container            │
  └───────────────────────┴────────────────────────┴─────────────────────────────┴───────────────────────────────┘

  Logto: What Integration Looks Like

  Docker Compose — single service addition:
  logto:
    image: svhd/logto:latest
    profiles: [auth-logto]
    environment:
      - DB_URL=postgresql://engine:${POSTGRES_PASSWORD:-engine}@db:5432/logto
      - ENDPOINT=http://${ADHARA_HOST:-localhost}:3001
      - ADMIN_ENDPOINT=http://${ADHARA_HOST:-localhost}:3002
      - TRUST_PROXY_HEADER=true
    depends_on:
      db:
        condition: service_healthy

  First boot: npx @logto/cli db seed (or runs automatically on first start)

  SPA integration: Your oidc-client-ts config just points to Logto's issuer URL — same as Zitadel or any OIDC provider. PKCE enforced by default for public clients.

  User provisioning: Simple REST — POST /api/users, PATCH /api/users/{id}, authenticated via M2M client credentials.

  Recommended Profile Matrix

  make init              → Core only (~500MB, token auth)
  make up-logto          → Core + Logto (~700MB, lightweight OIDC SSO)  ← NEW
  make up-auth           → Core + Zitadel (~1.3GB, enterprise OIDC SSO)
  make up-full           → Everything (~2GB)

  ---
  ━━━ 📚  L E A R N ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 7/7

  📋 SUMMARY: Logto is the strongest Casdoor alternative — same resource savings, US-based, clean security record, better documentation.
  📁 CAPTURE: Logto replaces both Casdoor and Zitadel as the lightweight auth option. Single container, reuses Postgres, full OIDC+PKCE, REST API.
  ➡️  NEXT: Want me to build the Logto integration? Same ~9 hour plan as Casdoor, but with Logto instead. Phase 1 (provider-agnostic refactor) is identical.