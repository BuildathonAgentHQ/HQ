"""
backend/app/control_plane/router.py — Control-plane REST endpoints.

Mounted at `/api/control-plane` in `main.py`. Surfaces PR risk
scores, test coverage, repo health, and next-best-action recommendations
by evaluating live GitHub data and running it through the custom algorithms.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from backend.app.config import settings
from backend.app.control_plane.coverage_analyzer import CoverageAnalyzer
from backend.app.control_plane.github_connector import GitHubConnector
from backend.app.control_plane.pr_analyzer import PRAnalyzer
from backend.app.control_plane.recommendations import RecommendationEngine
from backend.app.control_plane.repo_health import RepoHealthAnalyzer
from backend.app.repo_manager.manager import RepoManager
from shared.schemas import (
    CoverageReport,
    NextBestAction,
    PRRiskScore,
    RepoHealthReport,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize Analyzers & Connectors
github_connector = GitHubConnector(settings)
pr_analyzer = PRAnalyzer(github_connector)
coverage_analyzer = CoverageAnalyzer(github_connector, settings)
health_analyzer = RepoHealthAnalyzer(github_connector)
recommendation_engine = RecommendationEngine(pr_analyzer, coverage_analyzer, health_analyzer)
# Delete the import statement that causes circular imports
# repo_manager will be accessed via request.app.state.repo_manager


@router.get("/prs", response_model=list[PRRiskScore])
async def get_pr_scores(request: Request, repo_id: str, refresh: bool = False) -> list[PRRiskScore]:
    """Return risk-scored pull requests.

    Sorted by risk_score descending so the riskiest PRs appear first.
    Pass ?refresh=true to bypass cache and fetch fresh data from GitHub.
    """
    try:
        repo_manager = request.app.state.repo_manager
        repo = await repo_manager.get_repo(repo_id)
        open_prs = await github_connector.get_open_prs(repo.full_name, bypass_cache=refresh)
        scores: list[PRRiskScore] = []
        for pr in open_prs:
            pr_num = pr.get("number")
            if pr_num:
                try:
                    files = await github_connector.get_pr_files(repo.full_name, pr_num)
                    # We pass an empty string for diff to save overhead, parsing lines directly from files
                    score = await pr_analyzer.analyze_pr(pr, files, "", repo.full_name)
                    scores.append(score)
                except Exception as e:
                    logger.warning(f"Failed to analyze PR {pr_num}: {e}")

        # Update dependency overlap if applicable
        try:
            deps = await pr_analyzer.detect_dependencies(open_prs, repo.full_name)
            for score in scores:
                if deps.get(score.pr_number):
                    score.factors.has_dependency_overlap = True
        except Exception:
            pass

        return sorted(scores, key=lambda p: p.risk_score, reverse=True)
    except Exception as e:
        logger.error(f"Error fetching PR scores: {e}")
        return []


@router.get("/coverage", response_model=CoverageReport)
async def get_coverage(request: Request, repo_id: str) -> CoverageReport:
    """Return feature-level test coverage across all PRs (open + closed)."""
    repo_manager = request.app.state.repo_manager
    repo = await repo_manager.get_repo(repo_id)
    return await coverage_analyzer.analyze_coverage(repo.full_name)


@router.get("/health", response_model=RepoHealthReport)
async def get_repo_health(request: Request, repo_id: str) -> RepoHealthReport:
    """Return the latest repository health snapshot."""
    repo_manager = request.app.state.repo_manager
    repo = await repo_manager.get_repo(repo_id)
    return await health_analyzer.analyze_health(repo.full_name)


@router.get("/actions", response_model=list[NextBestAction])
async def get_recommended_actions(request: Request, repo_id: str) -> list[NextBestAction]:
    """Return recommended next-best-actions, sorted by priority."""
    # Temporarily we will not use repo_id for actions generating as it generates via analyzers underneath that we'd have to rewrite (and it's a bit mocked for now)
    repo_manager = request.app.state.repo_manager
    repo = await repo_manager.get_repo(repo_id)
    return await recommendation_engine.generate_recommendations(repo.full_name)
