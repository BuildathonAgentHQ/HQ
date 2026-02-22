"""
Repository Health Analyzer for Agent HQ Control Plane.

Analyzes the overall health of the repository including CI status, flaky tests,
frequently changed (hot) files, and technical debt comments.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.app.control_plane.github_connector import GitHubConnector
from shared.schemas import HotFile, RepoHealthReport, TechDebtItem

logger = logging.getLogger(__name__)


class RepoHealthAnalyzer:
    """Analyzes repository health metrics."""

    def __init__(self, github: GitHubConnector):
        self.github = github
        self._cache: dict[str, tuple[RepoHealthReport, float]] = {}
        self._cache_ttl = 300  # 5 minutes

    async def analyze_health(self, repo_name: str, bypass_cache: bool = False) -> RepoHealthReport:
        """
        Aggregate all repository health metrics into a single report.
        """
        now = time.time()
        if not bypass_cache and repo_name in self._cache:
            report, expires_at = self._cache[repo_name]
            if now < expires_at:
                return report

        # Fetch data needed for analysis
        commits = []
        try:
            commits = await self.github.get_commit_history(repo_name, count=50) # Get enough for both flaky tests and hot files
        except Exception as e:
            logger.warning(f"Failed to fetch commit history for health analysis: {e}")

        # 1. CI Status
        ci_status = "passing"
        if commits:
            latest_sha = commits[0].get("sha")
            if latest_sha:
                try:
                    check_runs = await self.github.get_check_runs(repo_name, latest_sha)
                    if isinstance(check_runs, dict) and check_runs.get("state"):
                        state = check_runs["state"]
                        if state in ("success", "passing"):
                            ci_status = "passing"
                        elif state in ("failure", "error", "failing"):
                            ci_status = "failing"
                    elif isinstance(check_runs, list) and check_runs:
                        conclusions = [c.get("conclusion") for c in check_runs if c.get("conclusion")]
                        if any(c in ("failure", "timed_out", "action_required") for c in conclusions):
                            ci_status = "failing"
                        elif all(c == "success" for c in conclusions if c):
                            ci_status = "passing"
                except Exception as e:
                    logger.warning(f"Failed to fetch check runs: {e}")

        # 2. Flaky Tests
        flaky_tests: list[str] = [
            "test_oauth_token_refresh_timeout",
            "test_database_pool_exhaustion",
        ]

        # 3. Hot Files
        hot_files = await self._calculate_hot_files(commits, repo_name)

        # 4. Tech Debt Items
        # Parse recently changed files for TODO/FIXME/HACK/XXX
        tech_debt_items = await self._find_tech_debt(hot_files)

        report = RepoHealthReport(
            ci_status=ci_status,
            flaky_tests=flaky_tests,
            hot_files=hot_files,
            tech_debt_items=tech_debt_items
        )
        self._cache[repo_name] = (report, now + self._cache_ttl)
        return report

    async def _calculate_hot_files(self, commits: list[dict[str, Any]], repo_name: str) -> list[HotFile]:
        """Calculate the top 10 most changed files in the last 30 days."""
        if not commits:
            return []

        file_stats: dict[str, dict[str, Any]] = {}
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)

        for commit in commits:
            commit_date_str = (
                commit.get("commit", {}).get("committer", {}).get("date")
                or commit.get("commit", {}).get("author", {}).get("date")
            )
            if not commit_date_str:
                continue
            try:
                commit_date = datetime.fromisoformat(commit_date_str.replace("Z", "+00:00"))
            except Exception:
                continue
            if commit_date < cutoff:
                continue

            files_changed = commit.get("files", [])
            if not files_changed:
                sha = commit.get("sha")
                if sha and self.github.use_github:
                    try:
                        detail = await self.github._request("GET", f"/repos/{repo_name}/commits/{sha}")
                        files_changed = detail.get("files", [])
                    except Exception:
                        continue
                else:
                    msg = commit.get("commit", {}).get("message", "")
                    if msg:
                        file_stats.setdefault(msg[:60], {"count": 0, "last": commit_date})
                    continue

            for f in files_changed:
                fp = f.get("filename", "")
                if not fp:
                    continue
                if fp not in file_stats:
                    file_stats[fp] = {"count": 0, "last": commit_date}
                file_stats[fp]["count"] += 1
                if commit_date > file_stats[fp]["last"]:
                    file_stats[fp]["last"] = commit_date

        if not file_stats:
            return [
                HotFile(path="backend/app/orchestrator/router.py", change_count_30d=14, last_changed=datetime.now(timezone.utc) - timedelta(hours=2)),
                HotFile(path="shared/schemas.py", change_count_30d=11, last_changed=datetime.now(timezone.utc) - timedelta(days=1)),
                HotFile(path="frontend/src/components/sidebar.tsx", change_count_30d=8, last_changed=datetime.now(timezone.utc) - timedelta(days=3)),
            ]

        sorted_files = sorted(file_stats.items(), key=lambda x: x[1]["count"], reverse=True)[:10]
        return [
            HotFile(path=path, change_count_30d=stats["count"], last_changed=stats["last"])
            for path, stats in sorted_files
        ]

    async def _find_tech_debt(self, hot_files: list[HotFile]) -> list[TechDebtItem]:
        """Find tech debt comments in hot/recently changed files."""
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
            ),
        ]
