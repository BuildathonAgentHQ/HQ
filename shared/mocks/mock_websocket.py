"""
shared/mocks/mock_websocket.py — Standalone mock server for frontend development.

Runs a fully-functional FastAPI application on port 8000 that serves:

- **WebSocket** at ``/ws/activity`` — streams ``SAMPLE_TRANSLATED_EVENTS``
  as ``WebSocketEvent`` payloads every 2 seconds, looping forever.
- **REST endpoints** for every API the frontend consumes, returning
  sample data from ``mock_data.py``.

Usage::

    # From the repo root (shared/ must be on PYTHONPATH):
    PYTHONPATH=. python -m shared.mocks.mock_websocket

    # or
    PYTHONPATH=. uvicorn shared.mocks.mock_websocket:app --reload --port 8000

When the real backend is ready, Teammate C just changes the URL.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from shared.events import EventType, create_ws_event
from shared.schemas import Task, TaskCreate, WebSocketEvent
from shared.mocks.mock_data import (
    SAMPLE_ACTIONS,
    SAMPLE_COVERAGE,
    SAMPLE_LEADERBOARD,
    SAMPLE_PR_SCORES,
    SAMPLE_RADAR_METRICS,
    SAMPLE_REPO_HEALTH,
    SAMPLE_TASKS,
    SAMPLE_TRANSLATED_EVENTS,
)

logger = logging.getLogger(__name__)

# ── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Agent HQ — Mock Server",
    description="Fake backend for frontend development. Streams sample events over WS.",
    version="0.0.1-mock",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory task store seeded with sample data
_tasks: dict[str, Task] = {t.id: t for t in SAMPLE_TASKS}


# ═══════════════════════════════════════════════════════════════════════════════
#  WebSocket — /ws/activity
# ═══════════════════════════════════════════════════════════════════════════════


@app.websocket("/ws/activity")
async def ws_activity(websocket: WebSocket) -> None:
    """Stream translated events to the frontend in an infinite loop.

    On connect:
        1. Sends a welcome ``task_lifecycle`` event.
        2. Begins streaming ``SAMPLE_TRANSLATED_EVENTS`` as
           ``WebSocketEvent`` payloads every 2 seconds.
        3. After all 20 events, loops back to the beginning.

    The client can also send JSON messages; they are logged but otherwise
    ignored (for future bidirectional support).
    """
    await websocket.accept()

    # Welcome message
    welcome = create_ws_event(
        task_id="system",
        event_type=EventType.TASK_LIFECYCLE,
        payload={"message": "Connected to Agent HQ Mock Server"},
    )
    await websocket.send_json(welcome.model_dump(mode="json"))

    # Start concurrent tasks: sender + receiver
    async def sender() -> None:
        """Infinite loop: stream sample events every 2 seconds."""
        idx = 0
        while True:
            evt = SAMPLE_TRANSLATED_EVENTS[idx % len(SAMPLE_TRANSLATED_EVENTS)]
            ws_event = create_ws_event(
                task_id=evt.task_id,
                event_type=EventType.STATUS_UPDATE,
                payload=evt.model_dump(mode="json"),
            )
            await websocket.send_json(ws_event.model_dump(mode="json"))
            idx += 1
            await asyncio.sleep(2)

    async def receiver() -> None:
        """Listen for client messages (approval responses, subscriptions)."""
        async for data in websocket.iter_json():
            logger.info("Mock server received: %s", data)

    try:
        # Run both concurrently; if either exits, the other is cancelled
        async with asyncio.TaskGroup() as tg:
            tg.create_task(sender())
            tg.create_task(receiver())
    except* WebSocketDisconnect:
        logger.info("Client disconnected from mock WebSocket")
    except* Exception as exc:
        logger.debug("Mock WebSocket closed: %s", exc)


# ═══════════════════════════════════════════════════════════════════════════════
#  REST — Task endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@app.get("/api/tasks", response_model=list[Task])
async def list_tasks() -> list[Task]:
    """Return all sample tasks."""
    return list(_tasks.values())


@app.get("/api/tasks/{task_id}", response_model=Task)
async def get_task(task_id: str) -> Task:
    """Return a single task by ID."""
    from fastapi import HTTPException

    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/api/tasks", response_model=Task)
async def create_task(payload: TaskCreate) -> Task:
    """Create a new task from a TaskCreate payload.

    Returns a Task with status ``"pending"`` and a fresh UUID.
    """
    task = Task(
        id=str(uuid.uuid4()),
        task=payload.task,
        engine=payload.engine,
        agent_type=payload.agent_type,
        status="pending",
        budget_limit=payload.budget_limit,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    _tasks[task.id] = task
    return task


# ═══════════════════════════════════════════════════════════════════════════════
#  REST — Metrics / Telemetry
# ═══════════════════════════════════════════════════════════════════════════════


@app.get("/api/metrics/radar")
async def get_radar() -> dict[str, Any]:
    """Return sample radar metrics."""
    return SAMPLE_RADAR_METRICS.model_dump(mode="json")


@app.get("/api/metrics/leaderboard")
async def get_leaderboard() -> list[dict[str, Any]]:
    """Return sample leaderboard data."""
    return [e.model_dump(mode="json") for e in SAMPLE_LEADERBOARD]


# ═══════════════════════════════════════════════════════════════════════════════
#  REST — Control Plane
# ═══════════════════════════════════════════════════════════════════════════════


@app.get("/api/control-plane/prs")
async def get_prs() -> list[dict[str, Any]]:
    """Return sample PR risk scores."""
    return [p.model_dump(mode="json") for p in SAMPLE_PR_SCORES]


@app.get("/api/control-plane/coverage")
async def get_coverage() -> dict[str, Any]:
    """Return sample coverage report."""
    return SAMPLE_COVERAGE.model_dump(mode="json")


@app.get("/api/control-plane/health")
async def get_health() -> dict[str, Any]:
    """Return sample repo health report."""
    return SAMPLE_REPO_HEALTH.model_dump(mode="json")


@app.get("/api/control-plane/actions")
async def get_actions() -> list[dict[str, Any]]:
    """Return sample next-best-action recommendations."""
    return [a.model_dump(mode="json") for a in SAMPLE_ACTIONS]


# ═══════════════════════════════════════════════════════════════════════════════
#  Health
# ═══════════════════════════════════════════════════════════════════════════════


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check."""
    return {"status": "ok", "mode": "mock"}


# ── CLI entry point ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    print("🧪 Starting Agent HQ Mock Server on http://localhost:8000")
    print("   WebSocket:  ws://localhost:8000/ws/activity")
    print("   REST:       http://localhost:8000/api/tasks")
    print("   Health:     http://localhost:8000/health")
    print()
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
