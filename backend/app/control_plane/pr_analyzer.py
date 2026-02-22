"""
PR Analyzer for Agent HQ Control Plane.

Provides both fast heuristic risk scoring (instant results) AND deep
Claude-powered PR review (arrives asynchronously).  The frontend shows
the heuristic score first, then updates when the Claude review lands.
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging
from typing import Any, Optional

from backend.app.control_plane.github_connector import GitHubConnector
from shared.schemas import CodeIssue, PRReview, PRRiskFactors, PRRiskScore

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency at module load
_repo_analyzer: Any = None


def _get_repo_analyzer() -> Any:
    """Lazy-load the RepoAnalyzer singleton to avoid import cycles."""
    global _repo_analyzer
    if _repo_analyzer is None:
        try:
            from backend.app.claude_client.client import ClaudeClient
            from backend.app.claude_client.repo_analyzer import RepoAnalyzer
            from backend.app.config import settings
            from backend.app.repo_manager.manager import RepoManager

            claude = ClaudeClient(settings)
            github = GitHubConnector(settings)
            repo_mgr = RepoManager(settings, github)
            _repo_analyzer = RepoAnalyzer(claude, repo_mgr)
        except Exception as exc:
            logger.warning("Failed to initialise RepoAnalyzer: %s", exc)
    return _repo_analyzer


class PRAnalyzer:
    """Analyzes PRs for risk, dependencies, and reviewers.

    Two-tier analysis:
        1. **Heuristic** (``analyze_pr``) — instant, based on diff size,
           core files, missing tests, and churn.  Returns ``PRRiskScore``.
        2. **Claude** (``get_pr_review``) — deep review via
           ``RepoAnalyzer.analyze_pr()``.  Returns ``PRReview``.
    """

    def __init__(self, github: GitHubConnector):
        self.github = github
        self.core_file_patterns = [
            # Config files
            "*.yml", "*.yaml", "*.json", "*.toml", "*.env*",
            # Entry points
            "main.*", "index.*", "app.*",
            # Database
            "*migration*", "*schema*", "models.*",
            # Auth
            "*auth*", "*permission*", "*security*",
            # CI
            ".github/*", "Dockerfile", "docker-compose*",
        ]
        # Cache for Claude reviews: (repo_id, pr_number) → PRReview
        self._review_cache: dict[tuple[str, int], PRReview] = {}

    # ── Core file detection ──────────────────────────────────────────────

    def _is_core_file(self, filename: str) -> bool:
        """Check if a file matches any of the core file patterns."""
        return any(
            fnmatch.fnmatch(filename, pat)
            or fnmatch.fnmatch(filename.split("/")[-1], pat)
            for pat in self.core_file_patterns
        )

    # ── Tier 1: fast heuristic analysis ──────────────────────────────────

    async def analyze_pr(
        self,
        pr_data: dict[str, Any],
        files: list[dict[str, Any]],
        diff: str,
        repo_name: str,
        *,
        repo_id: Optional[str] = None,
    ) -> PRRiskScore:
        """Calculate a heuristic risk score, then optionally kick off a
        deep Claude review in the background.

        Args:
            pr_data: Raw PR dict from GitHub API.
            files:   List of file dicts from ``/pulls/{n}/files``.
            diff:    Full PR diff string (may be empty for faster scoring).
            repo_name: Full repository name (e.g. owner/repo).
            repo_id: If provided, triggers an async Claude review.

        Returns:
            ``PRRiskScore`` with heuristic-based risk.
        """
        # 1. Diff Size (30%)
        diff_size = sum(
            f.get("additions", 0) + f.get("deletions", 0) for f in files
        )
        if diff_size <= 100:
            diff_risk = 0
        elif diff_size <= 500:
            diff_risk = 25
        elif diff_size <= 1000:
            diff_risk = 50
        elif diff_size <= 2000:
            diff_risk = 75
        else:
            diff_risk = 100

        # 2. Core Files Changed (25%)
        core_files_changed = any(
            self._is_core_file(f["filename"]) for f in files
        )
        core_risk = 100 if core_files_changed else 0

        # 3. Missing Tests (25%)
        code_files_changed = 0
        test_files_changed = 0
        for f in files:
            filename = f["filename"].lower()
            if filename.endswith((".py", ".js", ".ts")):
                if "test" in filename:
                    test_files_changed += 1
                else:
                    code_files_changed += 1

        missing_tests = False
        missing_tests_risk = 0
        if code_files_changed > 0:
            if test_files_changed == 0:
                missing_tests = True
                missing_tests_risk = 100
            elif test_files_changed < code_files_changed:
                missing_tests = True
                missing_tests_risk = 50

        # 4. Churn Score (20%)
        churn_risk = 0.0
        try:
            await self.github.get_commit_history(repo_name, count=100)
            churn_risk = 50.0 if core_files_changed else 10.0
        except Exception:
            churn_risk = 0.0

        # Calculate final risk score
        risk_score_raw = (
            diff_risk * 0.30
            + core_risk * 0.25
            + missing_tests_risk * 0.25
            + churn_risk * 0.20
        )
        risk_score = int(min(max(risk_score_raw, 0), 100))

        if risk_score < 25:
            risk_level = "low"
        elif risk_score < 50:
            risk_level = "medium"
        elif risk_score < 75:
            risk_level = "high"
        else:
            risk_level = "critical"

        factors = PRRiskFactors(
            diff_size=diff_size,
            core_files_changed=core_files_changed,
            missing_tests=missing_tests,
            churn_score=churn_risk,
            has_dependency_overlap=False,
        )

        result = PRRiskScore(
            pr_id=str(pr_data.get("id", pr_data.get("number", 0))),
            pr_number=pr_data.get("number", 0),
            title=pr_data.get("title", "Untitled PR"),
            author=pr_data.get("user", {}).get("login", "Unknown"),
            risk_score=risk_score,
            risk_level=risk_level,
            factors=factors,
            reviewers_suggested=[],
        )

        # Fire-and-forget Claude deep review if repo_id is provided
        if repo_id:
            pr_number = pr_data.get("number")
            if pr_number:
                asyncio.create_task(
                    self._background_claude_review(repo_id, pr_number)
                )

        return result

    # ── Tier 2: Claude deep review ───────────────────────────────────────

    async def get_pr_review(
        self, repo_id: str, pr_number: int
    ) -> Optional[PRReview]:
        """Return the cached Claude-powered PR review, or trigger one.

        Returns:
            ``PRReview`` if available, otherwise ``None`` (review in progress).
        """
        cache_key = (repo_id, pr_number)
        if cache_key in self._review_cache:
            return self._review_cache[cache_key]

        # Trigger a review and return None — frontend polls or listens on WS
        asyncio.create_task(self._background_claude_review(repo_id, pr_number))
        return None

    async def get_pr_issues(
        self, repo_id: str, pr_number: int
    ) -> list[CodeIssue]:
        """Return issues found by Claude for a specific PR.

        Returns an empty list if the review hasn't completed yet.
        """
        analyzer = _get_repo_analyzer()
        if analyzer is None:
            return []
        return [
            issue
            for issue in analyzer.issues.values()
            if issue.repo_id == repo_id and issue.pr_number == pr_number
        ]

    async def _background_claude_review(
        self, repo_id: str, pr_number: int
    ) -> None:
        """Run Claude review in the background and cache the result."""
        cache_key = (repo_id, pr_number)
        if cache_key in self._review_cache:
            return  # already done

        analyzer = _get_repo_analyzer()
        if analyzer is None:
            logger.warning("RepoAnalyzer unavailable; skipping Claude review")
            return

        try:
            logger.info(
                "Starting background Claude review for PR #%d", pr_number
            )
            review = await analyzer.analyze_pr(repo_id, pr_number)
            self._review_cache[cache_key] = review
            logger.info(
                "Claude review complete for PR #%d: verdict=%s",
                pr_number,
                review.verdict,
            )
        except Exception:
            logger.exception(
                "Background Claude review failed for PR #%d", pr_number
            )

    # ── Dependency & reviewer analysis (unchanged) ───────────────────────

    async def detect_dependencies(self, prs: list[dict[str, Any]], repo_name: str) -> dict[int, list[int]]:
        """Identify missing PR dependency overlaps (e.g., both touch `config/db.json`)."""
        pr_files: dict[int, set[str]] = {}

        for pr in prs:
            pr_num = pr.get("number")
            if not pr_num:
                continue
            try:
                files = await self.github.get_pr_files(repo_name, pr_num)
                pr_files[pr_num] = {f["filename"] for f in files}
            except Exception:
                pr_files[pr_num] = set()

        dependencies: dict[int, list[int]] = {
            pr_num: [] for pr_num in pr_files
        }

        pr_numbers = list(pr_files.keys())
        for i, num1 in enumerate(pr_numbers):
            files1 = pr_files[num1]
            for num2 in pr_numbers[i + 1 :]:
                files2 = pr_files[num2]
                if files1.intersection(files2):
                    dependencies[num1].append(num2)
                    dependencies[num2].append(num1)

        return dependencies

    async def suggest_reviewers(
        self,
        files: list[dict[str, Any]],
        commit_history: list[dict[str, Any]],
    ) -> list[str]:
        """Suggest reviewers based on recent committers."""
        author_counts: dict[str, int] = {}

        for commit in commit_history:
            author = commit.get("commit", {}).get("author", {}).get("name")
            login = commit.get("author", {}).get("login")
            reviewer = login or author
            if reviewer and "[bot]" not in reviewer.lower():
                author_counts[reviewer] = author_counts.get(reviewer, 0) + 1

        sorted_authors = sorted(
            author_counts.keys(),
            key=lambda a: author_counts[a],
            reverse=True,
        )
        return sorted_authors[:3]
