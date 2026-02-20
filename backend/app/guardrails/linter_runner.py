"""
backend/app/guardrails/linter_runner.py — ruff/eslint/bandit execution.

Runs lint tools against files changed by agents and reports results
via the WebSocket event stream.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from shared.schemas import LintResult


class LinterRunner:
    """Executes linting tools and parses their output.

    Supports ruff (Python), eslint (JS/TS), and bandit (Python security).
    """

    async def run_ruff(self, file_path: str, task_id: str) -> LintResult:
        """Run ruff linter on a Python file.

        Args:
            file_path: Path to the Python file to lint.
            task_id: The task that produced the file change.

        Returns:
            LintResult with parsed issues.

        TODO:
            - Execute `ruff check --output-format=json <file_path>`
            - Parse JSON output into LintIssue objects
            - Emit LINT_RESULT event via WebSocket
        """
        # TODO: Implement ruff execution
        raise NotImplementedError("LinterRunner.run_ruff not yet implemented")

    async def run_eslint(self, file_path: str, task_id: str) -> LintResult:
        """Run eslint on a JavaScript/TypeScript file.

        Args:
            file_path: Path to the JS/TS file to lint.
            task_id: The task that produced the file change.

        Returns:
            LintResult with parsed issues.

        TODO:
            - Execute `npx eslint --format=json <file_path>`
            - Parse JSON output into LintIssue objects
            - Emit LINT_RESULT event via WebSocket
        """
        # TODO: Implement eslint execution
        raise NotImplementedError("LinterRunner.run_eslint not yet implemented")

    async def run_bandit(self, file_path: str, task_id: str) -> LintResult:
        """Run bandit security linter on a Python file.

        Args:
            file_path: Path to the Python file to scan.
            task_id: The task that produced the file change.

        Returns:
            LintResult with security issues.

        TODO:
            - Execute `bandit -f json <file_path>`
            - Parse JSON output into LintIssue objects
            - Emit LINT_RESULT event with severity info
        """
        # TODO: Implement bandit execution
        raise NotImplementedError("LinterRunner.run_bandit not yet implemented")

    async def lint_file(self, file_path: str, task_id: str) -> list[LintResult]:
        """Auto-detect file type and run appropriate linters.

        Args:
            file_path: Path to the file to lint.
            task_id: The task context.

        Returns:
            List of LintResult objects from all applicable linters.

        TODO:
            - Detect file extension (.py → ruff + bandit, .ts/.tsx → eslint)
            - Run applicable linters concurrently
            - Aggregate results
        """
        # TODO: Implement auto-detection and concurrent linting
        return []
