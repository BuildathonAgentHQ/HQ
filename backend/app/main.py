"""
backend/app/main.py — FastAPI entry point for Agent HQ.

Wires together all modules: orchestrator, telemetry, control-plane,
knowledge, timeline, and real-time WebSocket streaming.

Every endpoint returns mock data immediately so the frontend team can
develop against a working API from hour 2.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.app.websocket.manager import manager as ws_manager
from backend.app.websocket.events import event_router
from shared.events import EventType, create_ws_event

# ── Router imports ──────────────────────────────────────────────────────────
from backend.app.orchestrator.router import router as orchestrator_router
from backend.app.telemetry.metrics_api import router as telemetry_router
from backend.app.control_plane.router import router as control_plane_router
from backend.app.knowledge.router import router as knowledge_router
from backend.app.timeline.router import router as timeline_router

logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ───────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    Startup:
        - Log startup message
        - TODO: Initialize PTY pool, MLflow, file watcher, Nia MCP

    Shutdown:
        - Gracefully close all WebSocket connections
        - TODO: Terminate agent processes, flush telemetry
    """
    logger.info("Agent HQ Backend Started")
    print("🚀 Agent HQ Backend Started")
    yield
    # Graceful shutdown: close all remaining WebSocket connections
    for ws in list(ws_manager.active_connections):
        try:
            await ws.close()
        except Exception:
            pass
    logger.info("👋 Agent HQ Backend Stopped")


# ── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Agent HQ API",
    description="AI-powered command centre for orchestrating autonomous coding agents",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS — allow all origins for development ────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── REST route registrations ────────────────────────────────────────────────
app.include_router(orchestrator_router,   prefix="/api/tasks",          tags=["tasks"])
app.include_router(telemetry_router,      prefix="/api/metrics",        tags=["metrics"])
app.include_router(control_plane_router,  prefix="/api/control-plane",  tags=["control-plane"])
app.include_router(knowledge_router,      prefix="/api/knowledge",      tags=["knowledge"])
app.include_router(timeline_router,       prefix="/api/timeline",       tags=["timeline"])


# ── WebSocket endpoint ──────────────────────────────────────────────────────


@app.websocket("/ws/activity")
async def websocket_activity(websocket: WebSocket) -> None:
    """Real-time activity streaming via WebSocket.

    Lifecycle:
        1. Accept the connection via ``ConnectionManager``.
        2. Send a welcome event so the client knows it's live.
        3. Enter a receive loop for bidirectional messaging
           (subscriptions, approvals).
        4. On disconnect, remove from the manager.

    Supported client messages (``{"type": ..., "payload": {...}}``):
        - ``subscribe``   → ``{"task_id": "..."}``
        - ``unsubscribe`` → ``{"task_id": "..."}``
        - ``approve``     → ``{"task_id": "...", "approved": true}``
    """
    await ws_manager.connect(websocket)

    # Welcome event
    welcome = create_ws_event(
        task_id="system",
        event_type=EventType.TASK_LIFECYCLE,
        payload={
            "message": "Connected to Agent HQ",
            "active_connections": ws_manager.connection_count,
        },
    )
    await ws_manager.send_personal(websocket, welcome)

    try:
        while True:
            data: dict[str, Any] = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "subscribe" and "task_id" in data.get("payload", {}):
                await ws_manager.subscribe(websocket, data["payload"]["task_id"])

            elif msg_type == "unsubscribe" and "task_id" in data.get("payload", {}):
                await ws_manager.unsubscribe(websocket, data["payload"]["task_id"])

            elif msg_type == "approve":
                logger.info("Approval response received: %s", data.get("payload"))

            else:
                logger.warning("Unknown WS message type: %s", msg_type)

    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception:
        logger.exception("WebSocket error")
        await ws_manager.disconnect(websocket)


# ── Health check ─────────────────────────────────────────────────────────────


@app.get("/")
async def health_check() -> dict[str, Any]:
    """Root health check.

    Returns:
        Status, version, and live connection counts.
    """
    return {
        "status": "ok",
        "version": "0.1.0",
        "websocket_connections": ws_manager.connection_count,
        "task_subscriptions": ws_manager.subscription_count,
    }
