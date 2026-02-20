.PHONY: setup dev dev-backend dev-frontend test lint mock check docker-up docker-down clean env

# ═══════════════════════════════════════════════════════════════════════════════
#  Agent HQ — Makefile
# ═══════════════════════════════════════════════════════════════════════════════

# ── Setup ─────────────────────────────────────────────────────────────────────
setup: env                          ## Install all dependencies
	@echo "📦 Installing backend dependencies…"
	pip install -r backend/requirements.txt
	@echo "📦 Installing frontend dependencies…"
	cd frontend && npm install
	@echo "✅ Setup complete — run 'make dev' to start"

env:                                ## Create .env from example if missing
	@test -f .env || (cp .env.example .env && echo "📝 Created .env from .env.example")

# ── Development ───────────────────────────────────────────────────────────────
dev: env                            ## Start backend + frontend concurrently
	@echo "🚀 Starting Agent HQ (backend:$${WS_PORT:-8000} + frontend:3000)…"
	@PYTHONPATH=. uvicorn backend.app.main:app --reload --host 0.0.0.0 --port $${WS_PORT:-8000} & \
	cd frontend && npm run dev & \
	wait

dev-backend: env                    ## Start backend only
	PYTHONPATH=. uvicorn backend.app.main:app --reload --host 0.0.0.0 --port $${WS_PORT:-8000}

dev-frontend:                       ## Start frontend only
	cd frontend && npm run dev

# ── Mock server ───────────────────────────────────────────────────────────────
mock: env                           ## Start the standalone mock server
	@echo "🧪 Starting mock server on :8000…"
	PYTHONPATH=. python -m shared.mocks.mock_websocket

# ── Testing ───────────────────────────────────────────────────────────────────
test:                               ## Run all tests
	PYTHONPATH=. pytest backend/tests/ -v && cd frontend && npm test

test-backend:                       ## Run backend tests only
	PYTHONPATH=. pytest backend/tests/ -v

test-frontend:                      ## Run frontend tests only
	cd frontend && npm test

# ── Linting ───────────────────────────────────────────────────────────────────
lint:                               ## Run linters (ruff + next lint)
	ruff check backend/ shared/ && cd frontend && npm run lint

lint-fix:                           ## Auto-fix lint issues
	ruff check --fix backend/ shared/

# ── Docker ────────────────────────────────────────────────────────────────────
docker-up: env                      ## Start all services via Docker Compose
	docker compose up --build -d

docker-up-full: env                 ## Start all services including MLflow
	docker compose --profile full up --build -d

docker-down:                        ## Stop all Docker services
	docker compose --profile full down

docker-logs:                        ## Tail Docker logs
	docker compose logs -f

# ── Full check ────────────────────────────────────────────────────────────────
check: lint test                    ## Lint + test (CI gate)

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:                              ## Remove build artifacts
	rm -rf frontend/.next frontend/node_modules/.cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "🧹 Cleaned"

# ── Help ──────────────────────────────────────────────────────────────────────
help:                               ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
