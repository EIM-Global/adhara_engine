Plan: Authentication & Login — Zitadel OIDC Integration                                                                                                  
                                                                                                                                                          
 Context                                                                  
                                                                          
 Adhara Engine has Zitadel running as an identity provider (port 8081) and a fully-implemented JWT validation middleware in api/app/core/auth.py, but
 nothing is wired up. The UI has no login page, no token handling, and all API routes are unprotected. This needs to be implemented before deploying to
 the cloud.                                                                                                                                               
                                                                                                                                                          
 What already exists:                                                     
 - Zitadel running in Docker Compose (localhost:8081, TLS disabled)       
 - auth.py with get_current_user(), require_auth(), require_role() — all using JWKS + RS256
 - Config: zitadel_domain and zitadel_issuer in settings                  
 - PyJWT + httpx already in requirements.txt                         
                                                                                                                                                          
 What's missing:                                                                                                                                          
 - Zitadel OIDC application not created (need client_id)                  
 - UI has no auth library, login page, or token handling                  
 - API routes have no auth dependencies applied
 - No Authorization header sent with API requests

 Approach: OIDC PKCE Flow

 User → React (SPA) → Zitadel Login → Redirect back with code → Token Exchange → JWT
 React attaches JWT to API calls → FastAPI validates via existing auth.py middleware

 ---
 Phase 1: Zitadel Setup Script

 File: scripts/setup-zitadel.sh

 One-time Zitadel console setup. The OIDC app creation requires the console UI or Management API. The script will:

 1. Wait for Zitadel to be healthy (/debug/healthz)
 2. Print step-by-step instructions to:
   - Log into Zitadel console at http://localhost:8081/ui/console/
   - Default admin credentials: zitadel-admin@zitadel.localhost / Password1!
   - Create a new Project called "Adhara Engine"
   - Create an Application: type User Agent (SPA), auth method PKCE
   - Set redirect URIs: http://localhost:5173/auth/callback, http://engine.localhost/auth/callback
   - Set post-logout URIs: http://localhost:5173, http://engine.localhost
   - Copy the generated client_id
 3. Prompt user to paste the client_id and write it to .env

 New env vars (.env.example):
 ZITADEL_CLIENT_ID=          # from Zitadel console → Project → Application

 ---
 Phase 2: UI Authentication

 Install dependency

 cd ui && pnpm add oidc-client-ts react-oidc-context

 Using react-oidc-context (wraps oidc-client-ts) — standard OIDC library, well-maintained, not Zitadel-specific.

 New/Modified Files

 ui/src/auth/config.ts (NEW)
 - OIDC configuration:
   - authority: VITE_ZITADEL_ISSUER (e.g. http://localhost:8081)
   - client_id: VITE_ZITADEL_CLIENT_ID
   - redirect_uri: ${window.location.origin}/auth/callback
   - post_logout_redirect_uri: ${window.location.origin}
   - scope: openid profile email urn:zitadel:iam:org:projects:roles
   - response_type: code (PKCE)

 ui/src/auth/AuthProvider.tsx (NEW)
 - Wraps AuthProvider from react-oidc-context
 - Provides auth context to entire app

 ui/src/pages/Login.tsx (NEW)
 - Login page with "Sign in" button
 - Calls auth.signinRedirect() → redirects to Zitadel login
 - Shows loading state during redirect

 ui/src/components/ProtectedRoute.tsx (NEW)
 - Checks auth.isAuthenticated
 - Not authenticated → redirect to /login
 - Loading → spinner
 - Authenticated → render children

 ui/src/components/Layout.tsx (MODIFY)
 - Add user info + logout button to sidebar footer
 - Show user name/email from OIDC claims
 - Logout calls auth.signoutRedirect()

 ui/src/api/client.ts (MODIFY)
 - Add token getter: let _getToken: (() => string | undefined) | null = null
 - Export setTokenGetter(fn) called from AuthProvider
 - Attach Authorization: Bearer {token} to all requests when token available

 ui/src/App.tsx (MODIFY)
 - Wrap routes in AuthProvider
 - Add /login route (public, outside ProtectedRoute)
 - Add /auth/callback route (OIDC redirect handler)
 - Wrap Layout in ProtectedRoute

 Auth Flow

 1. User visits any page → ProtectedRoute checks auth
 2. Not authenticated → redirect to /login
 3. Click "Sign In" → signinRedirect() → Zitadel login page
 4. Login success → redirect to /auth/callback with auth code
 5. react-oidc-context exchanges code for tokens via PKCE
 6. Authenticated → redirect to original page
 7. All API calls include Authorization: Bearer {access_token}

 ---
 Phase 3: Protect API Routes

 Apply require_auth dependency to all route handlers (except /health):

 api/app/routers/tenants.py — add user: dict = Depends(require_auth) to create, delete
 api/app/routers/workspaces.py — same for create, delete
 api/app/routers/sites.py — all endpoints (list_all, create, delete, env, ports)
 api/app/routers/deployments.py — deploy, stop, restart, logs, status
 api/app/routers/services.py — all endpoints
 api/app/routers/domains.py — all write operations

 Read-only endpoints (list tenants, get tenant) stay optionally auth'd for now.

 /health stays public for monitoring.

 Gradual approach: Apply require_auth first (any logged-in user). Role-based access (require_role("admin")) layered in a follow-up once roles are
 configured in Zitadel.

 ---
 Phase 4: Env Config

 ui/.env.example (NEW)
 VITE_ZITADEL_ISSUER=http://localhost:8081
 VITE_ZITADEL_CLIENT_ID=

 .env.example (MODIFY) — add ZITADEL_CLIENT_ID

 ---
 Files Summary

 ┌──────────────────────────────────────┬────────┬───────────────────────────────┐
 │                 File                 │ Action │            Purpose            │
 ├──────────────────────────────────────┼────────┼───────────────────────────────┤
 │ scripts/setup-zitadel.sh             │ NEW    │ Zitadel OIDC app setup guide  │
 ├──────────────────────────────────────┼────────┼───────────────────────────────┤
 │ .env.example                         │ MODIFY │ Add ZITADEL_CLIENT_ID         │
 ├──────────────────────────────────────┼────────┼───────────────────────────────┤
 │ ui/.env.example                      │ NEW    │ Vite auth env vars            │
 ├──────────────────────────────────────┼────────┼───────────────────────────────┤
 │ ui/src/auth/config.ts                │ NEW    │ OIDC configuration            │
 ├──────────────────────────────────────┼────────┼───────────────────────────────┤
 │ ui/src/auth/AuthProvider.tsx         │ NEW    │ React auth context wrapper    │
 ├──────────────────────────────────────┼────────┼───────────────────────────────┤
 │ ui/src/pages/Login.tsx               │ NEW    │ Login page                    │
 ├──────────────────────────────────────┼────────┼───────────────────────────────┤
 │ ui/src/components/ProtectedRoute.tsx │ NEW    │ Auth gate for routes          │
 ├──────────────────────────────────────┼────────┼───────────────────────────────┤
 │ ui/src/components/Layout.tsx         │ MODIFY │ User info + logout in sidebar │
 ├──────────────────────────────────────┼────────┼───────────────────────────────┤
 │ ui/src/api/client.ts                 │ MODIFY │ Attach Bearer token           │
 ├──────────────────────────────────────┼────────┼───────────────────────────────┤
 │ ui/src/App.tsx                       │ MODIFY │ Auth routes + wrapper         │
 ├──────────────────────────────────────┼────────┼───────────────────────────────┤
 │ api/app/routers/tenants.py           │ MODIFY │ Add require_auth              │
 ├──────────────────────────────────────┼────────┼───────────────────────────────┤
 │ api/app/routers/workspaces.py        │ MODIFY │ Add require_auth              │
 ├──────────────────────────────────────┼────────┼───────────────────────────────┤
 │ api/app/routers/sites.py             │ MODIFY │ Add require_auth              │
 ├──────────────────────────────────────┼────────┼───────────────────────────────┤
 │ api/app/routers/deployments.py       │ MODIFY │ Add require_auth              │
 ├──────────────────────────────────────┼────────┼───────────────────────────────┤
 │ api/app/routers/services.py          │ MODIFY │ Add require_auth              │
 ├──────────────────────────────────────┼────────┼───────────────────────────────┤
 │ api/app/routers/domains.py           │ MODIFY │ Add require_auth              │
 └──────────────────────────────────────┴────────┴───────────────────────────────┘

 ---
 Verification

 1. Zitadel healthy: curl http://localhost:8081/debug/healthz
 2. OIDC discovery: curl http://localhost:8081/.well-known/openid-configuration
 3. Login flow: Visit http://localhost:5173 → redirected to /login → Sign In → Zitadel → authenticated
 4. API protection: curl http://localhost:8000/api/v1/sites → 401
 5. API with token: UI requests succeed with Bearer token
 6. Logout: Click logout → Zitadel → login page → session cleared
