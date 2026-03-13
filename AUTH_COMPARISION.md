  Auth Platform Comparison                                                                                                                                                       
                                                                                                                                                                                 
  ┌────────────────────────┬───────────────────────┬────────────────────────┬──────────────────────┬───────────────────────┐
  │        Criteria        │       Keycloak        │        Zitadel         │      Authentik       │         Logto         │                                                     
  ├────────────────────────┼───────────────────────┼────────────────────────┼──────────────────────┼───────────────────────┤                                                     
  │ Language               │ Java (JVM)            │ Go                     │ Python               │ TypeScript            │                                                     
  ├────────────────────────┼───────────────────────┼────────────────────────┼──────────────────────┼───────────────────────┤                                                     
  │ Docker RAM             │ ~700MB–2GB            │ ~150–200MB             │ ~375–735MB           │ ~150–300MB            │                                                     
  ├────────────────────────┼───────────────────────┼────────────────────────┼──────────────────────┼───────────────────────┤                                                     
  │ Passkeys/WebAuthn      │ ✅ GA since v26.4     │ ✅ Native              │ ✅ Since 2025.12     │ ✅ Native             │                                                     
  ├────────────────────────┼───────────────────────┼────────────────────────┼──────────────────────┼───────────────────────┤                                                     
  │ OAuth2 + Google        │ ✅                    │ ✅                     │ ✅                   │ ✅                    │                                                     
  ├────────────────────────┼───────────────────────┼────────────────────────┼──────────────────────┼───────────────────────┤                                                     
  │ Multi-tenant           │ ✅ Realms + Orgs      │ ✅ Built for it        │ ⚠️  Limited           │ ✅ Organizations      │                                                     
  ├────────────────────────┼───────────────────────┼────────────────────────┼──────────────────────┼───────────────────────┤                                                     
  │ RBAC                   │ ✅ Fine-grained       │ ✅ Org-level           │ ✅                   │ ✅                    │                                                     
  ├────────────────────────┼───────────────────────┼────────────────────────┼──────────────────────┼───────────────────────┤                                                     
  │ Service Accounts (M2M) │ ✅ Client Credentials │ ✅ Machine users + PAT │ ✅                   │ ✅                    │                                                     
  ├────────────────────────┼───────────────────────┼────────────────────────┼──────────────────────┼───────────────────────┤                                                     
  │ GitHub Stars           │ ~32,900               │ ~13,000                │ ~20,200              │ ~11,600               │                                                     
  ├────────────────────────┼───────────────────────┼────────────────────────┼──────────────────────┼───────────────────────┤                                                     
  │ Docker Compose         │ Single container + DB │ Single container + DB  │ Server + worker + DB │ Single container + DB │
  └────────────────────────┴───────────────────────┴────────────────────────┴──────────────────────┴───────────────────────┘

  Ory and SuperTokens were also evaluated — Ory requires 3-4 separate containers (too complex), SuperTokens needs paid tier for multi-tenancy.

  ━━━ 🧠  T H I N K ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  You're right that Keycloak is a strong choice. Here's the honest trade-off:

  Why Keycloak makes sense:
  - Most battle-tested (Red Hat backed, been around for 10+ years)
  - Largest ecosystem — every integration you'd ever need already exists
  - Passkeys fully GA since v26.4 (Sept 2025)
  - Multi-tenancy via Realms maps perfectly to our Tenant model (1 Realm = 1 Tenant)
  - Service accounts are first-class for the AI builder M2M flow
  - Most documentation, most Stack Overflow answers, most tutorials
  - Python/FastAPI integration is well-documented (via python-keycloak library)

  The one downside:
  - RAM: ~700MB at startup, 1-2GB recommended. On your laptop with OrbStack that's fine. On a small GCP VM it eats into your budget. But an e2-standard-4 (16GB RAM) handles it
  easily.

  The alternative I'd mention: Zitadel does everything Keycloak does at 1/5th the RAM, and it was purpose-built for multi-tenant SaaS. But it has a smaller community and fewer
  integrations. If RAM ever becomes a concern on smaller VMs, it's worth revisiting.

  My take: Keycloak is the safe, proven choice. You won't regret it. Want me to add it to the PRD and PLAN as the auth layer?

  🗣️  Kairos: Keycloak is the right call — most proven, has passkeys, multi-tenant realms, and service accounts. Just costs some RAM.
