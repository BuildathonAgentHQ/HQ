"""
backend/app/swarm/router.py — FastAPI endpoints for the agent swarm.

Mounted at ``/api/swarm`` in ``main.py``.  Exposes plan creation,
execution, fix application, and issue management.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from backend.app.claude_client.client import ClaudeClient
from backend.app.claude_client.repo_analyzer import RepoAnalyzer
from backend.app.config import settings
from backend.app.control_plane.github_connector import GitHubConnector
from backend.app.repo_manager.manager import RepoManager
from backend.app.swarm.orchestrator import SwarmOrchestrator
from backend.app.websocket.events import event_router
from shared.schemas import CodeIssue, FixProposal, SwarmPlan

logger = logging.getLogger(__name__)

router = APIRouter()



# ── Request / response models ───────────────────────────────────────────────


class CreatePlanRequest(BaseModel):
    repo_id: str
    pr_number: Optional[int] = None
    mode: Literal["pr_review", "repo_audit", "fix_issues"] = "pr_review"


class ApplyFixesRequest(BaseModel):
    fix_ids: list[str]


class UpdateIssueRequest(BaseModel):
    status: Literal["open", "fixing", "fixed", "dismissed"]


class DispatchAgentRequest(BaseModel):
    """One-shot request: describe the action and we plan → execute → PR."""
    action_type: str
    description: str
    target: str
    repo_id: Optional[str] = None
    engine: Optional[str] = "claude-code"


# ═════════════════════════════════════════════════════════════════════════════
#  Dispatch — one-shot plan + execute + PR
# ═════════════════════════════════════════════════════════════════════════════


@router.post("/dispatch", response_model=dict[str, Any])
async def dispatch_agent(request: Request, body: DispatchAgentRequest) -> dict[str, Any]:
    """One-click dispatch: creates a swarm plan, executes it, applies fixes, and opens a PR.

    This is the endpoint behind the "Dispatch Agent" button on the Repo Health
    and Coverage Map pages.  It runs the full pipeline asynchronously and
    returns immediately with a tracking plan_id.
    """
    orchestrator: SwarmOrchestrator = request.app.state.swarm_orchestrator
    repo_manager: RepoManager = request.app.state.repo_manager

    repo_id = body.repo_id
    if not repo_id:
        repos = await repo_manager.list_repos()
        if not repos:
            raise HTTPException(400, "No repositories connected. Connect one first on the Repositories page.")
        repo_id = repos[0].id

    agent_type_map = {
        "add_tests": "test_writer",
        "fix_flaky": "test_writer",
        "refactor": "refactor",
        "update_docs": "doc_writer",
        "split_pr": "fix_generator",
    }

    agent_type = agent_type_map.get(body.action_type, "fix_generator")

    issue = CodeIssue(
        repo_id=repo_id,
        file_path=body.target,
        issue_type="testing" if "test" in body.action_type else "refactor",
        severity="high" if body.action_type in ("fix_flaky", "add_tests") else "medium",
        description=body.description,
        suggestion=f"Auto-fix via {agent_type} agent",
    )

    plan = await orchestrator.plan_fix(repo_id, [issue])

    engine = body.engine or "claude-code"

    if plan.tasks:
        for t in plan.tasks:
            t.agent_type = agent_type
            t.engine = engine

    async def _run_pipeline() -> None:
        try:
            await orchestrator.execute_plan(plan.id)
            fix_ids = [
                fp.id for fp in orchestrator.fix_proposals.values()
                if fp.repo_id == repo_id and fp.status == "proposed"
            ]
            if fix_ids:
                result = await orchestrator.apply_fixes(plan.id, fix_ids)
                logger.info("Dispatch auto-PR created: %s", result.get("pr_url", "none"))
            else:
                logger.info("Dispatch completed for plan %s but no fixes proposed", plan.id)
        except Exception:
            logger.exception("Dispatch pipeline failed for plan %s", plan.id)

    asyncio.create_task(_run_pipeline())

    return {
        "plan_id": plan.id,
        "status": "dispatched",
        "agent_type": agent_type,
        "engine": engine,
        "message": f"Agent dispatched via {engine}. Plan has {len(plan.tasks)} task(s). "
                   "A PR will be created automatically when the agent finishes.",
    }


# ═════════════════════════════════════════════════════════════════════════════
#  Plan CRUD
# ═════════════════════════════════════════════════════════════════════════════


@router.post("/plan", response_model=dict[str, Any])
async def create_plan(request: Request, body: CreatePlanRequest) -> dict[str, Any]:
    """Create an execution plan based on the selected mode.

    Modes:
        - ``pr_review``:  Analyze the PR → find issues → build fix plan.
        - ``repo_audit``: Analyze the full repo → find issues → build fix plan.
        - ``fix_issues``: Use already-discovered issues → build fix plan.
    """
    orchestrator = request.app.state.swarm_orchestrator
    analyzer = request.app.state.repo_analyzer

    issues: list[CodeIssue] = []

    if body.mode == "pr_review":
        if body.pr_number is None:
            raise HTTPException(400, "pr_number is required for pr_review mode")
        review = await analyzer.analyze_pr(body.repo_id, body.pr_number)
        issues = review.issues

    elif body.mode == "repo_audit":
        result = await analyzer.analyze_repo(body.repo_id)
        # Collect issues stored by the analyzer
        issues = [
            i for i in analyzer.issues.values()
            if i.repo_id == body.repo_id
        ]

    elif body.mode == "fix_issues":
        # Use existing issues already discovered
        issues = [
            i for i in analyzer.issues.values()
            if i.repo_id == body.repo_id and i.status == "open"
        ]

    if not issues:
        return {
            "plan": None,
            "message": "No issues found to fix.",
            "issues_count": 0,
        }

    plan = await orchestrator.plan_fix(
        body.repo_id, issues, pr_number=body.pr_number
    )

    return {
        "plan": plan.model_dump(mode="json"),
        "issues_count": len(issues),
        "message": f"Plan created with {len(plan.tasks)} tasks for {len(issues)} issues.",
    }


@router.get("/plans", response_model=list[dict[str, Any]])
async def list_plans(request: Request) -> list[dict[str, Any]]:
    """List all swarm plans."""
    orchestrator = request.app.state.swarm_orchestrator
    return [
        p.model_dump(mode="json")
        for p in orchestrator.active_plans.values()
    ]



@router.get("/plans/active", response_model=list[dict[str, Any]])
async def active_swarm_plans(request: Request) -> list[dict[str, Any]]:
    """Return currently active (executing or recently completed) swarm plans.
    Used by the dashboard's Active Swarms widget.
    """
    orchestrator = request.app.state.swarm_orchestrator
    plans = list(orchestrator.active_plans.values())
    # Show executing first, then completed (most recent), up to 5
    plans.sort(
        key=lambda p: (
            0 if p.status == "executing" else 1,
            p.created_at,
        ),
        reverse=True,
    )
    return [p.model_dump(mode="json") for p in plans[:5]]

@router.get("/plans/{plan_id}", response_model=dict[str, Any])
async def get_plan(request: Request, plan_id: str) -> dict[str, Any]:
    """Get a specific swarm plan by ID."""
    orchestrator = request.app.state.swarm_orchestrator
    plan = orchestrator.active_plans.get(plan_id)
    if plan is None:
        raise HTTPException(404, f"Plan not found: {plan_id}")
    return plan.model_dump(mode="json")


# ═════════════════════════════════════════════════════════════════════════════
#  Execution
# ═════════════════════════════════════════════════════════════════════════════


@router.post("/plans/{plan_id}/execute", response_model=dict[str, Any])
async def execute_plan(request: Request, plan_id: str) -> dict[str, Any]:
    """Start executing a swarm plan.

    Returns immediately; progress is streamed via WebSocket events
    (``swarm_started``, ``swarm_agent_started/completed``,
    ``swarm_completed``).
    """
    orchestrator = request.app.state.swarm_orchestrator
    plan = orchestrator.active_plans.get(plan_id)
    if plan is None:
        raise HTTPException(404, f"Plan not found: {plan_id}")

    if plan.status != "planning":
        raise HTTPException(
            409,
            f"Plan is already in '{plan.status}' state; "
            f"only 'planning' plans can be executed.",
        )

    # Fire-and-forget — execution runs in background
    asyncio.create_task(orchestrator.execute_plan(plan_id))

    return {
        "plan_id": plan_id,
        "status": "executing",
        "message": f"Execution started for {len(plan.tasks)} tasks. "
                   f"Watch WebSocket for progress.",
    }


# ═════════════════════════════════════════════════════════════════════════════
#  Fixes
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/plans/{plan_id}/fixes", response_model=list[dict[str, Any]])
async def get_fixes(request: Request, plan_id: str) -> list[dict[str, Any]]:
    """List all fix proposals generated by a plan."""
    orchestrator = request.app.state.swarm_orchestrator
    plan = orchestrator.active_plans.get(plan_id)
    if plan is None:
        raise HTTPException(404, f"Plan not found: {plan_id}")

    fixes = [
        fp.model_dump(mode="json")
        for fp in orchestrator.fix_proposals.values()
        if fp.repo_id == plan.repo_id
    ]
    return fixes


@router.post("/plans/{plan_id}/apply", response_model=dict[str, Any])
async def apply_fixes(request: Request, plan_id: str, body: ApplyFixesRequest) -> dict[str, Any]:
    """Apply selected fixes to the repo via GitHub API.

    Creates a branch with the changes and opens a PR.
    """
    orchestrator = request.app.state.swarm_orchestrator
    try:
        result = await orchestrator.apply_fixes(plan_id, body.fix_ids)
        return result
    except KeyError:
        raise HTTPException(404, f"Plan not found: {plan_id}")


@router.post("/plans/{plan_id}/apply-all", response_model=dict[str, Any])
async def apply_all_fixes(request: Request, plan_id: str) -> dict[str, Any]:
    """Apply ALL proposed fixes from a plan — the "Fix Everything" button."""
    orchestrator = request.app.state.swarm_orchestrator
    try:
        result = await orchestrator.apply_all_fixes(plan_id)
        return result
    except KeyError:
        raise HTTPException(404, f"Plan not found: {plan_id}")


# ═════════════════════════════════════════════════════════════════════════════
#  Issues
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/issues", response_model=list[dict[str, Any]])
async def get_all_issues(
    request: Request,
    repo_id: Optional[str] = Query(None, description="Filter by repository ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    issue_type: Optional[str] = Query(None, description="Filter by issue type"),
) -> list[dict[str, Any]]:
    """List all discovered issues, optionally filtered."""
    analyzer = request.app.state.repo_analyzer

    issues = list(analyzer.issues.values())

    if repo_id:
        issues = [i for i in issues if i.repo_id == repo_id]
    if status:
        issues = [i for i in issues if i.status == status]
    if severity:
        issues = [i for i in issues if i.severity == severity]
    if issue_type:
        issues = [i for i in issues if i.issue_type == issue_type]

    return [i.model_dump(mode="json") for i in issues]


@router.patch("/issues/{issue_id}", response_model=dict[str, Any])
async def update_issue(request: Request, issue_id: str, body: UpdateIssueRequest) -> dict[str, Any]:
    """Update an issue's status (e.g. dismiss it)."""
    analyzer = request.app.state.repo_analyzer

    issue = analyzer.issues.get(issue_id)
    if issue is None:
        raise HTTPException(404, f"Issue not found: {issue_id}")

    issue.status = body.status
    return {
        "id": issue.id,
        "status": issue.status,
        "message": f"Issue status updated to '{body.status}'.",
    }
