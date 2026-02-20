# Agent HQ — System Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Next.js Frontend                         │
│  ┌──────────┐ ┌──────────────┐ ┌───────────┐ ┌──────────────┐  │
│  │ Command  │ │  Activity    │ │  Health   │ │   Budget     │  │
│  │  Input   │ │   Stream     │ │   Radar   │ │    Card      │  │
│  └────┬─────┘ └──────┬───────┘ └─────┬─────┘ └──────┬───────┘  │
│       │              │               │               │          │
│       └──────────────┴───────────────┴───────────────┘          │
│                          │ WebSocket + REST                     │
└──────────────────────────┼──────────────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────────────┐
│                    FastAPI Backend                               │
│                          │                                      │
│  ┌───────────────────────┴───────────────────────────────────┐  │
│  │                   WebSocket Manager                        │  │
│  └───────────┬───────────┬───────────┬───────────┬───────────┘  │
│              │           │           │           │              │
│  ┌───────────┴──┐ ┌──────┴─────┐ ┌───┴────┐ ┌───┴──────────┐  │
│  │ Orchestrator │ │ Translation│ │ Guard- │ │  Telemetry   │  │
│  │   (PTY)     │ │ (Nemotron) │ │  rails │ │  (MLflow)    │  │
│  └──────────────┘ └────────────┘ └────────┘ └──────────────┘  │
│              │                                                  │
│  ┌───────────┴──┐ ┌────────────────────────────────────────┐   │
│  │   Context    │ │         Control Plane (GitHub)          │   │
│  │  (Nia MCP)   │ │  PR Analysis · Coverage · Repo Health  │   │
│  └──────────────┘ └────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │   shared/schemas.py     │
              │   (Source of Truth)      │
              └─────────────────────────┘
```

## Module Responsibilities

| Module | Owner | Purpose |
|--------|-------|---------|
| `orchestrator` | — | PTY process spawning, task lifecycle |
| `context` | Teammate A | Nia MCP integration, knowledge base |
| `translation` | Teammate B | Nemotron stdout→English translation |
| `guardrails` | Teammate A | File watching, linting, destructive-op blocking |
| `telemetry` | Teammate B | MLflow tracking, token/cost metrics |
| `control_plane` | Teammate D | GitHub PR analysis, coverage, recommendations |
| `websocket` | — | Connection management, event broadcast |

## Data Flow

1. **User** submits a task via the Command Input component
2. **Orchestrator** spawns a PTY subprocess for the chosen agent engine
3. **Translation** layer batches raw output every 2 seconds, sends to Nemotron
4. **Guardrails** watch for destructive commands and file changes
5. **Telemetry** tracks tokens, cost, and logs to MLflow
6. **WebSocket Manager** broadcasts all events to connected frontends
7. **Control Plane** provides GitHub repo health on demand

---

> **TODO:** Add sequence diagrams for key flows (task creation, approval gate, budget exceeded).
