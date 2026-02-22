"""
shared/mocks/mock_data.py — Canonical sample data for every schema type.

Used by the mock WebSocket/REST server and by tests.  Every teammate
can build and test against this data independently.

IMPORTANT: All data here uses the FROZEN schemas from ``shared/schemas.py``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from shared.schemas import (
    AgentLeaderboardEntry,
    CoverageReport,
    HotFile,
    NextBestAction,
    PRFeatureCoverage,
    PRRiskFactors,
    PRRiskScore,
    RepoHealthReport,
    Task,
    TechDebtItem,
    TelemetryMetrics,
    TranslatedEvent,
    UntestableDiff,
)

_now = datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════════════════
#  SAMPLE_TASKS — 5 tasks in various lifecycle states
# ═══════════════════════════════════════════════════════════════════════════════

SAMPLE_TASKS: list[Task] = [
    Task(
        id="task-001",
        task="Add JWT authentication middleware to the FastAPI backend",
        engine="claude-code",
        agent_type="general",
        status="running",
        budget_limit=2.0,
        budget_used=0.73,
        created_at=_now - timedelta(minutes=12),
        updated_at=_now - timedelta(seconds=30),
        token_count=14_320,
        strike_count=0,
    ),
    Task(
        id="task-002",
        task="Write comprehensive unit tests for the payment module",
        engine="cursor-cli",
        agent_type="test_writer",
        status="success",
        budget_limit=1.5,
        budget_used=1.12,
        created_at=_now - timedelta(hours=2),
        updated_at=_now - timedelta(hours=1, minutes=40),
        exit_code=0,
        token_count=28_450,
        strike_count=0,
    ),
    Task(
        id="task-003",
        task="Refactor database connection pooling for async support",
        engine="claude-code",
        agent_type="refactor",
        status="failed",
        budget_limit=2.0,
        budget_used=1.98,
        created_at=_now - timedelta(hours=5),
        updated_at=_now - timedelta(hours=4, minutes=10),
        exit_code=1,
        token_count=41_200,
        strike_count=3,
    ),
    Task(
        id="task-004",
        task="Generate API documentation for all REST endpoints",
        engine="claude-code",
        agent_type="doc",
        status="pending",
        budget_limit=1.0,
        budget_used=0.0,
        created_at=_now - timedelta(minutes=2),
        updated_at=_now - timedelta(minutes=2),
        token_count=0,
        strike_count=0,
    ),
    Task(
        id="task-005",
        task="Review PR #47 for security vulnerabilities and code quality",
        engine="cursor-cli",
        agent_type="reviewer",
        status="suspended",
        budget_limit=2.0,
        budget_used=2.01,
        created_at=_now - timedelta(hours=1),
        updated_at=_now - timedelta(minutes=45),
        token_count=35_800,
        strike_count=1,
    ),
    Task(
        id="task-006",
        task="Generate integration tests for the OAuth2 login flow",
        engine="gemini-cli",
        agent_type="test_writer",
        status="success",
        budget_limit=1.5,
        budget_used=0.42,
        created_at=_now - timedelta(hours=2),
        updated_at=_now - timedelta(hours=1, minutes=30),
        token_count=28_500,
        strike_count=0,
    ),
    Task(
        id="task-007",
        task="Refactor the event bus to use typed channels",
        engine="codex",
        agent_type="refactor",
        status="running",
        budget_limit=3.0,
        budget_used=0.73,
        created_at=_now - timedelta(minutes=20),
        updated_at=_now - timedelta(minutes=5),
        token_count=19_200,
        strike_count=0,
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
#  SAMPLE_TRANSLATED_EVENTS — 20 events simulating a full agent run lifecycle
#  setup → coding → error → debugging → fix → testing → success
# ═══════════════════════════════════════════════════════════════════════════════

SAMPLE_TRANSLATED_EVENTS: list[TranslatedEvent] = [
    # — Setup phase (1-4) —
    TranslatedEvent(
        task_id="task-001", status="Agent is initialising the workspace and reading project config",
        is_error=False, severity="info", category="setup",
    ),
    TranslatedEvent(
        task_id="task-001", status="Agent is installing project dependencies via npm install",
        is_error=False, severity="info", category="setup",
    ),
    TranslatedEvent(
        task_id="task-001", status="Agent is analysing the existing project structure",
        is_error=False, severity="info", category="setup",
    ),
    TranslatedEvent(
        task_id="task-001", status="Agent has identified 42 Python files and 3 config files",
        is_error=False, severity="info", category="setup",
    ),
    # — Coding phase (5-8) —
    TranslatedEvent(
        task_id="task-001", status="Agent is creating auth/models.py with User and Token schemas",
        is_error=False, severity="info", category="coding",
    ),
    TranslatedEvent(
        task_id="task-001", status="Agent is writing the JWT token verification middleware",
        is_error=False, severity="info", category="coding",
    ),
    TranslatedEvent(
        task_id="task-001", status="Agent is adding login and registration endpoints",
        is_error=False, severity="info", category="coding",
    ),
    TranslatedEvent(
        task_id="task-001", status="Agent is updating the main router to include auth routes",
        is_error=False, severity="info", category="coding",
    ),
    # — Error phase (9-10) —
    TranslatedEvent(
        task_id="task-001", status="Agent encountered an import error in auth/middleware.py",
        is_error=True, severity="error", category="debugging",
    ),
    TranslatedEvent(
        task_id="task-001", status="Agent is investigating a circular import between auth and core modules",
        is_error=True, severity="warning", category="debugging",
    ),
    # — Fix phase (11-13) —
    TranslatedEvent(
        task_id="task-001", status="Agent is refactoring imports to break the circular dependency",
        is_error=False, severity="info", category="coding",
    ),
    TranslatedEvent(
        task_id="task-001", status="Agent has resolved the import error and verified the fix",
        is_error=False, severity="info", category="coding",
    ),
    TranslatedEvent(
        task_id="task-001", status="Agent is adding password hashing with bcrypt",
        is_error=False, severity="info", category="coding",
    ),
    # — Testing phase (14-18) —
    TranslatedEvent(
        task_id="task-001", status="Agent is writing test cases for the auth module",
        is_error=False, severity="info", category="testing",
    ),
    TranslatedEvent(
        task_id="task-001", status="Agent is running pytest on tests/test_auth.py",
        is_error=False, severity="info", category="testing",
    ),
    TranslatedEvent(
        task_id="task-001", status="2 of 8 tests failed — fixing assertion in test_token_expiry",
        is_error=True, severity="warning", category="testing",
    ),
    TranslatedEvent(
        task_id="task-001", status="Agent fixed the failing tests and is re-running the suite",
        is_error=False, severity="info", category="testing",
    ),
    TranslatedEvent(
        task_id="task-001", status="All 8 tests passing — full auth test suite green",
        is_error=False, severity="info", category="testing",
    ),
    # — Completion (19-20) —
    TranslatedEvent(
        task_id="task-001", status="Agent is cleaning up temporary files and formatting code",
        is_error=False, severity="info", category="coding",
    ),
    TranslatedEvent(
        task_id="task-001", status="Task completed successfully — JWT auth middleware is ready",
        is_error=False, severity="info", category="completed",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
#  SAMPLE_PR_SCORES — 5 PRs with varying risk levels
# ═══════════════════════════════════════════════════════════════════════════════

SAMPLE_PR_SCORES: list[PRRiskScore] = [
    PRRiskScore(
        pr_id="pr-101", pr_number=101,
        title="feat: add OAuth2 provider support",
        author="alice",
        risk_score=42, risk_level="medium",
        factors=PRRiskFactors(
            diff_size=280, core_files_changed=True, missing_tests=False,
            churn_score=8.5, has_dependency_overlap=False,
        ),
        reviewers_suggested=["bob", "charlie"],
    ),
    PRRiskScore(
        pr_id="pr-102", pr_number=102,
        title="fix: patch SQL injection vulnerability in user search",
        author="bob",
        risk_score=85, risk_level="critical",
        factors=PRRiskFactors(
            diff_size=45, core_files_changed=True, missing_tests=False,
            churn_score=22.0, has_dependency_overlap=True,
        ),
        reviewers_suggested=["alice", "security-team"],
    ),
    PRRiskScore(
        pr_id="pr-103", pr_number=103,
        title="chore: update eslint and prettier configs",
        author="dependabot",
        risk_score=8, risk_level="low",
        factors=PRRiskFactors(
            diff_size=120, core_files_changed=False, missing_tests=True,
            churn_score=1.2, has_dependency_overlap=False,
        ),
        reviewers_suggested=["charlie"],
    ),
    PRRiskScore(
        pr_id="pr-104", pr_number=104,
        title="feat: add real-time collaboration cursors",
        author="charlie",
        risk_score=67, risk_level="high",
        factors=PRRiskFactors(
            diff_size=620, core_files_changed=True, missing_tests=True,
            churn_score=15.3, has_dependency_overlap=True,
        ),
        reviewers_suggested=["alice", "bob"],
    ),
    PRRiskScore(
        pr_id="pr-105", pr_number=105,
        title="docs: update README with deployment instructions",
        author="diana",
        risk_score=3, risk_level="low",
        factors=PRRiskFactors(
            diff_size=35, core_files_changed=False, missing_tests=False,
            churn_score=0.5, has_dependency_overlap=False,
        ),
        reviewers_suggested=["bob"],
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
#  SAMPLE_COVERAGE — Realistic test coverage report
# ═══════════════════════════════════════════════════════════════════════════════

SAMPLE_COVERAGE = CoverageReport(
    total_coverage_pct=74.6,
    module_coverage={
        "backend.app.orchestrator": 82.3,
        "backend.app.engine": 68.1,
        "backend.app.guardrails": 91.0,
        "backend.app.translation": 55.4,
        "backend.app.telemetry": 77.8,
        "backend.app.control_plane": 63.2,
        "backend.app.websocket": 88.5,
        "shared": 95.0,
    },
    untested_diffs=[
        UntestableDiff(file_path="backend/app/engine/runner.py", lines_uncovered=34, risk="high — core execution path"),
        UntestableDiff(file_path="backend/app/translation/nemotron.py", lines_uncovered=22, risk="medium — API integration"),
        UntestableDiff(file_path="backend/app/control_plane/pr_analyzer.py", lines_uncovered=18, risk="medium — risk scoring"),
    ],
    trend="improving",
    pr_features=[
        PRFeatureCoverage(pr_number=101, title="feat: add OAuth2 [open]", author="alice", source_files=2, test_files=1, has_tests=True, coverage_status="covered"),
        PRFeatureCoverage(pr_number=102, title="fix: SQL injection [open]", author="bob", source_files=1, test_files=1, has_tests=True, coverage_status="covered"),
        PRFeatureCoverage(pr_number=103, title="chore: eslint config [open]", author="dependabot", source_files=2, test_files=0, has_tests=False, coverage_status="uncovered"),
    ],
    total_prs=3,
    prs_with_tests=2,
    lines_covered=420,
    lines_total=560,
    line_coverage_pct=75.0,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  SAMPLE_REPO_HEALTH — Repository health snapshot
# ═══════════════════════════════════════════════════════════════════════════════

SAMPLE_REPO_HEALTH = RepoHealthReport(
    ci_status="passing",
    flaky_tests=[
        "tests/test_auth.py::test_login_timeout",
        "tests/test_ws.py::test_reconnect_under_load",
        "tests/test_engine.py::test_concurrent_task_limit",
    ],
    hot_files=[
        HotFile(path="backend/app/engine/runner.py", change_count_30d=28, last_changed=_now - timedelta(hours=3)),
        HotFile(path="backend/app/websocket/manager.py", change_count_30d=19, last_changed=_now - timedelta(hours=6)),
        HotFile(path="shared/schemas.py", change_count_30d=15, last_changed=_now - timedelta(days=1)),
        HotFile(path="frontend/src/lib/types.ts", change_count_30d=14, last_changed=_now - timedelta(days=1)),
    ],
    tech_debt_items=[
        TechDebtItem(description="Replace polling with SSE for metrics endpoint", age_days=45, severity="medium"),
        TechDebtItem(description="Migrate from synchronous file I/O to async in guardrails", age_days=30, severity="high"),
        TechDebtItem(description="Remove deprecated TaskSummary references", age_days=12, severity="low"),
    ],
)


# ═══════════════════════════════════════════════════════════════════════════════
#  SAMPLE_RADAR_METRICS — Telemetry radar chart data
# ═══════════════════════════════════════════════════════════════════════════════

SAMPLE_RADAR_METRICS = TelemetryMetrics(
    security=82.0,
    stability=91.0,
    quality=76.5,
    speed=68.0,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  SAMPLE_LEADERBOARD — 4 agent engine rankings
# ═══════════════════════════════════════════════════════════════════════════════

SAMPLE_LEADERBOARD: list[AgentLeaderboardEntry] = [
    AgentLeaderboardEntry(
        engine="claude-code",
        tasks_completed=47,
        success_rate=0.93,
        avg_duration_seconds=185.0,
        avg_cost_dollars=0.48,
        total_tokens=1_240_000,
    ),
    AgentLeaderboardEntry(
        engine="cursor-cli",
        tasks_completed=31,
        success_rate=0.87,
        avg_duration_seconds=220.0,
        avg_cost_dollars=0.35,
        total_tokens=890_000,
    ),
    AgentLeaderboardEntry(
        engine="gemini-cli",
        tasks_completed=22,
        success_rate=0.82,
        avg_duration_seconds=260.0,
        avg_cost_dollars=0.31,
        total_tokens=640_000,
    ),
    AgentLeaderboardEntry(
        engine="codex",
        tasks_completed=15,
        success_rate=0.80,
        avg_duration_seconds=290.0,
        avg_cost_dollars=0.40,
        total_tokens=480_000,
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
#  SAMPLE_ACTIONS — 5 Next Best Action recommendations
# ═══════════════════════════════════════════════════════════════════════════════

SAMPLE_ACTIONS: list[NextBestAction] = [
    NextBestAction(
        action_type="fix_flaky",
        description="test_login_timeout has failed 3 times this week — likely a race condition in the auth token refresh",
        target="tests/test_auth.py",
        priority="high",
        estimated_effort="~30 min",
    ),
    NextBestAction(
        action_type="add_tests",
        description="backend/app/engine/runner.py has 34 uncovered lines on the core execution path",
        target="backend/app/engine/runner.py",
        priority="high",
        estimated_effort="~2 hours",
    ),
    NextBestAction(
        action_type="split_pr",
        description="PR #104 touches 620 lines across core files — consider splitting auth and collab changes",
        target="104",
        priority="medium",
        estimated_effort="~1 hour",
    ),
    NextBestAction(
        action_type="refactor",
        description="Migrate synchronous file I/O in guardrails module to async for better concurrency",
        target="backend/app/guardrails/",
        priority="medium",
        estimated_effort="~3 hours",
    ),
    NextBestAction(
        action_type="update_docs",
        description="API endpoint documentation is stale — 4 new endpoints added since last update",
        target="docs/api.md",
        priority="low",
        estimated_effort="~45 min",
    ),
]
