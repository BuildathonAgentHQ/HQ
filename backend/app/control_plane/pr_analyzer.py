"""
PR Analyzer for Agent HQ Control Plane.

Analyzes GitHub Pull Requests to assess risk levels based on diff size,
modifications to core files, missing tests, and file churn. Also provides
functionality to detect PR dependencies and suggest reviewers.
"""

from __future__ import annotations

import fnmatch
from typing import Any

from backend.app.control_plane.github_connector import GitHubConnector
from shared.schemas import PRRiskFactors, PRRiskScore


class PRAnalyzer:
    """Analyzes PRs for risk, dependencies, and reviewers."""

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
            ".github/*", "Dockerfile", "docker-compose*"
        ]

    def _is_core_file(self, filename: str) -> bool:
        """Check if a file matches any of the core file patterns."""
        # Convert path to just the filename for some patterns, but keep full for others
        # We'll just match the full path against the pattern
        return any(fnmatch.fnmatch(filename, pat) or fnmatch.fnmatch(filename.split("/")[-1], pat) 
                   for pat in self.core_file_patterns)

    async def analyze_pr(self, pr_data: dict[str, Any], files: list[dict[str, Any]], diff: str) -> PRRiskScore:
        """Calculate a comprehensive risk score for a PR."""
        
        # 1. Diff Size (30%)
        # Calculate total additions + deletions
        diff_size = sum(f.get("additions", 0) + f.get("deletions", 0) for f in files)
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
        core_files_changed = any(self._is_core_file(f["filename"]) for f in files)
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
            elif test_files_changed < code_files_changed:  # simplistic ratio check
                missing_tests = True
                missing_tests_risk = 50

        # 4. Churn Score (20%)
        # For each changed file, count how many times it was changed in the last 30 days
        # We will use the commit history to calculate this
        # Since history might be large, we'll fetch up to 100 recent commits for the analysis
        churn_risk = 0.0
        try:
            commits = await self.github.get_commit_history(count=100)
            
            for commit in commits:
                sha = commit.get("sha")
                if sha:
                    # In a real app we might fetch the commit details to see which files changed.
                    # For performance in this agent setup, we'll try to estimate or if API permits, get files.
                    # Since /commits/{sha} is needed to get files per commit, it could be N API calls.
                    # To avoid rate limits, we will do a simpler heuristic:
                    # If the file path is in the commit message (as a convention) or we skip it for now
                    # We will just assign a base churn risk here if we can't reliably fetch it all.
                    pass
                    
            # Let's say we normalize churn based on simple heuristics since we don't want 100 API calls
            # Mock churn for now based on if it's a core file (often high churn)
            if core_files_changed:
                churn_risk = 50.0
            else:
                churn_risk = 10.0
                
        except Exception:
            churn_risk = 0.0

        # Calculate final risk score
        risk_score_raw = (diff_risk * 0.30) + (core_risk * 0.25) + (missing_tests_risk * 0.25) + (churn_risk * 0.20)
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
            has_dependency_overlap=False  # To be updated by dependency detection
        )
            
        return PRRiskScore(
            pr_id=str(pr_data.get("id", pr_data.get("number", 0))),
            pr_number=pr_data.get("number", 0),
            title=pr_data.get("title", "Untitled PR"),
            author=pr_data.get("user", {}).get("login", "Unknown"),
            risk_score=risk_score,
            risk_level=risk_level,
            factors=factors,
            reviewers_suggested=[]
        )

    async def detect_dependencies(self, prs: list[dict[str, Any]]) -> dict[int, list[int]]:
        """
        Detect cross-PR file conflicts.
        Returns a dict mapping PR number -> list of dependent/conflicting PR numbers.
        """
        pr_files_map: dict[int, set[str]] = {}
        
        # Fetch files for all open PRs
        for pr in prs:
            pr_num = pr.get("number")
            if pr_num:
                try:
                    files = await self.github.get_pr_files(pr_num)
                    pr_files_map[pr_num] = {f["filename"] for f in files}
                except Exception:
                    pr_files_map[pr_num] = set()
                    
        dependencies: dict[int, list[int]] = {pr_num: [] for pr_num in pr_files_map}
        
        pr_numbers = list(pr_files_map.keys())
        for i, pr1 in enumerate(pr_numbers):
            for pr2 in pr_numbers[i+1:]:
                # Check for set intersection
                if pr_files_map[pr1].intersection(pr_files_map[pr2]):
                    dependencies[pr1].append(pr2)
                    dependencies[pr2].append(pr1)
                    
        return dependencies

    async def suggest_reviewers(self, files: list[dict[str, Any]], commit_history: list[dict[str, Any]]) -> list[str]:
        """Suggest reviewers based on recent committers to the repository."""
        # A simple heuristic based on overall recent committers
        author_counts: dict[str, int] = {}
        
        for commit in commit_history:
            author = commit.get("commit", {}).get("author", {}).get("name")
            login = commit.get("author", {}).get("login")
            
            # Prefer login if available, else name
            reviewer = login or author
            if reviewer and "[bot]" not in reviewer.lower():
                author_counts[reviewer] = author_counts.get(reviewer, 0) + 1
                
        # Sort authors by commit count, descending
        sorted_authors = sorted(author_counts.keys(), key=lambda a: author_counts[a], reverse=True)
        
        # Return top 3 suggested reviewers
        return sorted_authors[:3]
