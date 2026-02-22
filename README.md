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

## Work Division

### Ayush Verma:
Designed the complete system architecture, defined all 15 Pydantic data contracts (schemas.py) that serve as the single source of truth across Python and TypeScript, built the monorepo scaffold with Makefile targets for parallel development, implemented the core Orchestrator (PTY-based ProcessManager for headless agent spawning with async stdout streaming, TaskManager with full lifecycle management), created the WebSocket infrastructure (ConnectionManager singleton + EventRouter), built the comprehensive mock data layer enabling 12+ hours of parallel development without blocking, wrote the config system with feature flags for graceful degradation, led the v2 architectural pivot replacing the Nia MCP dependency with Claude API as the native intelligence engine, designed and speced the Claude API client with retry logic and structured JSON parsing, architected the Swarm Orchestrator with dependency-aware parallel execution and the coordinator prompt system, designed the RepoManager for on-demand GitHub repo analysis, created the full integration test suite and validation framework covering all 30+ backend modules, and managed sprint execution across all workstreams.

### Madhav Tibrewal:
Built the Context Layer: Nia MCP Server integration with tree-sitter local fallback (NiaContextProvider that never crashes — returns empty context on failure rather than blocking agents), Skill Synthesis engine with TF-IDF vectorization for storing and retrieving successful task sequences as reusable recipes, and the Knowledge Base with PDF ingestion via PyPDF2, 500-character chunking with overlap, and keyword search for injecting business context into agent prompts. Built the entire Guardrails system: Janitor Protocol using Python watchdog for real-time file monitoring on code changes, LinterRunner orchestrating ruff/eslint/bandit with parsed error messages clean enough to feed back to agents as fix-it prompts, Destructive Action Interceptor with regex pattern matching for rm -rf/DROP TABLE/git push --force and 10+ dangerous command classes generating plain-English descriptions for non-technical approval, ApprovalGate managing pending approvals with suspend/resolve lifecycle, and the 3-Strike Escalation Manager that auto-injects fix prompts on strikes 1-2 and triggers multi-agent debate on strike 3 by spawning a secondary evaluation agent.

### Shachaf Rispler:
Built the Translation Layer: Nemotron API integration with strict system prompts enforcing JSON-only responses for status/error/severity/category classification, template-based pattern fallback covering 30+ terminal output patterns (package installation, git operations, test execution, compilation, server startup, error tracebacks, linting output, ANSI escape code stripping) that serves as both the mock and the production fallback, and the BatchProcessor accumulating raw stdout lines every 2 seconds with immediate flush on error markers. Built the Telemetry system: AgentTelemetry with MLflow run lifecycle management (start/tag/log/close), get_radar_metrics() using pandas and StandardScaler normalization, get_leaderboard() aggregation, TokenTracker with heuristic estimation (4 chars/token × 1.3x safety margin), BudgetEnforcer with 80% warning threshold and 100% hard suspend with ApprovalRequest emission, and the full Metrics API (radar, leaderboard, history, FinOps with projected burn rate, CSV export). Built the Control Plane: GitHub Connector with httpx, 5-minute cache, conditional requests via ETag, rate limit handling, and the new v2 methods for branch creation, file updates, and PR creation used by the swarm. PR Risk Scoring with weighted factors (diff_size 30%, core_files 25%, missing_tests 25%, churn 20%), dependency detection between overlapping PRs, and reviewer suggestion. Coverage Analyzer parsing coverage.json/xml with untested-diff detection and auto-generation of TestWriter tasks. Repo Health Analyzer surfacing CI status, flaky test detection (failed in 20-80% of runs), hot file ranking (top 10 most-changed in 30 days), and tech debt aging from TODO/FIXME/HACK comments with git blame. The Recommendation Engine generating prioritized Next Best Actions that convert directly into agent tasks.

### Arya Shidore:
Built the complete Next.js 14 frontend with App Router, Tailwind, and shadcn/ui: the Command Input component with engine/agent-type selectors and budget controls, the WebSocket-driven Activity Stream rendering real-time plain-English event cards with severity coloring, category badges, and relative timestamps (enforcing the zero-code/zero-terminal UI rule throughout), Task Cards with status badges, elapsed time, and budget progress bars, the Health Radar using Recharts RadarChart with 4-axis normalized scoring (Security/Stability/Quality/Speed), the Approval Modal with red destructive-action styling requiring double-click confirmation and safe-default reject, the Decision Gate modal for multi-agent debate resolution, Budget Exceeded cards with add-funds/terminate options, the Agent Leaderboard with sortable efficiency rankings, Knowledge Base sidebar with drag-and-drop PDF upload, the Timeline Slider for git history time-travel. Built all page routes: PR Radar with risk-scored cards and "Generate Tests" dispatch, Coverage Map with Recharts Treemap colored by coverage percentage, Repo Health with CI badges/flaky tests/hot files/tech debt, and the FinOps dashboard with spend charts and projections. Created the custom useWebSocket hook with exponential backoff reconnection and the typed useAPI wrapper.
