"""
Coverage Analyzer for Agent HQ Control Plane.

Analyzes test coverage across the repository, identifies untested PR diffs,
and generates automated test-writing tasks for the Agent HQ orchestrator.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from backend.app.config import Settings
from backend.app.control_plane.github_connector import GitHubConnector
from shared.mocks import mock_github
from shared.schemas import CoverageReport, TaskCreate, UntestableDiff

logger = logging.getLogger(__name__)


class CoverageAnalyzer:
    """Analyzes test coverage and generates automated test-writing tasks."""

    def __init__(self, github: GitHubConnector, settings: Settings):
        self.github = github
        self.settings = settings

    async def analyze_coverage(self) -> CoverageReport:
        """
        Analyze the repository's test coverage.
        Prefers local files, then GitHub artifacts, and falls back to mocks.
        """
        coverage_data: dict[str, Any] = {}
        
        # 1. Check local coverage files
        # Assuming we might run in the repo root or can find coverage.json
        # In a real environment, we'd look for github paths or specific directories
        coverage_file = Path("coverage.json")
        if coverage_file.exists():
            try:
                with open(coverage_file, "r") as f:
                    coverage_data = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to parse local coverage.json: {e}")
        
        # 2. GitHub Actions artifacts (Skipping implementation details for sprint scope,
        # but the structure would query GitHub actions artifacts via API.)
        
        # 3. Fallback to mock data if no valid data source
        if not coverage_data:
            coverage_data = mock_github.get_sample_coverage_json()

        # Parse the coverage_data
        total_coverage_pct = coverage_data.get("totals", {}).get("percent_covered", 0.0)
        
        module_coverage: dict[str, float] = {}
        files_data = coverage_data.get("files", {})
        for filepath, data in files_data.items():
            pct = data.get("summary", {}).get("percent_covered", 0.0)
            module_name = filepath.split("/")[0] if "/" in filepath else filepath
            
            if module_name not in module_coverage:
                module_coverage[module_name] = pct
            else:
                # Naive average for scoping
                module_coverage[module_name] = (module_coverage[module_name] + pct) / 2.0
                
        # To populate untested_diffs, we would ideally cross-reference open PRs.
        # For the baseline analysis report, we'll try to find any recently modified files.
        untested_diffs: list[UntestableDiff] = []
        try:
            # Quick check for open PRs to populate the report
            recent_prs = await self.github.get_open_prs()
            if recent_prs:
                # Just take the latest PR for the global report snippet
                pr_num = recent_prs[0].get("number")
                if pr_num:
                    pr_files = await self.github.get_pr_files(pr_num)
                    untested_diffs = await self.find_untested_diffs(pr_files, coverage_data)
        except Exception as e:
            logger.warning(f"Could not fetch PRs for coverage cross-referencing: {e}")

        # Trend (mock logic: compare against imaginary 7-days-ago data)
        # In reality requires historical DB or second GitHub API call to older commit
        trend = "stable"
        if total_coverage_pct > 80:
            trend = "improving"
        elif total_coverage_pct < 60:
            trend = "declining"

        return CoverageReport(
            total_coverage_pct=round(total_coverage_pct, 2),
            module_coverage={k: round(v, 2) for k, v in module_coverage.items()},
            untested_diffs=untested_diffs,
            trend=trend
        )

    async def find_untested_diffs(self, pr_files: list[dict[str, Any]], coverage_data: dict[str, Any]) -> list[UntestableDiff]:
        """
        Cross-reference changed files in a PR with coverage data to find untested lines.
        """
        untested: list[UntestableDiff] = []
        files_cov = coverage_data.get("files", {})
        
        for f in pr_files:
            filename = f["filename"]
            # Only care about code files
            if not filename.endswith((".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".java")):
                continue
                
            # Skip test files themselves
            if "test" in filename.lower():
                continue
                
            additions = f.get("additions", 0)
            if additions == 0:
                continue

            # Check coverage data for this file
            file_cov = files_cov.get(filename, {})
            pct = file_cov.get("summary", {}).get("percent_covered", 100.0)
            
            # If coverage is missing or less than 100%, we estimate uncovered lines
            # A true implementation would parse the missing line numbers from coverage data 
            # and intersect them with the PR patch line numbers.
            # For this sprint, we estimate based on the file coverage percentage.
            if pct < 100.0 or filename not in files_cov:
                # Heuristic: if entirely absent from coverage, all additions are uncovered
                uncovered = additions if filename not in files_cov else int(additions * ((100.0 - pct) / 100.0))
                
                # Ignore trivial changes
                if uncovered == 0:
                    continue
                    
                # Assess risk
                if "auth" in filename or "security" in filename.lower():
                    risk = "critical — security module"
                elif "app/" in filename or "src/" in filename:
                    risk = "high — core logic"
                else:
                    risk = "medium — standard file"
                    
                untested.append(UntestableDiff(
                    file_path=filename,
                    lines_uncovered=uncovered,
                    risk=risk
                ))
                
        # Sort by risk severity (critical > high > medium > low) and lines uncovered
        severity_map = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        untested.sort(
            key=lambda x: (severity_map.get(x.risk.split(" ")[0], 0), x.lines_uncovered), 
            reverse=True
        )
        return untested

    async def generate_test_task(self, untested_diff: UntestableDiff) -> TaskCreate:
        """
        Generate a TaskCreate object for the Agent HQ orchestrator to write tests.
        """
        # In a deep integration, we'd extract function signatures from the AST.
        # For now, we instruct the agent generally about the file.
        prompt = (
            f"Write comprehensive unit tests for `{untested_diff.file_path}`.\n\n"
            f"This file recently had {untested_diff.lines_uncovered} lines of code added or modified "
            f"without corresponding test coverage. Consider this a {untested_diff.risk} priority.\n"
            f"Please review the logic, identify edge cases, and ensure maximum branch coverage."
        )
        
        return TaskCreate(
            task=prompt,
            engine="claude-code",  # Defaulting to an engine good at coding
            agent_type="test_writer",
            budget_limit=self.settings.BUDGET_LIMIT_PER_TASK,
            context_sources=[untested_diff.file_path]
        )
