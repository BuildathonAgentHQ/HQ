"""
backend/app/main.py — FastAPI entry point for Agent HQ.

Wires together all modules: orchestrator, telemetry, control-plane,
knowledge, timeline, real-time WebSocket streaming, Claude intelligence,
repo management, and the agent swarm.

v2: Centralised service instantiation, Claude + GitHub health checks,
    CORS for frontend origin, and full event pipeline.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logging.getLogger("backend").setLevel(logging.INFO)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings
from backend.app.websocket.manager import manager as ws_manager
from backend.app.websocket.events import event_router
from shared.events import EventType, create_ws_event

# ── Service imports ─────────────────────────────────────────────────────────
from backend.app.claude_client.client import ClaudeClient
from backend.app.claude_client.repo_analyzer import RepoAnalyzer
from backend.app.control_plane.github_connector import GitHubConnector
from backend.app.repo_manager.manager import RepoManager
from backend.app.swarm.orchestrator import SwarmOrchestrator

# ── Router imports ──────────────────────────────────────────────────────────
from backend.app.orchestrator.router import router as orchestrator_router
from backend.app.telemetry.metrics_api import router as telemetry_router
from backend.app.control_plane.router import router as control_plane_router
from backend.app.knowledge.router import router as knowledge_router
from backend.app.timeline.router import router as timeline_router
<<<<<<< HEAD
from backend.app.config_router import router as config_router
=======
from backend.app.repo_manager.router import router as repo_manager_router
from backend.app.swarm.router import router as swarm_router
>>>>>>> c29f998 (Latest Update)

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
#  Centralised Service Instances (module-level singletons)
# ═════════════════════════════════════════════════════════════════════════════

claude_client = ClaudeClient(settings)
github_connector = GitHubConnector(settings)
repo_manager = RepoManager(settings, github_connector)
repo_analyzer = RepoAnalyzer(claude_client, repo_manager)
swarm_orchestrator = SwarmOrchestrator(
    claude_client, repo_manager, github_connector, event_router
)


# ═════════════════════════════════════════════════════════════════════════════
#  Lifespan (startup / shutdown)
# ═════════════════════════════════════════════════════════════════════════════


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    Startup:
        - Inject service singletons into ``app.state`` for route access.
        - Test Claude API connectivity (quick "hello" message).
        - Test GitHub API connectivity (list user info).
        - Log Agent HQ v2 startup banner.

    Shutdown:
        - Gracefully close all WebSocket connections.
    """
    # ── Store singletons on app.state for Depends() / direct access ──────
    app.state.claude_client = claude_client
    app.state.github_connector = github_connector
    app.state.repo_manager = repo_manager
    app.state.repo_analyzer = repo_analyzer
    app.state.swarm_orchestrator = swarm_orchestrator

    # ── Health checks ────────────────────────────────────────────────────
    # Claude API
    claude_ok = False
    if settings.USE_CLAUDE_API and settings.ANTHROPIC_API_KEY:
        try:
            result = await claude_client.complete(
                system_prompt="You are a health check assistant.",
                user_message="Respond with exactly: ok",
                max_tokens=16,
            )
            claude_ok = bool(result.get("text"))
            logger.info(
                "✅ Claude API connected — model=%s, tokens=%d",
                settings.CLAUDE_MODEL,
                result.get("input_tokens", 0) + result.get("output_tokens", 0),
            )
        except Exception as exc:
            logger.warning("⚠️  Claude API health check failed: %s", exc)
    else:
        logger.info("ℹ️  Claude API disabled (USE_CLAUDE_API=%s)", settings.USE_CLAUDE_API)

    # GitHub API
    github_ok = False
    if settings.USE_GITHUB and settings.GITHUB_TOKEN:
        try:
            prs = await github_connector.get_open_prs()
            github_ok = True
            logger.info(
                "✅ GitHub API connected — repo=%s, open PRs=%d",
                settings.GITHUB_REPO,
                len(prs) if isinstance(prs, list) else 0,
            )
        except Exception as exc:
            logger.warning("⚠️  GitHub API health check failed: %s", exc)
    else:
        logger.info("ℹ️  GitHub API disabled (USE_GITHUB=%s, mock mode)", settings.USE_GITHUB)

    # ── Banner ───────────────────────────────────────────────────────────
    status_parts = [
        f"Claude={'✅' if claude_ok else '❌'}",
        f"GitHub={'✅' if github_ok else '❌'}",
        f"Swarm=enabled",
    ]
    banner = f"🚀 Agent HQ v2 started — {' | '.join(status_parts)}"
    logger.info(banner)
    print(banner)

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    for ws in list(ws_manager.active_connections):
        try:
            await ws.close()
        except Exception:
            pass
    logger.info("👋 Agent HQ Backend Stopped")


