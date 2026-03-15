# ============================================================
# Adhara Engine - Makefile
# ============================================================
# Runtime-agnostic: works with OrbStack, Docker Desktop,
# Docker Engine, Podman, Colima, or any Docker-compatible runtime.

.PHONY: init init-auth init-zitadel init-full \
        up up-auth up-zitadel up-full up-obs \
        down restart clean dev build \
        db-migrate db-seed db-reset \
        install cli-install status logs logs-api help \
        sites-status sites-down sites-up sites-restart \
        token

.DEFAULT_GOAL := help

# ── Host detection ───────────────────────────────────────────
# Use ADHARA_HOST from environment/.env, default to localhost
-include .env
export ADHARA_HOST ?= localhost
_HOST := $(ADHARA_HOST)

# ── Lifecycle ────────────────────────────────────────────────

init: .env ## First-time setup: core only (~500MB) — token auth
	docker compose up -d --build
	@echo "Waiting for database to be ready..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		docker compose exec -T db pg_isready -U engine -d adhara_engine > /dev/null 2>&1 && break; \
		sleep 2; \
	done
	docker compose exec -T api alembic upgrade head
	@echo ""
	@echo "============================================"
	@echo " Adhara Engine is ready (core profile)"
	@echo "============================================"
	@echo " UI:               http://$(_HOST)"
	@echo " API:              http://$(_HOST)/api"
	@echo " API (direct):     http://$(_HOST):8000"
	@echo " Traefik Dashboard: disabled (set insecure: true in traefik.yml to re-enable)"
	@echo "============================================"
	@echo ""
	@echo "Auth: token-based (run 'make token' to create one)"
	@echo "Want SSO? Run 'make init-auth' (Logto) or 'make init-zitadel'"
	@echo ""
	@echo "Run 'make status' to check service health."

init-auth: .env ## First-time setup: core + Logto SSO (~650MB)
	docker compose --profile auth up -d --build
	@echo "Waiting for database to be ready..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		docker compose exec -T db pg_isready -U engine -d adhara_engine > /dev/null 2>&1 && break; \
		sleep 2; \
	done
	docker compose exec -T api alembic upgrade head
	@echo ""
	@echo "============================================"
	@echo " Adhara Engine is ready (Logto SSO)"
	@echo "============================================"
	@echo " UI:               http://$(_HOST)"
	@echo " API:              http://$(_HOST)/api"
	@echo " Logto Admin:      http://$(_HOST):3002"
	@echo " Traefik Dashboard: disabled (set insecure: true in traefik.yml to re-enable)"
	@echo "============================================"
	@echo ""
	@echo "Next: Open Logto Admin to create an application and get your Client ID."
	@echo "Then set VITE_OIDC_CLIENT_ID in ui/.env and run: docker compose up -d --build ui"
	@echo ""
	@echo "Run 'make status' to check service health."

init-zitadel: .env ## First-time setup: core + Zitadel SSO (~1.3GB)
	docker compose --profile zitadel up -d --build
	@echo "Waiting for database to be ready..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		docker compose exec -T db pg_isready -U engine -d adhara_engine > /dev/null 2>&1 && break; \
		sleep 2; \
	done
	docker compose exec -T api alembic upgrade head
	@echo ""
	@echo "============================================"
	@echo " Adhara Engine is ready (Zitadel SSO)"
	@echo "============================================"
	@echo " UI:               http://$(_HOST)"
	@echo " API:              http://$(_HOST)/api"
	@echo " Zitadel Console:  http://$(_HOST)/ui/console/"
	@echo " Traefik Dashboard: disabled (set insecure: true in traefik.yml to re-enable)"
	@echo "============================================"
	@echo ""
	@echo "Next: Run 'bash scripts/setup-zitadel.sh' to configure OIDC."
	@echo ""
	@echo "Run 'make status' to check service health."

init-full: .env ## First-time setup: ALL services (~2GB) — Logto SSO, logging, registry, storage
	docker compose --profile all up -d --build
	@echo "Waiting for database to be ready..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		docker compose exec -T db pg_isready -U engine -d adhara_engine > /dev/null 2>&1 && break; \
		sleep 2; \
	done
	docker compose exec -T api alembic upgrade head
	@echo ""
	@echo "============================================"
	@echo " Adhara Engine is ready (full profile)"
	@echo "============================================"
	@echo " UI:               http://$(_HOST)"
	@echo " API:              http://$(_HOST)/api"
	@echo " Logto Admin:      http://$(_HOST):3002"
	@echo " Traefik Dashboard: disabled (set insecure: true in traefik.yml to re-enable)"
	@echo " Grafana:          http://$(_HOST):3003"
	@echo " MinIO Console:    http://$(_HOST):9001"
	@echo " Registry:         http://$(_HOST):5000"
	@echo "============================================"
	@echo ""
	@echo "Run 'make status' to check service health."

