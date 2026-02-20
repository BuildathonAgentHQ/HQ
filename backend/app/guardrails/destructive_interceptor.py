"""
backend/app/guardrails/destructive_interceptor.py — Catches dangerous commands.

Uses regex heuristics to intercept potentially destructive shell or SQL commands
(like rm -rf, drop table, git reset --hard) and immediately suspends the task,
forwarding an ApprovalRequest to the user before execution.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from shared.schemas import ApprovalRequest

logger = logging.getLogger(__name__)


class DestructiveActionInterceptor:
    """Scans raw agent commands for destructive intent."""

    def __init__(self) -> None:
        # Define dangerous patterns and their corresponding plain-English explanations.
        # This maps compiled regex -> informative warning text.
        self.DANGEROUS_PATTERNS: list[tuple[re.Pattern, str]] = [
            (
                re.compile(r"rm\s+-r?[fF][rR]?\s+.*", re.IGNORECASE),
                "The agent wants to forcibly and permanently delete files or directories. This cannot be undone."
            ),
            (
                re.compile(r"rm\s+-r\s+.*(?:/|~).*", re.IGNORECASE),
                "The agent wants to recursively delete a substantial directory (like a root or home folder). This cannot be undone."
            ),
            (
                re.compile(r"drop\s+(table|database)\s+\w+", re.IGNORECASE),
                "The agent wants to completely destroy a database table or entire database schema. All data will be permanently wiped."
            ),
            (
                re.compile(r"truncate\s+table\s+\w+", re.IGNORECASE),
                "The agent wants to instantly wipe all rows from a database table without logging individual deletions. The structure remains but data is lost."
            ),
            (
                re.compile(r"git\s+push\s+(?:--force|-f)", re.IGNORECASE),
                "The agent wants to forcefully overwrite the remote Git repository branch. This can permanently destroy commit history and other peoples' work."
            ),
            (
                re.compile(r"git\s+reset\s+--hard", re.IGNORECASE),
                "The agent wants to permanently discard all uncommitted changes in your repository. Any unsaved code will be lost."
            ),
            (
                re.compile(r"delete\s+from\s+\w+(?:\s+where\s+1\s*=\s*1)?\s*(?:;|$)", re.IGNORECASE),
                "The agent wants to delete rows from a database table without a specific filter. This could unintentionally wipe the entire table."
            ),
            (
                re.compile(r"chmod\s+(?:-[Rfv]\s+)?777\s+.*", re.IGNORECASE),
                "The agent wants to make a file or directory completely public (read/write/execute for anyone). This is a severe security vulnerability."
            ),
            (
                re.compile(r"dd\s+if=.*", re.IGNORECASE),
                "The agent wants to execute a low-level disk copy command. Incorrect usage can instantly overwrite and destroy fundamental system partitions."
            ),
            (
                re.compile(r"mkfs\..*", re.IGNORECASE),
                "The agent wants to format a disk partition. This will instantly wipe all existing data on the target drive."
            ),
            (
                re.compile(r"sudo\s+.*(?:etc|usr|var|bin|sbin|boot|lib).*", re.IGNORECASE),
                "The agent wants to use administrator privileges to modify critical system directories. This could break your operating system."
            )
        ]

    async def scan_command(self, task_id: str, command: str) -> Optional[ApprovalRequest]:
        """Check the command against all DANGEROUS_PATTERNS.
        
        Args:
            task_id: The ID of the task trying to execute the action.
            command: The raw shell or SQL command.
            
        Returns:
            ApprovalRequest if the command is dangerous, else None.
        """
        for pattern, description in self.DANGEROUS_PATTERNS:
            if pattern.search(command):
                logger.warning(f"Task {task_id}: Blocked destructive command: '{command}'")
                return ApprovalRequest(
                    task_id=task_id,
                    action_type="destructive_cmd",
                    command=command,
                    description=description,
                    options=[
                        "Approve — execute this command",
                        "Reject — cancel and try alternative"
                    ]
                )
                
        return None
