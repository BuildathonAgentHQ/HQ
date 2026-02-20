"""
backend/app/control_plane/router.py — Control-plane REST endpoints.

Mounted at `/api/control-plane` in `main.py`. Surfaces PR risk
scores, test coverage, repo health, and next-best-action recommendations
by evaluating live GitHub data and running it through the custom algorithms.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from backend.app.config import settings
from backend.app.control_plane.coverage_analyzer import CoverageAnalyzer
from backend.app.control_plane.github_connector import GitHubConnector
from backend.app.control_plane.pr_analyzer import PRAnalyzer
from backend.app.control_plane.recommendations import RecommendationEngine
from backend.app.control_plane.repo_health import RepoHealthAnalyzer
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


@router.get("/prs", response_model=list[PRRiskScore])
async def get_pr_scores() -> list[PRRiskScore]:
    """Return risk-scored pull requests.

    Sorted by risk_score descending so the riskiest PRs appear first.
    """
    try:
        open_prs = await github_connector.get_open_prs()
        scores: list[PRRiskScore] = []
        for pr in open_prs:
            pr_num = pr.get("number")
            if pr_num:
                try:
                    files = await github_connector.get_pr_files(pr_num)
                    # We pass an empty string for diff to save overhead, parsing lines directly from files
                    score = await pr_analyzer.analyze_pr(pr, files, "")
                    scores.append(score)
                except Exception as e:
                    logger.warning(f"Failed to analyze PR {pr_num}: {e}")

        # Update dependency overlap if applicable
        try:
            deps = await pr_analyzer.detect_dependencies(open_prs)
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
async def get_coverage() -> CoverageReport:
    """Return the latest test-coverage report."""
    return await coverage_analyzer.analyze_coverage()


@router.get("/health", response_model=RepoHealthReport)
async def get_repo_health() -> RepoHealthReport:
    """Return the latest repository health snapshot."""
    return await health_analyzer.analyze_health()


@router.get("/actions", response_model=list[NextBestAction])
async def get_recommended_actions() -> list[NextBestAction]:
    """Return recommended next-best-actions, sorted by priority."""
    return await recommendation_engine.generate_recommendations()
