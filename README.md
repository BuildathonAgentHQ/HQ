# 🚀 Agent HQ

**AI-powered command center for orchestrating autonomous coding agents.**

Agent HQ is an AI-powered command center that replaces manual code review and bug-fixing workflows with an autonomous agent swarm. Developers connect any GitHub repository through a single dashboard and get instant, deep code analysis powered by the Claude API — every open PR is reviewed for bugs, security vulnerabilities, missing tests, and performance issues, with plain-English explanations instead of raw linter output. When issues are found, users click "Fix" and a coordinated swarm of six specialized AI agents (Reviewer, FixGenerator, TestWriter, SecurityAuditor, RefactorAgent, DocWriter) work in parallel to generate precise code fixes, write tests, and push a clean PR — all visible in real-time through a swarm monitor. The system includes a full safety layer: destructive command interception with human approval gates, a 3-strike escalation protocol that triggers multi-agent debate when fixes fail repeatedly, per-task budget enforcement with automatic suspension at cost thresholds, and real-time telemetry tracking every token spent. The backend is a Python/FastAPI service with WebSocket-driven live updates, the frontend is a Next.js dashboard with radar charts, PR risk heatmaps, coverage treemaps, and FinOps analytics, and the entire architecture gracefully degrades — every external dependency (Claude API, GitHub, Nemotron, MLflow) has a local fallback, so the demo works even if services go down.

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

## GitHub OAuth (optional)

To enable "Sign in with GitHub" and the repo dropdown on the Repositories page:

1. Create an [OAuth App](https://github.com/settings/applications/new) on GitHub
2. Set **Authorization callback URL** to either:
   - `http://localhost:8000/api/auth/github/callback` or
   - `http://localhost:8000/api/github/auth/callback`  
   ⚠️ Must use port **8000** (backend). Both paths are supported.
3. Add to `.env`:
   ```
   GITHUB_CLIENT_ID=your_client_id
   GITHUB_CLIENT_SECRET=your_client_secret
   GITHUB_OAUTH_REDIRECT_URI=http://localhost:8000/api/auth/github/callback
   GITHUB_OAUTH_SCOPES=repo,read:user
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
