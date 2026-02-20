"""
backend/app/guardrails/approval_gate.py — Manages paused tasks awaiting human approval.

Holds ApprovalRequests dynamically in memory while tasks are paused, allowing
the API/WebSocket routes to query statuses or resolve actions.
"""

from __future__ import annotations

import logging
from typing import Optional

from shared.schemas import ApprovalRequest

logger = logging.getLogger(__name__)


class ApprovalGate:
    """Manages the state of tasks paused for human-in-the-loop review."""

    def __init__(self) -> None:
        # Maps task_id -> ApprovalRequest object
        self._pending_approvals: dict[str, ApprovalRequest] = {}

    def add_pending(self, task_id: str, request: ApprovalRequest) -> None:
        """Store the approval request and mark the task as explicitly paused.
        
        Note: The actual pausing of the async task happens in the Engine Runner
        after this yields the payload to the frontend.
        """
        self._pending_approvals[task_id] = request
        logger.info(f"Task {task_id} paused awaiting human approval for: {request.action_type}")

    def resolve(self, task_id: str, option: str) -> Optional[str]:
        """Remove the task from pending and return the user's choice.
        
        Args:
            task_id: The ID of the pending task.
            option: The chosen resolution string (e.g. 'Approve', 'Reject').
            
        Returns:
            The chosen option string if the task was found, else None.
        """
        if task_id in self._pending_approvals:
            del self._pending_approvals[task_id]
            logger.info(f"Task {task_id} approval resolved with: '{option}'")
            return option
            
        logger.warning(f"Attempted to resolve task {task_id} but no pending approval was found.")
        return None

    def get_pending(self, task_id: str) -> Optional[ApprovalRequest]:
        """Check if a specific task has a pending approval."""
        return self._pending_approvals.get(task_id)
