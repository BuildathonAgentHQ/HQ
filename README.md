# 🚀 Agent HQ

**AI-powered command center for orchestrating autonomous coding agents.**

Agent HQ provides a unified dashboard to spawn, monitor, and govern coding agents across your projects — with real-time translation of agent output, budget enforcement, guardrails against destructive operations, and deep GitHub integration.

---

## Architecture

| Layer | Tech | Purpose |
|---|---|---|
| **Frontend** | Next.js 14 + TailwindCSS + Recharts | Real-time dashboard & controls |
| **Backend** | Python 3.11 + FastAPI + WebSockets | Orchestration, guardrails, telemetry |
| **Shared** | Pydantic models | Single source of truth for schemas |

## Quick Start

```bash
# 1. Clone & install
git clone <repo-url> && cd agent-hq
cp .env.example .env          # Fill in API keys
make setup

# 2. Start dev servers (backend + frontend)
make dev

# 3. (Optional) Run mock servers for frontend development
make mock
```

## Make Targets

| Target | Description |
|---|---|
| `make setup` | Install Python and Node dependencies |
| `make dev` | Run backend (uvicorn) and frontend (next dev) concurrently |
| `make test` | Run pytest + frontend tests |
| `make lint` | Run ruff + eslint |
| `make mock` | Start mock WebSocket server for frontend dev |
| `make check` | Lint + test in one shot |

## Project Structure

```
agent-hq/
├── backend/          # FastAPI + orchestrator + guardrails + telemetry
├── frontend/         # Next.js dashboard
├── shared/           # Pydantic schemas, event enums, mock servers
├── docs/             # Architecture docs & agent reference
└── .agent_hq/        # MCP configuration
```

## Contributing

1. All data models live in `shared/schemas.py` — update there first.
2. Event types are defined in `shared/events.py`.
3. Backend modules expose FastAPI routers that are mounted in `backend/app/main.py`.
4. Frontend components consume the WebSocket stream via the `use-websocket` hook.

---

> **Status:** Scaffolding complete — business logic stubs only. See TODO markers throughout the codebase.
