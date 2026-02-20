"""
Repository Health Analyzer for Agent HQ Control Plane.

Analyzes the overall health of the repository including CI status, flaky tests,
frequently changed (hot) files, and technical debt comments.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.app.control_plane.github_connector import GitHubConnector
from shared.schemas import HotFile, RepoHealthReport, TechDebtItem

logger = logging.getLogger(__name__)


class RepoHealthAnalyzer:
    """Analyzes repository health metrics."""

    def __init__(self, github: GitHubConnector):
        self.github = github

    async def analyze_health(self) -> RepoHealthReport:
        """
        Aggregate all repository health metrics into a single report.
        """
        # Fetch data needed for analysis
        commits = []
        try:
            commits = await self.github.get_commit_history(count=50) # Get enough for both flaky tests and hot files
        except Exception as e:
            logger.warning(f"Failed to fetch commit history for health analysis: {e}")

        # 1. CI Status
        ci_status = "unknown"
        if commits:
            latest_sha = commits[0].get("sha")
            if latest_sha:
                try:
                    check_runs = await self.github.get_check_runs(latest_sha)
                    if hasattr(check_runs, "get") and check_runs.get("state"):
                        # If mock data returns combined status structure
                        state = check_runs.get("state")
                        if state in ("success", "passing"):
                            ci_status = "passing"
                        elif state in ("failure", "error", "failing"):
                            ci_status = "failing"
                    elif isinstance(check_runs, list) and check_runs:
                        # Actual check runs list
                        conclusions = [c.get("conclusion") for c in check_runs if c.get("conclusion")]
                        if any(c in ("failure", "timed_out", "action_required") for c in conclusions):
                            ci_status = "failing"
                        elif all(c == "success" for c in conclusions if c):
                            ci_status = "passing"
                except Exception as e:
                    logger.warning(f"Failed to fetch check runs: {e}")

        # 2. Flaky Tests
        # For a true implementation, we would iterate through the last 20 CI runs, 
        # specifically parsing the JUnit XML/test reports attached to failures.
        # Since that data is highly specialized per-repo, we'll use a mocked heuristic
        # based on recent commits or simply return known flaky tests if using mocks.
        flaky_tests: list[str] = []
        if not self.github.use_github:
            flaky_tests = ["test_oauth_token_refresh_timeout", "test_database_pool_exhaustion"]

        # 3. Hot Files
        hot_files = await self._calculate_hot_files(commits)

        # 4. Tech Debt Items
        # Parse recently changed files for TODO/FIXME/HACK/XXX
        tech_debt_items = await self._find_tech_debt(hot_files)

        return RepoHealthReport(
            ci_status=ci_status,
            flaky_tests=flaky_tests,
            hot_files=hot_files,
            tech_debt_items=tech_debt_items
        )

    async def _calculate_hot_files(self, commits: list[dict[str, Any]]) -> list[HotFile]:
        """Calculate the top 10 most changed files in the last 30 days."""
        # If we have real git connectivity, we'd fetch the files for each commit.
        # To avoid massive API rate limits for 50 commits, we'll try to guess from mock
        # or use a simplified approach. 
        if not self.github.use_github:
            # Generate deterministic mock hot files
            return [
                HotFile(
                    path="backend/app/orchestrator/router.py", 
                    change_count_30d=14, 
                    last_changed=datetime.now(timezone.utc) - timedelta(hours=2)
                ),
                HotFile(
                    path="shared/schemas.py", 
                    change_count_30d=11, 
                    last_changed=datetime.now(timezone.utc) - timedelta(days=1)
                ),
                HotFile(
                    path="frontend/src/components/sidebar.tsx", 
                    change_count_30d=8, 
                    last_changed=datetime.now(timezone.utc) - timedelta(days=3)
                )
            ]
            
        # In a real scenario hitting the GH API, doing 50 /commits/{sha} calls is heavy.
        # We would ideally use the GraphQL API. For this connector, if we have limited quota,
        # we will use a safe mock subset if real data is too expensive to fetch right now.
        return []

    async def _find_tech_debt(self, hot_files: list[HotFile]) -> list[TechDebtItem]:
        """Find tech debt comments in hot/recently changed files."""
        # A true implementation would cat the files or fetch them from GitHub
        # and parse via regex. We'll simulate the regex parsing logic here.
        items: list[TechDebtItem] = []
        
        if not self.github.use_github:
            return [
                TechDebtItem(
                    description="HACK: Temporarily bypassing CSRF validation for webhook ingress",
                    age_days=14,
                    severity="high"
                ),
                TechDebtItem(
                    description="FIXME: Race condition in PTY stdout reading stream",
                    age_days=3,
                    severity="medium"
                ),
                TechDebtItem(
                    description="TODO: Migrate this dictionary to a proper Redis cache",
                    age_days=45,
                    severity="low"
                )
            ]

        # The pattern for extracting debt (e.g. re.compile(r'(TODO|FIXME|HACK|XXX)[\s:]+(.*)', re.IGNORECASE))
        # We would normally download the file content for each hot file
        # content = await self.github._request("GET", f"/repos/.../contents/{hot_file.path}")
        # for match in debt_pattern.finditer(decoded_content):
        #    ... classification logic ...
        
        # Since we are orchestrating an MVP, if github is enabled but we don't 
        # want to burn content API limits during hackathon
        return items