# ═════════════════════════════════════════════════════════════════════════════
#  FastAPI App
# ═════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Agent HQ API",
    description="AI-powered command centre for orchestrating autonomous coding agents",
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS — allow frontend and all origins for development ────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,  # http://localhost:3000
        "http://localhost:3000",
        "http://localhost:3001",
        "*",  # development fallback
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═════════════════════════════════════════════════════════════════════════════
#  REST Route Registrations
# ═════════════════════════════════════════════════════════════════════════════

app.include_router(orchestrator_router,   prefix="/api/tasks",          tags=["tasks"])
app.include_router(telemetry_router,      prefix="/api/metrics",        tags=["metrics"])
app.include_router(control_plane_router,  prefix="/api/control-plane",  tags=["control-plane"])
app.include_router(knowledge_router,      prefix="/api/knowledge",      tags=["knowledge"])
app.include_router(timeline_router,       prefix="/api/timeline",       tags=["timeline"])
<<<<<<< HEAD
app.include_router(config_router,          prefix="/api/config",         tags=["config"])
=======
app.include_router(repo_manager_router,   prefix="/api/repos",          tags=["repos"])
app.include_router(swarm_router,          prefix="/api/swarm",          tags=["swarm"])
>>>>>>> c29f998 (Latest Update)


# ═════════════════════════════════════════════════════════════════════════════
#  Dashboard-specific endpoints (aggregate data for the frontend)
# ═════════════════════════════════════════════════════════════════════════════


@app.get("/api/control-plane/reviews/recent", tags=["control-plane"])
async def recent_reviews() -> list[dict[str, Any]]:
    """Return the most recent PR reviews (up to 10) for the dashboard.

    Reads from the RepoAnalyzer's in-memory review store.
    """
    reviews = list(repo_analyzer.reviews.values())
    # Sort newest first
    reviews.sort(key=lambda r: r.reviewed_at, reverse=True)
    return [r.model_dump(mode="json") for r in reviews[:10]]


# ═════════════════════════════════════════════════════════════════════════════
#  WebSocket endpoint
# ═════════════════════════════════════════════════════════════════════════════


@app.websocket("/ws/activity")
async def websocket_activity(websocket: WebSocket) -> None:
    """Real-time activity streaming via WebSocket."""
    try:
        await ws_manager.connect(websocket)
        logger.info(f"WebSocket {id(websocket)} accepted successfully.")
    except Exception as e:
        logger.error(f"WebSocket connect failed: {e}")
        return

    # Welcome event
    welcome = create_ws_event(
        task_id="system",
        event_type=EventType.TASK_LIFECYCLE,
        payload={
            "message": "Connected to Agent HQ v2",
            "active_connections": ws_manager.connection_count,
            "capabilities": ["swarm", "claude_review", "repo_analysis"],
        },
    )
    try:
        await ws_manager.send_personal(websocket, welcome)
    except Exception as e:
        logger.error(f"WebSocket {id(websocket)} welcome send failed: {e}")
        return

    try:
        while True:
            logger.info(f"WebSocket {id(websocket)} waiting to receive...")
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


# ═════════════════════════════════════════════════════════════════════════════
#  Health check
# ═════════════════════════════════════════════════════════════════════════════


@app.get("/")
async def health_check() -> dict[str, Any]:
    """Root health check.

    Returns:
        Status, version, service states, and live connection counts.
    """
    usage = claude_client.get_usage_stats()
    return {
        "status": "ok",
        "version": "2.0.0",
        "websocket_connections": ws_manager.connection_count,
        "task_subscriptions": ws_manager.subscription_count,
        "services": {
            "claude_api": settings.USE_CLAUDE_API and bool(settings.ANTHROPIC_API_KEY),
            "github_api": settings.USE_GITHUB and bool(settings.GITHUB_TOKEN),
            "swarm": True,
        },
        "claude_usage": {
            "total_input_tokens": usage.get("total_input_tokens", 0),
            "total_output_tokens": usage.get("total_output_tokens", 0),
            "estimated_cost": usage.get("estimated_cost", 0.0),
        },
        "connected_repos": len(repo_manager.repos),
        "active_plans": len(swarm_orchestrator.active_plans),
    }
