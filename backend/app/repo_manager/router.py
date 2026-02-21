"""
backend/app/repo_manager/router.py — FastAPI endpoints for repository management.

Prefix: /api/repos
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app.config import settings
from backend.app.control_plane.github_connector import GitHubConnector
from backend.app.repo_manager.manager import RepoManager

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Request schemas ─────────────────────────────────────────────────────────


class AddRepoRequest(BaseModel):
    owner: str = Field(..., description="GitHub owner (user or org).")
    name: str = Field(..., description="Repository name.")


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.post("")
async def add_repo(request: Request, body: AddRepoRequest) -> dict[str, Any]:
    """Connect a new GitHub repository to Agent HQ."""
    try:
        repo_manager = request.app.state.repo_manager
        repo = await repo_manager.add_repo(body.owner, body.name)
        
        # Trigger Claude indexing in the background so the UI doesn't hang
        import asyncio
        analyzer = request.app.state.repo_analyzer
        asyncio.create_task(analyzer.index_repository(repo.id))
        
        return repo.model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("")
async def list_repos(request: Request) -> list[dict[str, Any]]:
    """List all connected repositories."""
    repos = await request.app.state.repo_manager.list_repos()
    return [r.model_dump(mode="json") for r in repos]


@router.get("/{repo_id}")
async def get_repo(request: Request, repo_id: str) -> dict[str, Any]:
    """Get details of a specific connected repository."""
    try:
        repo = await request.app.state.repo_manager.get_repo(repo_id)
        return repo.model_dump(mode="json")
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Repository not found: {repo_id}")


@router.delete("/{repo_id}")
async def remove_repo(request: Request, repo_id: str) -> dict[str, str]:
    """Disconnect a repository from Agent HQ."""
    try:
        await request.app.state.repo_manager.remove_repo(repo_id)
        return {"status": "removed", "repo_id": repo_id}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Repository not found: {repo_id}")


@router.get("/{repo_id}/structure")
async def get_structure(request: Request, repo_id: str) -> dict[str, Any]:
    """Get the file tree of a connected repository."""
    try:
        return await request.app.state.repo_manager.get_repo_structure(repo_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Repository not found: {repo_id}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GitHub API error: {exc}")


@router.get("/{repo_id}/prs")
async def list_prs(request: Request, repo_id: str) -> list[dict[str, Any]]:
    """List open PRs for a connected repository."""
    try:
        return await request.app.state.repo_manager.get_open_prs(repo_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Repository not found: {repo_id}")


@router.get("/{repo_id}/prs/{pr_number}")
async def get_pr_context(request: Request, repo_id: str, pr_number: int) -> dict[str, Any]:
    """Get full PR context for Claude review."""
    try:
        return await request.app.state.repo_manager.get_pr_full_context(repo_id, pr_number)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Repository not found: {repo_id}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GitHub API error: {exc}")


@router.get("/{repo_id}/prs/{pr_number}/review")
async def get_pr_review(request: Request, repo_id: str, pr_number: int) -> dict[str, Any]:
    """Get the full PR review if it exists."""
    analyzer = request.app.state.repo_analyzer
    # Search for an existing review for this repo_id + pr_number
    pr_reviews = [
        r for r in analyzer.reviews.values()
        if r.repo_id == repo_id and r.pr_number == pr_number
    ]
    if not pr_reviews:
        raise HTTPException(
            status_code=404, detail=f"PR Review not found for {repo_id} PR #{pr_number}"
        )
    
    # Sort by reviewed_at (most recent first) and return the latest
    pr_reviews.sort(key=lambda x: x.reviewed_at, reverse=True)
    return pr_reviews[0].model_dump(mode="json")


@router.post("/{repo_id}/analyze")
async def trigger_analysis(request: Request, repo_id: str) -> dict[str, str]:
    """Trigger a re-analysis of the repository by Claude.

    Runs the repo analyzer in the background and emits WebSocket events
    for progress tracking.
    """
    try:
        repo = await request.app.state.repo_manager.get_repo(repo_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Repository not found: {repo_id}")

    import asyncio
    from backend.app.websocket.events import event_router
    from shared.events import EventType, create_ws_event

    async def _run_analysis():
        """Background task: run Claude analysis and emit progress events."""
        try:
            # Emit start event
            await event_router.emit(create_ws_event(
                task_id=repo_id, event_type=EventType.STATUS_UPDATE,
                payload={"status": f"Analyzing {repo.full_name}...", "category": "repo", "severity": "info"},
            ))

            analyzer = request.app.state.repo_analyzer
            result = await analyzer.analyze_repository(repo_id)

            # Update repo with analysis results
            repo_mgr = request.app.state.repo_manager
            from datetime import datetime, timezone
            repo_obj = await repo_mgr.get_repo(repo_id)
            repo_obj.last_analyzed = datetime.now(timezone.utc)
            if result and hasattr(result, "health_score"):
                repo_obj.health_score = result.health_score

            # Emit completion event
            await event_router.emit(create_ws_event(
                task_id=repo_id, event_type=EventType.STATUS_UPDATE,
                payload={
                    "status": f"Analysis complete for {repo.full_name}",
                    "category": "repo", "severity": "info",
                    "health_score": getattr(result, "health_score", None),
                },
            ))
            logger.info("Analysis complete for %s", repo.full_name)
        except Exception as exc:
            logger.error("Analysis failed for %s: %s", repo.full_name, exc)
            await event_router.emit(create_ws_event(
                task_id=repo_id, event_type=EventType.STATUS_UPDATE,
                payload={"status": f"Analysis failed: {exc}", "category": "repo", "severity": "error"},
            ))

    asyncio.create_task(_run_analysis())
    return {
        "status": "analysis_started",
        "repo_id": repo_id,
        "repo": repo.full_name,
    }