.env:
	cp .env.example .env
	@echo "Generating secure random secrets..."
	@SECRET=$$(openssl rand -base64 32) && sed -i.bak "s|ENGINE_SECRET_KEY=.*|ENGINE_SECRET_KEY=$$SECRET|" .env
	@SECRET=$$(openssl rand -base64 24) && sed -i.bak "s|POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$$SECRET|" .env
	@sed -i.bak "s|MINIO_ACCESS_KEY=.*|MINIO_ACCESS_KEY=$$(openssl rand -hex 12)|" .env
	@SECRET=$$(openssl rand -base64 24) && sed -i.bak "s|MINIO_SECRET_KEY=.*|MINIO_SECRET_KEY=$$SECRET|" .env
	@SECRET=$$(openssl rand -base64 24) && sed -i.bak "s|GRAFANA_PASSWORD=.*|GRAFANA_PASSWORD=$$SECRET|" .env
	@SECRET=$$(openssl rand -base64 24) && sed -i.bak "s|ZITADEL_DB_PASSWORD=.*|ZITADEL_DB_PASSWORD=$$SECRET|" .env
	@python3 -c "import secrets,string; print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(32)))" | xargs -I{} sed -i.bak "s|ZITADEL_MASTERKEY=.*|ZITADEL_MASTERKEY={}|" .env
	@rm -f .env.bak
	@echo "Created .env with auto-generated secrets."

.PHONY: _ensure-registry-auth
_ensure-registry-auth:
	@if [ -n "$$(docker compose ps -q registry 2>/dev/null)" ]; then \
		REGISTRY_USERNAME=$${REGISTRY_USERNAME:-admin}; \
		REGISTRY_PASSWORD=$${REGISTRY_PASSWORD:-$$(openssl rand -base64 24)}; \
		docker compose exec -T registry sh -c "apk add --no-cache apache2-utils > /dev/null 2>&1 && htpasswd -Bbn $$REGISTRY_USERNAME $$REGISTRY_PASSWORD > /auth/htpasswd" 2>/dev/null || \
		docker run --rm -v adhara-engine_registry-auth:/auth registry:2 sh -c "apk add --no-cache apache2-utils > /dev/null 2>&1 && htpasswd -Bbn $$REGISTRY_USERNAME $$REGISTRY_PASSWORD > /auth/htpasswd"; \
		echo "Registry auth configured for user: $$REGISTRY_USERNAME"; \
	fi

up: ## Start core services
	docker compose up -d
	@echo "Adhara Engine running (core)."

up-auth: ## Start core + Logto SSO (default SSO)
	docker compose --profile auth up -d
	@echo "Adhara Engine running (core + Logto)."

up-zitadel: ## Start core + Zitadel SSO (enterprise)
	docker compose --profile zitadel up -d
	@echo "Adhara Engine running (core + Zitadel)."

up-full: ## Start ALL services (all profiles)
	docker compose --profile all up -d
	@echo "Adhara Engine running (full)."

up-obs: ## Start core + observability (Grafana, Loki, Alloy)
	docker compose --profile observability up -d
	@echo "Adhara Engine running (core + observability)."

down: ## Stop all services (engine only — use sites-down for deployed sites)
	docker compose down
	@count=$$(docker ps -q --filter "label=adhara.engine=true" | wc -l | tr -d ' '); \
	if [ "$$count" != "0" ]; then \
		echo ""; \
		echo "⚠  $$count deployed site container(s) still running."; \
		echo "   Run 'make sites-down' to stop them too."; \
	fi

restart: ## Restart all services
	docker compose restart

clean: ## Stop everything and remove volumes (DESTRUCTIVE)
	@echo "WARNING: This will delete all data (database, storage, logs)."
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	docker compose down -v --remove-orphans

# ── Development ──────────────────────────────────────────────

dev: .env ## Start in dev mode (hot reload for API)
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
	@echo "Dev mode running. API hot-reloads on file changes."

build: ## Rebuild all images (no cache)
	docker compose build --no-cache

# ── Database ─────────────────────────────────────────────────

db-migrate: ## Run database migrations
	docker compose exec api alembic upgrade head

db-seed: ## Seed database with sample data
	docker compose exec api python scripts/seed.py

db-reset: ## Reset database (DESTRUCTIVE)
	@echo "WARNING: This will delete all database data."
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	docker compose exec api alembic downgrade base
	docker compose exec api alembic upgrade head

# ── API Token ─────────────────────────────────────────────────

