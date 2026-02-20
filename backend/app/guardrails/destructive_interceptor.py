"""
backend/app/guardrails/destructive_interceptor.py — Block rm -rf, drop table, etc.

Scans agent output and commands for destructive operations and blocks them
before they can execute, requiring human approval.
"""

from __future__ import annotations

import re
from typing import Optional

from shared.schemas import DestructiveCommand, RiskLevel


# ── Destructive command patterns ─────────────────────────────────────────────

DESTRUCTIVE_PATTERNS: list[tuple[re.Pattern[str], RiskLevel, str]] = [
    (re.compile(r"rm\s+-rf\s+", re.IGNORECASE), RiskLevel.CRITICAL, "Recursive force delete"),
    (re.compile(r"rm\s+-r\s+/", re.IGNORECASE), RiskLevel.CRITICAL, "Recursive delete from root"),
    (re.compile(r"DROP\s+TABLE", re.IGNORECASE), RiskLevel.CRITICAL, "SQL table drop"),
    (re.compile(r"DROP\s+DATABASE", re.IGNORECASE), RiskLevel.CRITICAL, "SQL database drop"),
    (re.compile(r"TRUNCATE\s+TABLE", re.IGNORECASE), RiskLevel.HIGH, "SQL table truncate"),
    (re.compile(r"DELETE\s+FROM\s+\w+\s*;?\s*$", re.IGNORECASE), RiskLevel.HIGH, "SQL delete without WHERE"),
    (re.compile(r"chmod\s+-R\s+777", re.IGNORECASE), RiskLevel.HIGH, "Recursive world-writable permissions"),
    (re.compile(r"git\s+push\s+.*--force", re.IGNORECASE), RiskLevel.HIGH, "Force push to remote"),
    (re.compile(r"git\s+reset\s+--hard", re.IGNORECASE), RiskLevel.MEDIUM, "Hard git reset"),
    (re.compile(r"format\s+[a-zA-Z]:", re.IGNORECASE), RiskLevel.CRITICAL, "Disk format"),
    # TODO: Add more destructive patterns
]


class DestructiveInterceptor:
    """Scans command strings and agent output for destructive operations.

    Attributes:
        blocked_commands: List of commands that were intercepted.
    """

    def __init__(self) -> None:
        self.blocked_commands: list[DestructiveCommand] = []

    def scan(self, task_id: str, text: str) -> Optional[DestructiveCommand]:
        """Scan a text string for destructive commands.

        Args:
            task_id: The task context.
            text: Raw command string or output to scan.

        Returns:
            DestructiveCommand if a dangerous pattern was found, None otherwise.

        TODO:
            - Scan against all DESTRUCTIVE_PATTERNS
            - Return the highest risk match
            - Add to blocked_commands list
            - Emit DESTRUCTIVE_BLOCKED event via WebSocket
        """
        # TODO: Implement pattern scanning
        for pattern, risk_level, reason in DESTRUCTIVE_PATTERNS:
            if pattern.search(text):
                cmd = DestructiveCommand(
                    task_id=task_id,
                    command=text.strip(),
                    risk_level=risk_level,
                    reason=reason,
                )
                self.blocked_commands.append(cmd)
                return cmd
        return None

    def get_blocked_for_task(self, task_id: str) -> list[DestructiveCommand]:
        """Get all blocked commands for a specific task.

        Args:
            task_id: The task to filter for.

        Returns:
            List of DestructiveCommand objects for the task.
        """
        return [cmd for cmd in self.blocked_commands if cmd.task_id == task_id]
