"""
backend/app/guardrails/linter_runner.py — Executes code linting and security checks.

Runs ruff, bandit, or eslint depending on the file extension and formats the
output into a precise error message that the agent can read and fix.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from shared.schemas import GuardrailEvent

logger = logging.getLogger(__name__)


class LinterRunner:
    """Executes subprocess linters and parses the output for GuardrailEvents."""

    def __init__(self) -> None:
        pass

    async def _run_subprocess(self, cmd: list[str]) -> tuple[int, str]:
        """Run a shell command asynchronously and return (returncode, stdout)."""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            stdout, _ = await process.communicate()
            output = stdout.decode("utf-8").strip() if stdout else ""
            return process.returncode or 0, output
        except FileNotFoundError:
            tool = cmd[0]
            logger.warning(f"Linter '{tool}' not found. Skipping.")
            return 0, ""
        except Exception as e:
            logger.error(f"Error executing {cmd}: {e}")
            return 0, ""

    def _extract_first_error(self, tool: str, output: str) -> str:
        """Extract a clean, readable error directly from the output."""
        lines = [line.strip() for line in output.split("\n") if line.strip()]
        if not lines:
            return f"{tool}: Unknown error"
            
        # Return the first meaningful line containing the failure info
        for line in lines:
            # Skip summary/header lines if obvious
            if line.startswith("Summary") or line.startswith("Run started"):
                continue
            return f"{tool}: {line}"
            
        return f"{tool}: {lines[0]}"

    async def run_checks(self, file_path: str) -> GuardrailEvent:
        """Run the appropriate linters and return a single aggregate event.
        
        Returns exactly ONE GuardrailEvent representing the worst outcome:
        if ANY check fails, returns passed=False with the first error.
        If all pass, returns passed=True.
        """
        path = Path(file_path)
        ext = path.suffix.lower()
        
        # We need a fallback task_id since this might run orthogonally
        task_id = "janitor_background_lint"

        if ext == ".py":
            # 1. Ruff
            code, ruff_out = await self._run_subprocess(["ruff", "check", file_path])
            if code != 0 and ruff_out:
                msg = self._extract_first_error("ruff", ruff_out)
                return GuardrailEvent(
                    task_id=task_id, file_path=file_path, check_type="lint",
                    passed=False, error_msg=msg, strike_count=1
                )
                
            # 2. Bandit
            code, bandit_out = await self._run_subprocess(["bandit", "-r", file_path, "-f", "custom", "--msg-template", "{line}: {test_id} {msg}"])
            if code != 0 and bandit_out:
                msg = self._extract_first_error("bandit", bandit_out)
                return GuardrailEvent(
                    task_id=task_id, file_path=file_path, check_type="security",
                    passed=False, error_msg=msg, strike_count=1
                )

        elif ext in (".js", ".ts", ".jsx", ".tsx"):
            # Node / Frontend linting
            # For this sprint we assume we are running eslint in the current relative context
            code, eslint_out = await self._run_subprocess(["npx", "eslint", file_path])
            if code != 0 and eslint_out:
                msg = self._extract_first_error("eslint", eslint_out)
                return GuardrailEvent(
                    task_id=task_id, file_path=file_path, check_type="lint",
                    passed=False, error_msg=msg, strike_count=1
                )

        # Base case: Everything passed
        return GuardrailEvent(
            task_id=task_id,
            file_path=file_path,
            check_type="lint",
            passed=True,
            error_msg="",
            strike_count=0
        )
