"""
backend/tests/conftest.py — Shared pytest fixtures for Agent HQ tests.

Every test module in backend/tests/ can use these fixtures by name.
Fixtures return deterministic objects with known values for assertions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from shared.schemas import (
    ApprovalRequest,
    ContextPayload,
    GuardrailEvent,
    PRRiskFactors,
    PRRiskScore,
    SkillRecipe,
    Task,
    TaskCreate,
    TranslatedEvent,
)
from backend.app.config import Settings


# ═══════════════════════════════════════════════════════════════════════════════
#  Schema fixtures
# ═══════════════════════════════════════════════════════════════════════════════

FIXED_TIME = datetime(2026, 2, 20, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def mock_task() -> Task:
    """A Task with deterministic values for assertions."""
    return Task(
        id="test-task-001",
        task="Add unit tests for the auth module",
        engine="claude-code",
        agent_type="test_writer",
        status="pending",
        budget_limit=2.0,
        budget_used=0.0,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
        exit_code=None,
        token_count=0,
        strike_count=0,
    )


@pytest.fixture
def mock_task_create() -> TaskCreate:
    """A TaskCreate payload for POST /api/tasks/ tests."""
    return TaskCreate(
        task="Refactor the database connection pool",
        engine="claude-code",
        agent_type="refactor",
        budget_limit=1.5,
        context_sources=[],
    )


@pytest.fixture
def mock_translated_event() -> TranslatedEvent:
    """A TranslatedEvent simulating a Nemotron translation."""
    return TranslatedEvent(
        task_id="test-task-001",
        status="Installing project dependencies",
        is_error=False,
        severity="info",
        category="setup",
    )


@pytest.fixture(params=["pass", "fail"])
def mock_guardrail_event(request: pytest.FixtureRequest) -> GuardrailEvent:
    """A GuardrailEvent — parametrised for both pass and fail variants."""
    if request.param == "pass":
        return GuardrailEvent(
            task_id="test-task-001",
            file_path="backend/app/main.py",
            check_type="lint",
            passed=True,
            error_msg="",
            strike_count=0,
            auto_fixed=False,
        )
    return GuardrailEvent(
        task_id="test-task-001",
        file_path="backend/app/main.py",
        check_type="security",
        passed=False,
        error_msg="Hardcoded secret detected in line 42",
        strike_count=1,
        auto_fixed=False,
    )


@pytest.fixture
def mock_approval_request() -> ApprovalRequest:
    """An ApprovalRequest for human-in-the-loop testing."""
    return ApprovalRequest(
        task_id="test-task-001",
        action_type="destructive_cmd",
        command="rm -rf /tmp/test-dir",
        description="The agent wants to delete a temporary directory.",
        options=["Approve", "Reject"],
    )


@pytest.fixture
def mock_context_payload() -> ContextPayload:
    """A ContextPayload with realistic architecture context."""
    return ContextPayload(
        architectural_context="FastAPI backend with SQLAlchemy ORM and PostgreSQL",
        dependencies=["fastapi", "sqlalchemy", "pydantic"],
        relevant_skills=[
            SkillRecipe(
                name="Add API endpoint",
                steps=["Create router", "Define schema", "Wire to main"],
                success_rate=0.92,
                last_used=FIXED_TIME,
            ),
        ],
        business_requirements=[
            "All endpoints must return JSON",
            "Auth required on write operations",
        ],
    )


@pytest.fixture
def mock_pr_score() -> PRRiskScore:
    """A PRRiskScore for control-plane tests."""
    return PRRiskScore(
        pr_id="pr-test-001",
        pr_number=42,
        title="Refactor auth middleware",
        author="dev-alice",
        risk_score=65,
        risk_level="medium",
        factors=PRRiskFactors(
            diff_size=320,
            core_files_changed=True,
            missing_tests=True,
            churn_score=4.2,
            has_dependency_overlap=False,
        ),
        reviewers_suggested=["dev-bob", "dev-carol"],
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Config fixture
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_settings() -> Settings:
    """Settings with all feature flags OFF (mock mode)."""
    return Settings(
        NEMOTRON_API_KEY="",
        NEMOTRON_API_URL="https://integrate.api.nvidia.com/v1",
        NIA_MCP_URL="http://localhost:3001",
        GITHUB_TOKEN="",
        GITHUB_REPO="",
        DATABRICKS_HOST="",
        DATABRICKS_TOKEN="",
        MLFLOW_TRACKING_URI="sqlite:///test_mlruns.db",
        BUDGET_LIMIT_PER_TASK=2.0,
        WS_PORT=8000,
        FRONTEND_URL="http://localhost:3000",
        USE_NEMOTRON=False,
        USE_NIA_MCP=False,
        USE_DATABRICKS=False,
        USE_GITHUB=False,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Service fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def event_router():
    """An EventRouter with a mocked ConnectionManager.

    The ``emit()`` method is an ``AsyncMock`` so tests can assert on it
    without touching real WebSockets.
    """
    from backend.app.websocket.events import EventRouter

    router = EventRouter()
    router.emit = AsyncMock()  # type: ignore[method-assign]
    return router


@pytest.fixture
def task_manager():
    """A TaskManager pre-loaded with 3 sample tasks (no mock seed)."""
    from backend.app.orchestrator.task_manager import TaskManager

    tm = TaskManager(seed_mock=False)
    for i, (prompt, engine) in enumerate(
        [
            ("Write unit tests for auth", "claude-code"),
            ("Refactor database layer", "claude-code"),
            ("Update API documentation", "cursor-cli"),
        ],
        start=1,
    ):
        tm.create_task(
            TaskCreate(
                task=prompt,
                engine=engine,
                agent_type="general",
                budget_limit=2.0,
                context_sources=[],
            )
        )
    return tm


# ═══════════════════════════════════════════════════════════════════════════════
#  HTTP client
# ═══════════════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def async_client():
    """An httpx AsyncClient pointed at the FastAPI test app."""
    from httpx import ASGITransport, AsyncClient

    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
