# Agent HQ — Internal Agent Interaction Reference

## Overview
This document provides guidelines for AI agents interacting with the Agent HQ system.

## Communication Protocol

### WebSocket Events
All real-time communication uses the WebSocket protocol at `ws://localhost:8000/ws/activity`.
Event types are defined in `shared/events.py` — the `EventType` enum is the canonical list.

### Message Format
Every WebSocket message is wrapped in a `WSMessage` envelope (see `shared/schemas.py`):
```json
{
  "event": "task.created",
  "payload": { ... },
  "timestamp": "2026-01-01T00:00:00Z"
}
```

## Agent Engines
- **Claude** — Anthropic's Claude via CLI
- **Codex** — OpenAI Codex CLI
- **Gemini** — Google Gemini agent
- **Custom** — User-defined agent binary

## Guardrails
All destructive commands (rm -rf, DROP TABLE, etc.) are intercepted and require
human approval via the `approval_gate` module. Agents should never bypass this.

## Budget Enforcement
Each task has a hard budget limit (default $2.00). The `budget_enforcer` module
will terminate agents that exceed their allocation.

---

## Model Context Protocol (MCP) & Context Injection

### 1. What MCP is and Why We Use It
The Model Context Protocol (MCP) is an open standard that enables agents to securely connect to external tools and data sources. In Agent HQ, we use MCP to connect agents (like `claude-code`) to our **Nia Context Server**. 

This fundamentally solves the problem of AI hallucination in large codebases. By granting agents real-time, bidirectional awareness of the repository—its architecture, explicit dependency graphs, and latest API boundaries—the agent grounds its reasoning in actual project state rather than stale pre-training data.

### 2. The Execution Flow
When a user submits a task, the platform executes the following flow:
1. **Agent HQ Orchestrator spawns the agent** (e.g., `claude-code`).
2. The agent boots and automatically **reads `.agent_hq/mcp.json`**, discovering the `nia-context` server.
3. Before generating irreversible code changes, the agent **queries the Nia server** using tools like `get_architecture()` and `search_codebase()`.
4. The agent **receives exact architectural context** (e.g., "We use FastAPI, Pydantic v2 schemas, and Next.js App Router").
5. The agent **starts coding with full awareness**, drastically reducing errors, repeated feedback cycles, and wasted budget.

### 3. Skill Synthesis (Zero-Shot to M-Shot Optimization)
Agent HQ doesn't just pass context; it learns from successful task executions:
* **Recording Success:** When an agent successfully completes a complex task (e.g., "Add a new API endpoint"), the sequence of actions, queries, and file modifications is recorded.
* **Embedding the Recipe:** This successful workflow is vector-embedded into our knowledge store as a `SkillRecipe`.
* **Retrieval & Re-use:** When a similar task is requested in the future, the Nia server retrieves this "recipe" and injects it into the prompt payload.
* **Skipping Re-reasoning:** Rather than blindly exploring the codebase again, the agent follows the proven recipe. This skips redundant reasoning steps, saving massive amounts of time and execution tokens.
