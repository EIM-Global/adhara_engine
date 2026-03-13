 Plan: GCP VM Deploy Script — scripts/deploy.sh                                         
                                                                                                                                                          
 Context                                                                                                                                                  
                                                                          
 Adhara Engine has thorough documentation for GCP deployment (docs/GCP_DEPLOYMENT.md) but no automation. The manual process is ~20 commands across VM     
 setup, Docker install, repo clone, secrets config, engine start, and site deploy. This script automates the entire pipeline for deploying to a fresh     
 Ubuntu GCP VM, with step-skipping for partially-configured machines.                                                                                     
                                                                          
 File                                                                                                                                                     
                                                                                                                                                          
 - /Users/pfarrell/projects/eim_internal/adhara_engine/scripts/deploy.sh — single self-contained bash script
                                                                          
 Design                                                              
                                                                                                                                                          
 Structure: Step-Based with Skip Prompts                                                                                                                  
                                                                          
 Each step checks if work is already done, then prompts to skip or proceed:
                                     
 Step 1/7: Install Docker
   → Detects: `docker --version` succeeds?
   → If yes: "Docker 27.x found. Skip? [Y/n]"
   → If no: Installs via get.docker.com, adds user to docker group

 Step 2/7: Install Docker Compose
   → Detects: `docker compose version` succeeds?
   → Same skip pattern

 Step 3/7: Install Git + Clone Repo
   → Detects: git installed? repo directory exists?
   → Clones adhara-engine repo (prompts for repo URL or uses default)

 Step 4/7: Configure Environment
   → Detects: .env file exists?
   → If no: Interactive prompts for:
     - Domain (e.g. engine.adharaweb.com)
     - ACME email for Let's Encrypt
     - Auto-generates all passwords/secrets with openssl
   → If yes: "Existing .env found. Reconfigure? [y/N]"

 Step 5/7: Start Adhara Engine
   → Runs: make init, waits for health, runs make db-migrate
   → Detects: containers already running? Prompts to restart or skip

 Step 6/7: Build & Push Jungle Habitas
   → Prompts for path to Jungle Habitas source (default: clones from git)
   → Runs: docker build, docker tag, docker push to localhost:5000

 Step 7/7: Deploy Jungle Habitas Site
   → Creates tenant + workspace if they don't exist (interactive name prompts)
   → Creates site, deploys, prints URL

 Key Design Decisions

 1. Single file, no dependencies — runs on a bare Ubuntu VM with just bash and curl
 2. Idempotent — safe to run multiple times; detects existing state
 3. Interactive prompts with sane defaults — user can accept defaults by pressing Enter
 4. Color output — green for success, yellow for skip, red for errors
 5. Generates traefik/dynamic/api.yml — the production Traefik routing config that GCP_DEPLOYMENT.md documents but doesn't exist in the repo
 6. Installs CLI — sets up Python venv and installs adhara-engine CLI as part of Step 5

 Secrets Handling (Step 4)

 Interactive prompts for user-facing config:
 - DOMAIN → used for Traefik, Zitadel external domain, ACME
 - ACME_EMAIL → Let's Encrypt contact

 Auto-generated (shown to user, saved to .env):
 - ENGINE_SECRET_KEY — openssl rand -hex 32
 - POSTGRES_PASSWORD — openssl rand -hex 16
 - MINIO_SECRET_KEY — openssl rand -hex 16
 - ZITADEL_MASTERKEY — openssl rand -hex 16 (32 chars)
 - ZITADEL_DB_PASSWORD — openssl rand -hex 16
 - GRAFANA_PASSWORD — openssl rand -hex 16

 Helper Functions

 - info(), success(), warn(), error() — colored output
 - confirm(prompt, default) — y/n prompt with default
 - prompt_value(prompt, default) — string input with default
 - check_command(cmd) — tests if command exists
 - wait_healthy() — polls docker compose ps until all services healthy

 Reference Files

 - docs/GCP_DEPLOYMENT.md — the authoritative source for all GCP steps (firewall, DNS, Traefik config)
 - .env.example — template for all env vars
 - Makefile — init, build, db-migrate, status targets

 Verification

 1. Read through the script to verify each step matches GCP_DEPLOYMENT.md
 2. Test locally: bash scripts/deploy.sh — should detect existing Docker, skip installs, work through engine + site deploy steps
 3. Verify the generated .env contains all required variables from .env.example
 4. Verify traefik/dynamic/api.yml is generated correctly when a domain is provided