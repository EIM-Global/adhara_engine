Plan: Client Site Deploy Documentation + Jungle Habitas Dockerfile       
                                                                                                                                                          
 Context                                                                                                                                                  
                                                                                                                                                          
 Adhara Engine can build and run Docker containers locally, but there's no documentation or UI guidance showing developers how to actually take a client  
 project (like a Vite+Express app deployed to Vercel), containerize it, and deploy it through Adhara Engine. This is the first real test of the deploy    
 pipeline with a real client site (Jungle Habitas).                       
                                                                                                                                                          
 Deliverables (5 items)                                                                                                                                   
                                                                                                                                                          
 1. Jungle Habitas Dockerfile + .dockerignore                                                                                                             
                                                                                                                                                          
 Files:                                                                   
 - /Users/pfarrell/projects/eim_clients/jungle_habitas/jungle_habitas/Dockerfile
 - /Users/pfarrell/projects/eim_clients/jungle_habitas/jungle_habitas/.dockerignore
                                                                          
 Multi-stage build:                                                       
 - Stage 1 (builder): node:20-alpine, npm ci, npm run build → produces dist/public/ (Vite client) + dist/index.cjs (esbuild server bundle)
 - Stage 2 (production): node:20-alpine, copy only dist/ — the server bundle is self-contained (esbuild inlines all server deps). No node_modules needed.
 - ENV NODE_ENV=production PORT=3000, EXPOSE 3000, CMD ["node", "dist/index.cjs"]
 - .dockerignore: node_modules, dist, .git, .DS_Store

 2. Deploy Guide — docs/DEPLOYING_SITES.md

 File: /Users/pfarrell/projects/eim_internal/adhara_engine/docs/DEPLOYING_SITES.md

 Comprehensive guide covering:
 - Overview — what Adhara Engine does, two deploy workflows
 - Prerequisites — engine running, CLI installed, tenant + workspace created
 - Writing a Dockerfile — requirements (single HTTP port, respect PORT env), multi-stage pattern, link to templates
 - Workflow 1: Pre-built Image — docker build → docker tag → docker push localhost:5000/... → adhara-engine site create --source docker_image →
 adhara-engine site deploy
 - Workflow 2: Git Repo — ensure Dockerfile at root → adhara-engine site create --source git_repo --source-url /path/to/repo → adhara-engine site deploy
 - Environment Variables — runtime vs build, auto-injected vars (ADHARA_*), CLI commands
 - Traefik Routing — hostname pattern, direct port access
 - Real-World Example — full walkthrough deploying Jungle Habitas using both workflows
 - Troubleshooting — common issues

 3. Dockerfile Templates — docs/examples/

 Files:
 - docs/examples/Dockerfile.vite-express — Vite + Express full-stack (like Jungle Habitas)
 - docs/examples/Dockerfile.nextjs — Next.js with standalone output
 - docs/examples/Dockerfile.static-vite — Static React/Vite SPA served by nginx

 Each template: multi-stage build, port 3000, inline comments explaining decisions.

 4. UI Workspace Page Update — WorkspaceDetail.tsx

 File: ui/src/pages/WorkspaceDetail.tsx

 Add a DeployGuide component:
 - Empty state (0 sites): Prominent card with "Deploy Your First Site" heading + 4-step CLI walkthrough with tenant/workspace slugs interpolated
 - Has sites (1+): Collapsible <details> section labeled "Deploy Guide"
 - Fetch tenant via api.getTenant(workspace.tenant_id) to get tenant slug
 - Code blocks styled bg-gray-900 text-green-400 font-mono text-xs rounded p-3 (matches existing Logs tab style)
 - Steps: build & push image → create site → deploy → open in browser

 5. LOCAL_SETUP.md Cross-Reference

 File: docs/LOCAL_SETUP.md

 Add a "Deploy Your Own App" section after the CLI walkthrough (~line 137) with a link to DEPLOYING_SITES.md and the docs/examples/ templates.

 Implementation Order

 1. Jungle Habitas Dockerfile (independent)
 2. Dockerfile templates (independent, parallel with #1)
 3. DEPLOYING_SITES.md (references templates + Jungle Habitas)
 4. WorkspaceDetail.tsx (independent of docs)
 5. LOCAL_SETUP.md update (just a cross-reference, last)

 Steps 1, 2, and 4 can run in parallel.

 Verification

 1. Build Jungle Habitas image: docker build -t jungle-habitas:latest . in the client project
 2. Verify it runs: docker run -p 3000:3000 -e SITE_URL=http://localhost:3000 jungle-habitas:latest
 3. Check the UI workspace page renders the deploy guide correctly (dev server)
 4. Review docs for accuracy against the actual CLI commands and API
