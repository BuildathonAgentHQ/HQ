# Force PowerShell as the shell for Windows compatibility
SHELL := powershell.exe
.SHELLFLAGS := -NoProfile -Command

.PHONY: setup dev dev-backend dev-frontend test lint mock check docker-up docker-down clean env help

# ═══════════════════════════════════════════════════════════════════════════════
#  Agent HQ — Makefile (Windows/PowerShell)
# ═══════════════════════════════════════════════════════════════════════════════

# ── Setup ─────────────────────────────────────────────────────────────────────
setup: env                          ## Install all dependencies
	Write-Host '📦 Installing backend dependencies…'
	pip install -r backend/requirements.txt
	Write-Host '📦 Installing frontend dependencies…'
	Push-Location frontend; npm install; Pop-Location
	Write-Host '✅ Setup complete — run make dev to start'

env:                                ## Create .env from example if missing
	if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host '📝 Created .env from .env.example' }

# ── Development ───────────────────────────────────────────────────────────────
dev: env                            ## Start backend + frontend concurrently
	Write-Host '🚀 Starting Agent HQ (backend + frontend)…'
	$$backendPort = if ($$env:WS_PORT) { $$env:WS_PORT } else { '8000' }; \
	$$env:PYTHONPATH = '.'; \
	$$backend = Start-Process -PassThru -NoNewWindow pwsh -ArgumentList '-NoProfile','-Command',"uvicorn backend.app.main:app --reload --host 0.0.0.0 --port $$backendPort"; \
	Push-Location frontend; npm run dev; Pop-Location; \
	Stop-Process -Id $$backend.Id -ErrorAction SilentlyContinue

dev-backend: env                    ## Start backend only
	$$backendPort = if ($$env:WS_PORT) { $$env:WS_PORT } else { '8000' }; \
	$$env:PYTHONPATH = '.'; \
	uvicorn backend.app.main:app --reload --host 0.0.0.0 --port $$backendPort

dev-frontend:                       ## Start frontend only
	Push-Location frontend; npm run dev; Pop-Location

# ── Mock server ───────────────────────────────────────────────────────────────
mock: env                           ## Start the standalone mock server
	Write-Host '🧪 Starting mock server on :8000…'
	$$env:PYTHONPATH = '.'; python -m shared.mocks.mock_websocket

# ── Testing ───────────────────────────────────────────────────────────────────
test:                               ## Run all tests
	$$env:PYTHONPATH = '.'; pytest backend/tests/ -v
	Push-Location frontend; npm test; Pop-Location

test-backend:                       ## Run backend tests only
	$$env:PYTHONPATH = '.'; pytest backend/tests/ -v

test-frontend:                      ## Run frontend tests only
	Push-Location frontend; npm test; Pop-Location

# ── Linting ───────────────────────────────────────────────────────────────────
lint:                               ## Run linters (ruff + next lint)
	ruff check backend/ shared/
	Push-Location frontend; npm run lint; Pop-Location

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
	if (Test-Path frontend/.next) { Remove-Item -Recurse -Force frontend/.next }
	if (Test-Path frontend/node_modules/.cache) { Remove-Item -Recurse -Force frontend/node_modules/.cache }
	Get-ChildItem -Recurse -Directory -Filter __pycache__ -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
	Write-Host '🧹 Cleaned'

# ── Help ──────────────────────────────────────────────────────────────────────
help:                               ## Show this help
	Get-Content $(MAKEFILE_LIST) | Select-String '^\w.*##' | ForEach-Object { $$line = $$_ -replace ':\s*(?:.*?)##\s*', '||'; $$parts = $$line -split '\|\|'; Write-Host ('  {0,-18} {1}' -f $$parts[0], $$parts[1]) -ForegroundColor Cyan }
