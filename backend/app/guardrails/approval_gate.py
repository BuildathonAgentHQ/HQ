"""
backend/app/guardrails/approval_gate.py — Approval event emission.

Manages the human-in-the-loop approval workflow for destructive operations.
Pauses agent execution until a human approves or rejects the action.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from shared.schemas import ApprovalRequest, ApprovalResponse, ApprovalStatus, RiskLevel


class ApprovalGate:
    """Manages pending approval requests and their resolution.

    Attributes:
        pending: Dict mapping request_id → ApprovalRequest.
        _events: Dict mapping request_id → asyncio.Event for waiting.
    """

    def __init__(self) -> None:
        self.pending: dict[str, ApprovalRequest] = {}
        self._events: dict[str, asyncio.Event] = {}
        self._responses: dict[str, ApprovalResponse] = {}

    async def request_approval(
        self,
        task_id: str,
        action: str,
        risk_level: RiskLevel,
        command: Optional[str] = None,
        timeout: float = 300.0,
    ) -> ApprovalResponse:
        """Create an approval request and wait for human response.

        This method blocks (async) until the human approves, rejects,
        or the request times out.

        Args:
            task_id: The task requiring approval.
            action: Description of the action needing approval.
            risk_level: Risk classification of the action.
            command: Optional raw command string.
            timeout: Seconds to wait before auto-rejecting (default 5 min).

        Returns:
            ApprovalResponse with the human's decision.

        TODO:
            - Create ApprovalRequest and store in pending
            - Emit APPROVAL_REQUIRED event via WebSocket
            - Wait on asyncio.Event with timeout
            - Handle timeout as auto-rejection
            - Clean up on resolution
        """
        # TODO: Implement approval request flow
        raise NotImplementedError("ApprovalGate.request_approval not yet implemented")

    async def resolve(self, response: ApprovalResponse) -> Optional[ApprovalRequest]:
        """Resolve a pending approval request.

        Args:
            response: ApprovalResponse from the frontend.

        Returns:
            The resolved ApprovalRequest, or None if not found.

        TODO:
            - Update ApprovalRequest status to APPROVED or REJECTED
            - Store response and set the asyncio.Event
            - Emit APPROVAL_RESOLVED event via WebSocket
        """
        # TODO: Implement resolution
        raise NotImplementedError("ApprovalGate.resolve not yet implemented")

    def get_pending(self, task_id: Optional[str] = None) -> list[ApprovalRequest]:
        """List pending approval requests.

        Args:
            task_id: Optional filter by task ID.

        Returns:
            List of pending ApprovalRequest objects.
        """
        requests = list(self.pending.values())
        if task_id:
            requests = [r for r in requests if r.task_id == task_id]
        return requests
