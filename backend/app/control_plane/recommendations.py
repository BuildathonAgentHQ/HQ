"""
Recommendation Engine for Agent HQ Control Plane.

Analyzes inputs from the PR Analyzer, Coverage Analyzer, and Repo Health Analyzer
to generate prioritized, actionable recommendations (NextBestActions) for the user.
Transforms these actions into executable tasks for agents.
"""

from __future__ import annotations

import logging

from backend.app.control_plane.coverage_analyzer import CoverageAnalyzer
from backend.app.control_plane.pr_analyzer import PRAnalyzer
from backend.app.control_plane.repo_health import RepoHealthAnalyzer
from shared.schemas import NextBestAction, TaskCreate

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """Generates next best actions based on repository telemetry."""

    def __init__(
        self,
        pr_analyzer: PRAnalyzer,
        coverage_analyzer: CoverageAnalyzer,
        repo_health_analyzer: RepoHealthAnalyzer,
    ):
        self.pr_analyzer = pr_analyzer
        self.coverage_analyzer = coverage_analyzer
        self.repo_health_analyzer = repo_health_analyzer

    async def generate_recommendations(self) -> list[NextBestAction]:
        """Aggregate data and generate prioritized recommendations."""
        actions: list[NextBestAction] = []

        # We'd fetch all data in a real app (with caching). 
        # Here we just execute the analyzers.
        try:
            # A. From Coverage Analysis
            coverage_report = await self.coverage_analyzer.analyze_coverage()
            
            for module, pct in coverage_report.module_coverage.items():
                if pct < 50.0:
                    actions.append(NextBestAction(
                        action_type="add_tests",
                        description=f"Module '{module}' has low coverage ({pct}%). Dispatch an agent to write unit tests.",
                        target=module,
                        priority="high",
                        estimated_effort="~2 hours"
                    ))
                    
            for untested in coverage_report.untested_diffs:
                priority = "high" if "critical" in untested.risk or "high" in untested.risk else "medium"
                actions.append(NextBestAction(
                    action_type="add_tests",
                    description=f"File '{untested.file_path}' has {untested.lines_uncovered} untested lines added recently. ({untested.risk})",
                    target=untested.file_path,
                    priority=priority,
                    estimated_effort="~1 hour"
                ))

            # B. From PR Analysis
            open_prs = await self.pr_analyzer.github.get_open_prs()
            
            # Analyze each PR
            # For efficiency and to avoid giant rate limits, we analyze just recent ones
            for pr in open_prs[:5]:
                pr_num = pr.get("number")
                if not pr_num:
                    continue
                    
                files = await self.pr_analyzer.github.get_pr_files(pr_num)
                # dummy diff
                risk_score = await self.pr_analyzer.analyze_pr(pr, files, "")
                
                if risk_score.risk_score > 75:
                    actions.append(NextBestAction(
                        action_type="split_pr",
                        description=f"PR #{pr_num} ('{risk_score.title}') is massive and touches core files. Consider asking the author to split it.",
                        target=f"PR #{pr_num}",
                        priority="high",
                        estimated_effort="~30 min (human review)"
                    ))
                    
            dependencies = await self.pr_analyzer.detect_dependencies(open_prs)
            for pr_num, conflicts in dependencies.items():
                if conflicts:
                    joined_conflicts = ", #".join(map(str, conflicts))
                    actions.append(NextBestAction(
                        action_type="refactor",
                        description=f"PR #{pr_num} modifies the exact same files as PR #{joined_conflicts}. Potential merge conflicts imminent.",
                        target=f"PR #{pr_num}",
                        priority="medium",
                        estimated_effort="~15 min (communication)"
                    ))

            # C. From Repo Health
            health_report = await self.repo_health_analyzer.analyze_health()
            
            for flaky in health_report.flaky_tests:
                actions.append(NextBestAction(
                    action_type="fix_flaky",
                    description=f"Test '{flaky}' failed intermittently in recent CI runs. Needs stabilization.",
                    target=flaky,
                    priority="high",
                    estimated_effort="~2 hours"
                ))
                
            for hot_file in health_report.hot_files:
                # Check if hot file has low coverage
                cov_pct = coverage_report.module_coverage.get(hot_file.path, 100.0)
                if cov_pct < 80.0:
                    actions.append(NextBestAction(
                        action_type="refactor",
                        description=f"'{hot_file.path}' is a hot file (changed {hot_file.change_count_30d} times) with lacking coverage. High regression risk.",
                        target=hot_file.path,
                        priority="high",
                        estimated_effort="~4 hours"
                    ))
                    
            for debt in health_report.tech_debt_items:
                if debt.age_days > 90 and debt.severity == "high":
                    actions.append(NextBestAction(
                        action_type="refactor",
                        description=f"Stale high-severity debt: '{debt.description}' ({debt.age_days} days old). Dispatch agent to refactor.",
                        target="repository_core", # mock target
                        priority="medium",
                        estimated_effort="~3 hours"
                    ))

            # D. General (Mock)
            # Documentation update check
            actions.append(NextBestAction(
                action_type="update_docs",
                description="The core architecture documentation (README.md, docs/) hasn't been updated in 30 days despite code churn.",
                target="docs/",
                priority="low",
                estimated_effort="~1 hour"
            ))

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")

        # Sort recommendations
        # Priority: high > medium > low
        # Then we'll just leave it the order we added them for impact
        priority_map = {"high": 3, "medium": 2, "low": 1}
        actions.sort(key=lambda x: priority_map.get(x.priority, 0), reverse=True)
        
        # Return top 10
        return actions[:10]

    async def create_agent_task(self, action: NextBestAction) -> TaskCreate:
        """Convert a recommendation into an executable TaskCreate payload."""
        
        # Determine agent type based on action type
        agent_type_map = {
            "add_tests": "test_writer",
            "refactor": "refactor",
            "update_docs": "doc",
            "split_pr": "general",
            "fix_flaky": "test_writer",
        }
        agent_type = agent_type_map.get(action.action_type, "general")
        
        # Create natural language task
        if action.action_type == "add_tests":
            prompt = f"Write unit tests for `{action.target}`. Note: {action.description}"
        elif action.action_type == "fix_flaky":
            prompt = f"Investigate and fix the flaky test `{action.target}`. Ensure it passes deterministically in CI."
        elif action.action_type == "refactor":
            prompt = f"Refactor `{action.target}` to address the following issue: {action.description}"
        elif action.action_type == "update_docs":
            prompt = f"Review the recent git history and update the documentation in `{action.target}` to reflect architecture changes."
        else:
            prompt = f"Address this priority action item: {action.description} on {action.target}"
            
        return TaskCreate(
            task=prompt,
            engine="claude-code", # Best engine for general coding 
            agent_type=agent_type,
            budget_limit=2.5, # Slightly higher budget for autonomous fixes
            context_sources=[action.target]
        )
