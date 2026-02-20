"""
backend/app/control_plane/router.py — Control-plane REST endpoints.

Mounted at ``/api/control-plane`` in ``main.py``.  Surfaces PR risk
scores, test coverage, repo health, and next-best-action recommendations
using mock data until the real analyzers are connected.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from shared.schemas import (
    CoverageReport,
    NextBestAction,
    PRRiskScore,
    RepoHealthReport,
)
from shared.mocks.mock_data import (
    SAMPLE_ACTIONS,
    SAMPLE_COVERAGE,
    SAMPLE_PR_SCORES,
    SAMPLE_REPO_HEALTH,
)

router = APIRouter()


@router.get("/prs", response_model=list[PRRiskScore])
async def get_pr_scores() -> list[PRRiskScore]:
    """Return risk-scored pull requests.

    Sorted by risk_score descending so the riskiest PRs appear first.
    """
    return sorted(SAMPLE_PR_SCORES, key=lambda p: p.risk_score, reverse=True)


@router.get("/coverage", response_model=CoverageReport)
async def get_coverage() -> CoverageReport:
    """Return the latest test-coverage report."""
    return SAMPLE_COVERAGE


@router.get("/health", response_model=RepoHealthReport)
async def get_repo_health() -> RepoHealthReport:
    """Return the latest repository health snapshot."""
    return SAMPLE_REPO_HEALTH


@router.get("/actions", response_model=list[NextBestAction])
async def get_recommended_actions() -> list[NextBestAction]:
    """Return recommended next-best-actions, sorted by priority."""
    priority_order = {"high": 0, "medium": 1, "low": 2}
    return sorted(SAMPLE_ACTIONS, key=lambda a: priority_order.get(a.priority, 9))