token: ## Create a platform-admin API token and save to .env
	@echo "Creating platform-admin API token..."
	@echo "Waiting for API to be ready..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		docker compose exec -T api python -c "from app.core.database import SessionLocal; SessionLocal().execute('SELECT 1')" > /dev/null 2>&1 && break; \
		echo "  Waiting for database... ($$i/10)"; \
		sleep 3; \
	done
	@OUTPUT=$$(docker compose exec -T api python scripts/create_token.py 2>/tmp/adhara_token_err) && \
	TOKEN=$$(echo "$$OUTPUT" | grep "^ae_live_" | head -1) && \
	if [ -n "$$TOKEN" ]; then \
		if grep -q "^ADHARA_ENGINE_TOKEN=" .env 2>/dev/null; then \
			sed -i.bak "s|^ADHARA_ENGINE_TOKEN=.*|ADHARA_ENGINE_TOKEN=$$TOKEN|" .env && rm -f .env.bak; \
			echo "Updated ADHARA_ENGINE_TOKEN in .env"; \
		else \
			echo "" >> .env; \
			echo "ADHARA_ENGINE_TOKEN=$$TOKEN" >> .env; \
			echo "Added ADHARA_ENGINE_TOKEN to .env"; \
		fi; \
		echo ""; \
		echo "Token: $$TOKEN"; \
		echo ""; \
		echo "Use with: curl -H 'Authorization: Bearer $$TOKEN' ..."; \
	else \
		echo "ERROR: Failed to create token."; \
		echo "--- stdout ---"; \
		echo "$$OUTPUT"; \
		echo "--- stderr ---"; \
		cat /tmp/adhara_token_err 2>/dev/null; \
		rm -f /tmp/adhara_token_err; \
		exit 1; \
	fi
	@rm -f /tmp/adhara_token_err

# ── CLI ──────────────────────────────────────────────────────

install: ## Install the CLI tool globally (adds adhara-engine to PATH)
	uv tool install --from ./cli --force adhara-engine-cli
	@echo ""
	@echo "CLI installed globally. Run: adhara-engine --help"
	@echo "If not found, ensure ~/.local/bin is on your PATH."

cli-install: ## Install the CLI tool locally (in venv)
	cd cli && uv venv .venv && . .venv/bin/activate && uv pip install -e .
	@echo ""
	@echo "CLI installed. Activate with: source cli/.venv/bin/activate"
	@echo "Then run: adhara-engine --help"

# ── Monitoring ───────────────────────────────────────────────

status: ## Show status of all services
	@docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

logs: ## Tail logs from all services
	docker compose logs -f

logs-api: ## Tail API logs only
	docker compose logs -f api

logs-service: ## Tail logs for a specific service (usage: make logs-service SVC=traefik)
	docker compose logs -f $(SVC)

# ── Deployed Sites ───────────────────────────────────

sites-status: ## Show all deployed site containers
	@docker ps --filter "label=adhara.engine=true" \
		--format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" || true
	@echo ""
	@echo "$$(docker ps -q --filter 'label=adhara.engine=true' | wc -l | tr -d ' ') site(s) running."

sites-down: ## Stop and remove all deployed site containers
	@count=$$(docker ps -q --filter "label=adhara.engine=true" | wc -l | tr -d ' '); \
	if [ "$$count" = "0" ]; then \
		echo "No site containers running."; \
	else \
		echo "Stopping $$count site container(s):"; \
		docker ps --filter "label=adhara.engine=true" --format "  ⏹  {{.Names}}\t({{.Status}})" ; \
		docker ps -q --filter "label=adhara.engine=true" | xargs docker stop > /dev/null; \
		docker ps -aq --filter "label=adhara.engine=true" | xargs docker rm > /dev/null; \
		echo ""; \
		echo "All $$count site container(s) stopped and removed."; \
	fi

sites-up: ## Start all previously stopped site containers
	@count=$$(docker ps -aq --filter "label=adhara.engine=true" --filter "status=exited" | wc -l | tr -d ' '); \
	if [ "$$count" = "0" ]; then \
		echo "No stopped site containers to start."; \
		echo "Use 'adhara-engine site deploy' to deploy sites."; \
	else \
		echo "Starting $$count site container(s):"; \
		docker ps -a --filter "label=adhara.engine=true" --filter "status=exited" --format "  ▶  {{.Names}}" ; \
		docker ps -aq --filter "label=adhara.engine=true" --filter "status=exited" | xargs docker start > /dev/null; \
		echo ""; \
		echo "All $$count site container(s) started."; \
	fi

sites-restart: ## Restart all deployed site containers
	@count=$$(docker ps -q --filter "label=adhara.engine=true" | wc -l | tr -d ' '); \
	if [ "$$count" = "0" ]; then \
		echo "No site containers running."; \
	else \
		echo "Restarting $$count site container(s):"; \
		docker ps --filter "label=adhara.engine=true" --format "  ♻  {{.Names}}\t({{.Status}})" ; \
		docker ps -q --filter "label=adhara.engine=true" | xargs docker restart > /dev/null; \
		echo ""; \
		echo "All $$count site container(s) restarted."; \
	fi

# ── Help ─────────────────────────────────────────────────────

help: ## Show this help
	@echo "Adhara Engine - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""
