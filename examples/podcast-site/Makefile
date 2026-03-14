# ============================================================
# Podcast Site — Example Makefile
# ============================================================
# Build, run, and deploy this example site independently.
#
# Usage:
#   make dev        — Start local dev server
#   make build      — Build for production
#   make docker     — Build Docker image
#   make deploy     — Build, push, and deploy to Adhara Engine

.PHONY: install dev build preview docker docker-run deploy clean help

IMAGE    ?= engine.localhost/podcast-site
TAG      ?= latest
PORT     ?= 3000
TENANT   ?= demo
WORKSPACE ?= sites

.DEFAULT_GOAL := help

# ── Development ──────────────────────────────────────────────

install: ## Install dependencies
	npm install

dev: node_modules ## Start local dev server (hot reload)
	npm run dev

build: node_modules ## Build for production
	npm run build

preview: build ## Preview production build locally
	npm run preview

node_modules: package.json
	npm install
	@touch node_modules

# ── Docker ───────────────────────────────────────────────────

docker: ## Build Docker image
	docker build -t $(IMAGE):$(TAG) .
	@echo ""
	@echo "Image built: $(IMAGE):$(TAG)"
	@echo "Run locally: make docker-run"

docker-run: ## Run the Docker image locally
	@echo "Starting on http://localhost:$(PORT)"
	docker run --rm -p $(PORT):3000 $(IMAGE):$(TAG)

# ── Deploy to Adhara Engine ──────────────────────────────────

push: docker ## Push image to Adhara Engine registry
	docker push $(IMAGE):$(TAG)
	@echo "Pushed $(IMAGE):$(TAG)"

deploy: push ## Build, push, and deploy to Adhara Engine
	@echo ""
	@echo "Creating site (if it doesn't exist)..."
	-adhara-engine site create \
		--workspace $(TENANT)/$(WORKSPACE) \
		--name "Podcast Site" \
		--source docker_image \
		--image "$(IMAGE):$(TAG)" \
		--port 3000 2>/dev/null
	@echo ""
	@echo "Deploying..."
	adhara-engine site deploy $(TENANT)/$(WORKSPACE)/podcast-site
	@echo ""
	@echo "============================================"
	@echo " Deployed! Open:"
	@echo " http://podcast-site.$(WORKSPACE).$(TENANT).localhost"
	@echo "============================================"

# ── Cleanup ──────────────────────────────────────────────────

clean: ## Remove build artifacts and node_modules
	rm -rf dist node_modules

# ── Help ─────────────────────────────────────────────────────

help: ## Show this help
	@echo "Podcast Site — Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Variables:"
	@echo "  IMAGE=$(IMAGE)  TAG=$(TAG)  TENANT=$(TENANT)  WORKSPACE=$(WORKSPACE)"
