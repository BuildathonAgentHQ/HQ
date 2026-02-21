"""
shared/schemas.py — THE single source of truth for all data models in Agent HQ.

Every backend module and frontend type definition MUST reference these models.
These schemas are FROZEN after initial approval — no breaking changes without
explicit team sign-off.

Update this file FIRST when changing any data shape.  All other modules import
from here; never re-define these structures locally.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════════
#  1. TaskCreate — Frontend → Backend (POST /api/tasks)
# ═══════════════════════════════════════════════════════════════════════════════


class TaskCreate(BaseModel):
    """Payload the frontend sends to create a new agent task.

    **Produced by:** Frontend task-creation form.
    **Consumed by:** ``backend/app/api/tasks.py`` → ``backend/app/engine/runner.py``.
    """

    task: str = Field(
        ...,
        description="Natural-language description of the work the agent should do.",
    )
    engine: Literal["claude-code", "cursor-cli"] = Field(
        ...,
        description="Which agent engine to dispatch to.",
    )
    agent_type: Literal[
        "general", "test_writer", "refactor", "doc", "reviewer", "release_notes"
    ] = Field(
        "general",
        description="Specialisation preset applied to the agent prompt.",
    )
    budget_limit: float = Field(
        2.0,
        ge=0,
        description="Maximum USD spend for this task before auto-suspend.",
    )
    context_sources: list[str] = Field(
        default_factory=list,
        description="Optional list of knowledge-base document IDs to inject as context.",
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  2. Task — Full server-side task record
# ═══════════════════════════════════════════════════════════════════════════════


class Task(BaseModel):
    """Complete task object stored and managed by the backend.

    **Produced by:** ``backend/app/api/tasks.py`` on creation, updated by
    ``backend/app/engine/runner.py`` during execution.
    **Consumed by:** Every backend module and the frontend task-detail view.
    """

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique task identifier (UUID v4).",
    )
    task: str = Field(
        ...,
        description="Natural-language description copied from TaskCreate.",
    )
    engine: str = Field(
        ...,
        description="Engine name (e.g. 'claude-code', 'cursor-cli').",
    )
    agent_type: str = Field(
        "general",
        description="Specialisation preset for this task.",
    )
    status: Literal["pending", "running", "success", "failed", "suspended"] = Field(
        "pending",
        description="Current lifecycle state.",
    )
    budget_limit: float = Field(2.0, ge=0)
    budget_used: float = Field(
        0.0,
        ge=0,
        description="Cumulative USD spent so far on this task.",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    exit_code: Optional[int] = Field(
        None,
        description="Process exit code once the engine subprocess terminates.",
    )
    token_count: int = Field(0, ge=0, description="Total tokens consumed.")
    strike_count: int = Field(
        0,
        ge=0,
        description="Consecutive Janitor Protocol failures. Three strikes → auto-suspend.",
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  3. RawStreamEvent — Subprocess stdout / stderr capture
# ═══════════════════════════════════════════════════════════════════════════════


class RawStreamEvent(BaseModel):
    """Raw line of output from the agent subprocess, before Nemotron translation.

    **Produced by:** ``backend/app/engine/runner.py`` (stream reader).
    **Consumed by:** ``backend/app/translation/nemotron.py`` for human-readable
    conversion.
    """

    task_id: str
    stream_type: Literal["stdout", "stderr"] = Field(
        ...,
        description="Which file descriptor this output came from.",
    )
    raw_content: str = Field(
        ...,
        description="The raw text exactly as emitted by the subprocess.",
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ═══════════════════════════════════════════════════════════════════════════════
#  4. TranslatedEvent — Nemotron's human-readable interpretation
# ═══════════════════════════════════════════════════════════════════════════════


class TranslatedEvent(BaseModel):
    """Plain-English interpretation of raw agent output, produced by Nemotron.

    **Produced by:** ``backend/app/translation/nemotron.py``.
    **Consumed by:** WebSocket broadcaster → frontend status panel.
    """

    task_id: str
    status: str = Field(
        ...,
        description="One-sentence, non-technical description of what the agent is doing.",
    )
    is_error: bool = Field(
        False,
        description="True if the translated output represents an error condition.",
    )
    severity: Literal["info", "warning", "error"] = Field(
        "info",
        description="Severity bucket for UI colouring / filtering.",
    )
    category: Literal[
        "setup", "coding", "testing", "debugging", "deploying", "waiting", "completed"
    ] = Field(
        "coding",
        description="High-level activity category for timeline grouping.",
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  5. WebSocketEvent — Universal WS envelope to the frontend
# ═══════════════════════════════════════════════════════════════════════════════


class WebSocketEvent(BaseModel):
    """Top-level envelope for every message sent over the WebSocket to the
    frontend.  The ``payload`` dict carries the actual sub-event data (e.g. a
    serialised ``TranslatedEvent`` or ``GuardrailEvent``).

    **Produced by:** ``backend/app/websocket/events.py`` via the
    ``create_ws_event`` helper in ``shared/events.py``.
    **Consumed by:** Frontend WebSocket listener → store dispatcher.
    """

    task_id: str
    event_type: Literal[
        "status_update",
        "error",
        "approval_required",
        "budget_exceeded",
        "debate",
        "guardrail",
        "task_lifecycle",
        "repo_added",
        "repo_analyzed",
        "pr_reviewed",
        "swarm_started",
        "swarm_agent_started",
        "swarm_agent_completed",
        "swarm_completed",
        "fix_proposed",
        "fix_applied",
    ] = Field(..., description="Discriminator for frontend event routing.")
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Serialised sub-event data; shape depends on event_type.",
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ═══════════════════════════════════════════════════════════════════════════════
#  6. GuardrailEvent — Janitor Protocol check result
# ═══════════════════════════════════════════════════════════════════════════════


class GuardrailEvent(BaseModel):
    """Emitted every time the Janitor Protocol runs a guardrail check on
    agent-produced artefacts.

    **Produced by:** ``backend/app/guardrails/janitor.py``.
    **Consumed by:** WebSocket broadcaster → frontend guardrail log panel &
    strike counter.
    """

    task_id: str
    file_path: str = Field(
        ...,
        description="Absolute or repo-relative path to the checked file.",
    )
    check_type: Literal["lint", "security", "destructive_action"] = Field(
        ...,
        description="Category of guardrail check that was executed.",
    )
    passed: bool = Field(
        ...,
        description="Whether the check passed without issues.",
    )
    error_msg: str = Field(
        "",
        description="Human-readable description of the failure (empty when passed).",
    )
    strike_count: int = Field(
        0,
        ge=0,
        description="Cumulative consecutive failures for this task.",
    )
    auto_fixed: bool = Field(
        False,
        description="True if the Janitor was able to auto-remediate the issue.",
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  7. ApprovalRequest — Human-in-the-loop gate
# ═══════════════════════════════════════════════════════════════════════════════


class ApprovalRequest(BaseModel):
    """Sent to the frontend whenever a destructive or contentious action is
    detected and requires explicit human authorisation.

    **Produced by:** ``backend/app/guardrails/janitor.py`` (destructive_cmd),
    ``backend/app/engine/runner.py`` (budget_overrun),
    ``backend/app/engine/debate.py`` (debate_resolution).
    **Consumed by:** Frontend approval modal → ``POST /api/tasks/{id}/approve``.
    """

    task_id: str
    action_type: Literal["destructive_cmd", "budget_overrun", "debate_resolution"] = (
        Field(..., description="Why this approval is being requested.")
    )
    command: Optional[str] = Field(
        None,
        description="The blocked shell command, if action_type is destructive_cmd.",
    )
    description: str = Field(
        ...,
        description="Plain-English explanation of what happened and what is at stake.",
    )
    options: list[str] = Field(
        ...,
        description='Choices presented to the user (e.g. ["Approve", "Reject"]).',
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  8. TelemetryMetrics — Radar chart endpoint payload
# ═══════════════════════════════════════════════════════════════════════════════


class TelemetryMetrics(BaseModel):
    """Normalised 0-100 scores powering the ``/api/metrics/radar`` endpoint.

    **Produced by:** ``backend/app/telemetry/collector.py``.
    **Consumed by:** Frontend radar chart component.
    """

    security: float = Field(
        ..., ge=0, le=100, description="Security posture score."
    )
    stability: float = Field(
        ..., ge=0, le=100, description="CI / test stability score."
    )
    quality: float = Field(
        ..., ge=0, le=100, description="Code quality score (lint, coverage, etc.)."
    )
    speed: float = Field(
        ..., ge=0, le=100, description="Delivery speed score."
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ═══════════════════════════════════════════════════════════════════════════════
#  9. AgentLeaderboardEntry — Efficiency leaderboard row
# ═══════════════════════════════════════════════════════════════════════════════


class AgentLeaderboardEntry(BaseModel):
    """A single row in the agent efficiency leaderboard.

    **Produced by:** ``backend/app/telemetry/collector.py``.
    **Consumed by:** Frontend leaderboard table component.
    """

    engine: str = Field(..., description="Engine identifier (e.g. 'claude-code').")
    tasks_completed: int = Field(0, ge=0)
    success_rate: float = Field(
        0.0, ge=0, le=1, description="Fraction of tasks in 'success' state."
    )
    avg_duration_seconds: float = Field(0.0, ge=0)
    avg_cost_dollars: float = Field(0.0, ge=0)
    total_tokens: int = Field(0, ge=0)


# ═══════════════════════════════════════════════════════════════════════════════
#  10. PRRiskScore — Control Plane PR risk analysis
# ═══════════════════════════════════════════════════════════════════════════════


class PRRiskFactors(BaseModel):
    """Breakdown of individual risk signals contributing to a PR's overall
    risk score.  Nested inside ``PRRiskScore``.

    **Produced by:** ``backend/app/control_plane/pr_analyzer.py``.
    """

    diff_size: int = Field(
        ..., ge=0, description="Total lines added + removed in the PR."
    )
    core_files_changed: bool = Field(
        ..., description="True if the PR touches files in the critical path."
    )
    missing_tests: bool = Field(
        ..., description="True if changed production code lacks accompanying tests."
    )
    churn_score: float = Field(
        ..., ge=0, description="Weighted recent-edit frequency of touched files."
    )
    has_dependency_overlap: bool = Field(
        ...,
        description="True if changed files overlap with another open PR's diff.",
    )


class PRRiskScore(BaseModel):
    """Full risk assessment for a single pull request.

    **Produced by:** ``backend/app/control_plane/pr_analyzer.py``.
    **Consumed by:** Frontend PR-risk panel & ``/api/control-plane/prs`` endpoint.
    """

    pr_id: str = Field(..., description="Internal unique identifier.")
    pr_number: int = Field(..., ge=1, description="GitHub PR number.")
    title: str
    author: str
    risk_score: int = Field(
        ..., ge=0, le=100, description="Composite risk score (0 = safe, 100 = danger)."
    )
    risk_level: Literal["low", "medium", "high", "critical"] = Field(
        ..., description="Bucketed risk classification."
    )
    factors: PRRiskFactors = Field(
        ..., description="Detailed breakdown of risk signals."
    )
    reviewers_suggested: list[str] = Field(
        default_factory=list,
        description="GitHub usernames recommended to review this PR.",
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  11. CoverageReport — Test coverage snapshot
# ═══════════════════════════════════════════════════════════════════════════════


class UntestableDiff(BaseModel):
    """A file diff that lacks test coverage.  Nested inside ``CoverageReport``.

    **Produced by:** ``backend/app/control_plane/coverage.py``.
    """

    file_path: str
    lines_uncovered: int = Field(..., ge=0)
    risk: str = Field(
        ...,
        description="Human-readable risk tag (e.g. 'high — auth module').",
    )


class CoverageReport(BaseModel):
    """Aggregated test-coverage data for the repository.

    **Produced by:** ``backend/app/control_plane/coverage.py``.
    **Consumed by:** Frontend coverage treemap & ``/api/control-plane/coverage``
    endpoint.
    """

    total_coverage_pct: float = Field(
        ..., ge=0, le=100, description="Overall line-coverage percentage."
    )
    module_coverage: dict[str, float] = Field(
        default_factory=dict,
        description="Module name → coverage percentage mapping.",
    )
    untested_diffs: list[UntestableDiff] = Field(
        default_factory=list,
        description="Files with changed-but-untested lines.",
    )
    trend: Literal["improving", "stable", "declining"] = Field(
        "stable",
        description="Direction of coverage change over the last 7 days.",
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  12. RepoHealthReport — Aggregate repository health
# ═══════════════════════════════════════════════════════════════════════════════


class HotFile(BaseModel):
    """A frequently-changed file.  Nested inside ``RepoHealthReport``.

    **Produced by:** ``backend/app/control_plane/health.py``.
    """

    path: str
    change_count_30d: int = Field(
        ..., ge=0, description="Number of commits touching this file in the last 30 days."
    )
    last_changed: datetime


class TechDebtItem(BaseModel):
    """A tracked technical-debt item.  Nested inside ``RepoHealthReport``.

    **Produced by:** ``backend/app/control_plane/health.py``.
    """

    description: str
    age_days: int = Field(..., ge=0)
    severity: str = Field(
        ..., description="e.g. 'low', 'medium', 'high'."
    )


class RepoHealthReport(BaseModel):
    """Overall repository health snapshot.

    **Produced by:** ``backend/app/control_plane/health.py``.
    **Consumed by:** Frontend repo-health dashboard & ``/api/control-plane/health``
    endpoint.
    """

    ci_status: Literal["passing", "failing", "unknown"] = Field(
        "unknown",
        description="Latest CI pipeline result.",
    )
    flaky_tests: list[str] = Field(
        default_factory=list,
        description="Test names that have non-deterministic pass/fail behaviour.",
    )
    hot_files: list[HotFile] = Field(
        default_factory=list,
        description="Files with the highest commit churn in the last 30 days.",
    )
    tech_debt_items: list[TechDebtItem] = Field(
        default_factory=list,
        description="Known tech-debt items ordered by severity.",
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  13. NextBestAction — Recommended action for the user
# ═══════════════════════════════════════════════════════════════════════════════


class NextBestAction(BaseModel):
    """An actionable recommendation surfaced by the control plane.

    **Produced by:** ``backend/app/control_plane/recommender.py``.
    **Consumed by:** Frontend "Next Best Action" card panel.
    """

    action_type: Literal[
        "add_tests", "split_pr", "fix_flaky", "refactor", "update_docs"
    ] = Field(..., description="Category of the recommended action.")
    description: str = Field(
        ..., description="Plain-English explanation of what to do and why."
    )
    target: str = Field(
        ..., description="File path or PR number the action relates to."
    )
    priority: Literal["high", "medium", "low"] = Field(
        "medium", description="Urgency bucket."
    )
    estimated_effort: str = Field(
        ...,
        description="Human-readable effort estimate (e.g. '~30 min', '2-3 hours').",
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  14. ContextPayload — What the context layer feeds to agents
# ═══════════════════════════════════════════════════════════════════════════════


class SkillRecipe(BaseModel):
    """A reusable skill / recipe from the learning layer.
    Nested inside ``ContextPayload``.

    **Produced by:** ``backend/app/context/knowledge_base.py``.
    """

    name: str
    steps: list[str] = Field(
        ..., description="Ordered steps to execute this skill."
    )
    success_rate: float = Field(
        ..., ge=0, le=1, description="Historical success fraction."
    )
    last_used: datetime


class ContextPayload(BaseModel):
    """Bundle of context injected into agent prompts before execution.

    **Produced by:** ``backend/app/context/builder.py``.
    **Consumed by:** ``backend/app/engine/runner.py`` (prompt construction).
    """

    architectural_context: str = Field(
        ...,
        description="High-level summary of the repo's architecture and conventions.",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Key dependency names relevant to the task.",
    )
    relevant_skills: list[SkillRecipe] = Field(
        default_factory=list,
        description="Previously-learned skill recipes that may apply.",
    )
    business_requirements: list[str] = Field(
        default_factory=list,
        description="Extracted business constraints / requirements for the task.",
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  15. DebateResult — Multi-agent disagreement resolution
# ═══════════════════════════════════════════════════════════════════════════════


class DebateOption(BaseModel):
    """A single option surfaced during a multi-agent debate.
    Nested inside ``DebateResult``.

    **Produced by:** ``backend/app/engine/debate.py``.
    """

    label: str = Field(..., description="Short label, e.g. 'Option A'.")
    description: str = Field(
        ..., description="Detailed explanation of this option."
    )
    recommended_by: str = Field(
        ..., description="Agent identifier that recommended this option."
    )


class DebateResult(BaseModel):
    """Summary of a multi-agent debate when agents disagree on approach.

    **Produced by:** ``backend/app/engine/debate.py`` after Nemotron mediation.
    **Consumed by:** Frontend debate resolution modal & approval flow.
    """

    task_id: str
    agent_a_position: str = Field(
        ..., description="Summary of agent A's proposed approach."
    )
    agent_b_position: str = Field(
        ..., description="Summary of agent B's proposed approach."
    )
    summary: str = Field(
        ...,
        description="Plain-English comparison produced by Nemotron.",
    )
    options: list[DebateOption] = Field(
        ..., description="Actionable options for the user to choose from."
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  16. Repository — A connected GitHub repository
# ═══════════════════════════════════════════════════════════════════════════════


class Repository(BaseModel):
    """A GitHub repository connected to Agent HQ for analysis and monitoring.

    **Produced by:** ``backend/app/api/repos.py`` on connection.
    **Consumed by:** Swarm agents, control plane, frontend repo list.
    """

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier (UUID v4).",
    )
    owner: str = Field(..., description="GitHub owner (user or org).")
    name: str = Field(..., description="Repository name.")
    full_name: str = Field(..., description="owner/name format.")
    url: str = Field(..., description="GitHub URL.")
    default_branch: str = Field("main", description="Default branch name.")
    added_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this repo was connected to Agent HQ.",
    )
    last_analyzed: Optional[datetime] = Field(
        None, description="Timestamp of the most recent Claude analysis."
    )
    analysis_summary: Optional[str] = Field(
        None, description="Plain-English summary from Claude's analysis."
    )
    tech_stack: list[str] = Field(
        default_factory=list, description="Detected technologies."
    )
    health_score: Optional[int] = Field(
        None, ge=0, le=100, description="Overall repo health score (0-100)."
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  17. CodeIssue — A single issue found by Claude analysis
# ═══════════════════════════════════════════════════════════════════════════════


class CodeIssue(BaseModel):
    """A code issue discovered by Claude during repo or PR analysis.

    **Produced by:** Swarm reviewer/security_auditor agents.
    **Consumed by:** Fix generator agent, frontend issue list.
    """

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier (UUID v4).",
    )
    repo_id: str = Field(..., description="ID of the repository this belongs to.")
    pr_number: Optional[int] = Field(
        None,
        description="GitHub PR number (null for repo-level issues).",
    )
    file_path: str = Field(..., description="Path to the affected file.")
    line_number: Optional[int] = Field(
        None, description="Specific line number, if applicable."
    )
    issue_type: Literal[
        "bug",
        "security",
        "performance",
        "error_handling",
        "testing",
        "style",
        "breaking",
        "refactor",
    ] = Field(..., description="Category of the issue.")
    severity: Literal["critical", "high", "medium", "low"] = Field(
        ..., description="How severe this issue is."
    )
    description: str = Field(
        ..., description="Plain-English description of the issue."
    )
    suggestion: str = Field(..., description="How to fix the issue.")
    status: Literal["open", "fixing", "fixed", "dismissed"] = Field(
        "open", description="Current lifecycle state of the issue."
    )
    assigned_agent: Optional[str] = Field(
        None, description="Which swarm agent is working on this issue."
    )
    fix_pr_url: Optional[str] = Field(
        None, description="Link to the PR containing the fix."
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  18. FixProposal — A proposed code fix from a swarm agent
# ═══════════════════════════════════════════════════════════════════════════════


class FixProposal(BaseModel):
    """A concrete code fix proposed by a swarm agent.

    **Produced by:** Fix generator / refactor agents.
    **Consumed by:** Approval gate → auto-apply or human review.
    """

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier (UUID v4).",
    )
    issue_id: str = Field(
        ..., description="ID of the CodeIssue this fix addresses."
    )
    repo_id: str = Field(..., description="ID of the repository.")
    agent_type: str = Field(
        ..., description="Which swarm agent generated this fix."
    )
    file_path: str = Field(..., description="Path to the file being modified.")
    original_code: str = Field(
        ..., description="Exact code segment to replace."
    )
    fixed_code: str = Field(
        ..., description="Corrected code segment."
    )
    explanation: str = Field(
        ..., description="Plain-English explanation of the fix."
    )
    test_code: Optional[str] = Field(
        None, description="Test code to verify the fix, if applicable."
    )
    status: Literal["proposed", "approved", "applied", "rejected"] = Field(
        "proposed", description="Current lifecycle state of the proposal."
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this fix was proposed.",
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  19. SwarmTask — A unit of work for the agent swarm
# ═══════════════════════════════════════════════════════════════════════════════


class SwarmTask(BaseModel):
    """A single task assigned to one swarm agent.

    **Produced by:** Swarm coordinator agent.
    **Consumed by:** Individual specialist agents.
    """

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier (UUID v4).",
    )
    repo_id: str = Field(..., description="ID of the repository.")
    pr_number: Optional[int] = Field(
        None, description="GitHub PR number (null for repo-level tasks)."
    )
    agent_type: Literal[
        "coordinator",
        "reviewer",
        "test_writer",
        "refactor",
        "security_auditor",
        "doc_writer",
        "fix_generator",
    ] = Field(..., description="Which specialist agent handles this task.")
    task_description: str = Field(
        ..., description="What this agent should do."
    )
    target_files: list[str] = Field(
        default_factory=list, description="Files to work on."
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="List of SwarmTask IDs this depends on.",
    )
    status: Literal["pending", "running", "success", "failed"] = Field(
        "pending", description="Current execution state."
    )
    result: Optional[dict] = Field(
        None, description="The agent's JSON response."
    )
    tokens_used: int = Field(0, ge=0, description="Tokens consumed.")
    cost: float = Field(0.0, ge=0, description="Estimated USD cost.")
    started_at: Optional[datetime] = Field(
        None, description="When execution began."
    )
    completed_at: Optional[datetime] = Field(
        None, description="When execution finished."
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  20. SwarmPlan — Execution plan for a swarm operation
# ═══════════════════════════════════════════════════════════════════════════════


class SwarmPlan(BaseModel):
    """A coordinated execution plan for multiple swarm agents.

    **Produced by:** Swarm coordinator agent.
    **Consumed by:** Swarm executor, frontend plan view.
    """

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier (UUID v4).",
    )
    repo_id: str = Field(..., description="ID of the repository.")
    pr_number: Optional[int] = Field(
        None, description="GitHub PR number (null for repo-level plans)."
    )
    trigger: Literal["pr_review", "repo_audit", "fix_issues", "manual"] = Field(
        ..., description="What triggered this swarm operation."
    )
    plan_summary: str = Field(
        ..., description="Brief description of the overall strategy."
    )
    tasks: list[SwarmTask] = Field(
        default_factory=list, description="Ordered list of agent tasks."
    )
    status: Literal["planning", "executing", "completed", "failed"] = Field(
        "planning", description="Current plan lifecycle state."
    )
    total_issues_found: int = Field(0, ge=0)
    total_fixes_proposed: int = Field(0, ge=0)
    total_fixes_applied: int = Field(0, ge=0)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this plan was created.",
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  21. PRReview — Enhanced PR review from Claude
# ═══════════════════════════════════════════════════════════════════════════════


class PRReview(BaseModel):
    """Comprehensive PR review powered by Claude, replacing heuristic-only
    risk scoring with deep code understanding.

    **Produced by:** PR reviewer swarm agent.
    **Consumed by:** Frontend PR review view, approval flow.
    """

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier (UUID v4).",
    )
    repo_id: str = Field(..., description="ID of the repository.")
    pr_number: int = Field(..., ge=1, description="GitHub PR number.")
    pr_title: str = Field(..., description="Title of the pull request.")
    pr_author: str = Field(..., description="Author's GitHub username.")
    summary: str = Field(
        ..., description="Claude's summary of what the PR does."
    )
    risk_level: Literal["low", "medium", "high", "critical"] = Field(
        ..., description="Overall risk classification."
    )
    verdict: Literal["approve", "request_changes", "needs_discussion"] = Field(
        ..., description="Review verdict."
    )
    issues: list[CodeIssue] = Field(
        default_factory=list, description="Issues found in this PR."
    )
    missing_tests: list[dict] = Field(
        default_factory=list,
        description="Files/areas that need test coverage (file + description).",
    )
    praise: list[str] = Field(
        default_factory=list, description="Things done well in this PR."
    )
    fix_plan: Optional[SwarmPlan] = Field(
        None, description="Auto-generated plan to fix all issues found."
    )
    reviewed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the review was completed.",
    )

