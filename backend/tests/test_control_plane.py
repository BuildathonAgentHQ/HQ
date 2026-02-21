"""Tests for the control plane: PR risk scoring, coverage, recommendations."""
from __future__ import annotations

import pytest

from app.config import Settings
from app.control_plane.coverage_analyzer import CoverageAnalyzer
from app.control_plane.github_connector import GitHubConnector
from app.control_plane.pr_analyzer import PRAnalyzer
from app.control_plane.recommendations import RecommendationEngine
from app.control_plane.repo_health import RepoHealthAnalyzer
from shared.schemas import (
    CoverageReport,
    NextBestAction,
    PRRiskScore,
    RepoHealthReport,
)


@pytest.fixture
def settings():
    return Settings(USE_GITHUB=False)


@pytest.fixture
def github(settings):
    return GitHubConnector(settings)


class TestGitHubConnector:
    @pytest.mark.asyncio
    async def test_get_open_prs_returns_list(self, github):
        prs = await github.get_open_prs()
        assert isinstance(prs, list)
        assert len(prs) > 0

    @pytest.mark.asyncio
    async def test_get_pr_files(self, github):
        files = await github.get_pr_files(1)
        assert isinstance(files, list)

    @pytest.mark.asyncio
    async def test_get_commit_history(self, github):
        commits = await github.get_commit_history(5)
        assert isinstance(commits, list)


class TestPRAnalyzer:
    @pytest.mark.asyncio
    async def test_analyze_pr_returns_risk_score(self, github):
        pa = PRAnalyzer(github)
        prs = await github.get_open_prs()
        pr = prs[0]
        files = await github.get_pr_files(pr.get("number", 1))
        diff = await github.get_pr_diff(pr.get("number", 1))
        score = await pa.analyze_pr(pr, files, diff)
        assert isinstance(score, PRRiskScore)
        assert 0 <= score.risk_score <= 100
        assert score.risk_level in ("low", "medium", "high", "critical")


class TestCoverageAnalyzer:
    @pytest.mark.asyncio
    async def test_returns_coverage_report(self, github, settings):
        ca = CoverageAnalyzer(github, settings)
        report = await ca.analyze_coverage()
        assert isinstance(report, CoverageReport)
        assert 0 <= report.total_coverage_pct <= 100


class TestRepoHealthAnalyzer:
    @pytest.mark.asyncio
    async def test_returns_health_report(self, github):
        rha = RepoHealthAnalyzer(github)
        health = await rha.analyze_health()
        assert isinstance(health, RepoHealthReport)
        assert health.ci_status in ("passing", "failing", "unknown")


class TestRecommendationEngine:
    @pytest.mark.asyncio
    async def test_generates_recommendations(self, github, settings):
        pa = PRAnalyzer(github)
        ca = CoverageAnalyzer(github, settings)
        rha = RepoHealthAnalyzer(github)
        engine = RecommendationEngine(pa, ca, rha)
        actions = await engine.generate_recommendations()
        assert isinstance(actions, list)
        if actions:
            assert isinstance(actions[0], NextBestAction)
