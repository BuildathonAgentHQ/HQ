"""
shared/mocks/mock_context.py — Hardcoded ContextPayload for development.

Provides ``mock_get_context()`` which returns a realistic ``ContextPayload``
without requiring a live Nia MCP server or knowledge base.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from shared.schemas import ContextPayload, SkillRecipe

_now = datetime.now(timezone.utc)


def mock_get_context(task: str, repo_path: str = ".") -> ContextPayload:
    """Return a hardcoded ContextPayload with realistic architectural context.

    This lets the engine runner inject context into agent prompts during
    development without connecting to a real knowledge base.

    Args:
        task: The natural-language task description.
        repo_path: Path to the target repository (used in the context blurb).

    Returns:
        A ``ContextPayload`` populated with sample data.
    """
    return ContextPayload(
        architectural_context=(
            f"Repository at {repo_path} is a Python/FastAPI monorepo. "
            "The backend lives in backend/app/ with sub-packages for "
            "orchestrator, engine, guardrails, translation, telemetry, "
            "and control_plane.  The frontend is a Next.js 14 app in "
            "frontend/ using TypeScript with the App Router.  Shared "
            "Pydantic schemas live in shared/schemas.py and are the "
            "single source of truth for all data shapes.  The project "
            "uses Ruff for linting, pytest for testing, and follows "
            "conventional commits."
        ),
        dependencies=[
            "fastapi",
            "pydantic",
            "uvicorn",
            "httpx",
            "websockets",
            "ruff",
            "pytest",
            "next",
            "react",
            "typescript",
        ],
        relevant_skills=[
            SkillRecipe(
                name="FastAPI endpoint creation",
                steps=[
                    "Create a new router file in the appropriate sub-package",
                    "Define request/response schemas in shared/schemas.py",
                    "Add the route handler with proper type annotations",
                    "Include the router in backend/app/main.py",
                    "Write tests in tests/ mirroring the module path",
                ],
                success_rate=0.94,
                last_used=_now - timedelta(hours=6),
            ),
            SkillRecipe(
                name="WebSocket event emission",
                steps=[
                    "Import event_router from backend.app.websocket.events",
                    "Build a WebSocketEvent using create_ws_event()",
                    "Call await event_router.emit(event)",
                    "Verify delivery in the frontend WebSocket listener",
                ],
                success_rate=0.91,
                last_used=_now - timedelta(hours=2),
            ),
            SkillRecipe(
                name="Pydantic model extension",
                steps=[
                    "Add the new model to shared/schemas.py",
                    "Mirror the interface in frontend/src/lib/types.ts",
                    "Update mock data in shared/mocks/mock_data.py",
                    "Run validation script to confirm no regressions",
                ],
                success_rate=0.97,
                last_used=_now - timedelta(days=1),
            ),
        ],
        business_requirements=[
            "All destructive commands must pass through human approval",
            "Task budget must not exceed the configured limit without explicit user consent",
            "Agent output must be translated into plain English before reaching the frontend",
            "Three consecutive guardrail failures auto-suspend the task",
            "PR risk scoring must flag any PR touching core auth or payment modules",
        ],
    )
