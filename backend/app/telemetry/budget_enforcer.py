"""
backend/app/telemetry/budget_enforcer.py — $2/task hard limit enforcement.

Monitors token costs and terminates agent processes that exceed their
budget allocation.
"""

from __future__ import annotations

from typing import Optional

from shared.schemas import BudgetAlert, Task, TokenUsage


class BudgetEnforcer:
    """Enforces per-task budget limits and emits alerts.

    Attributes:
        warning_threshold: Percentage of budget at which to warn (default 0.8 = 80%).
        alerts: List of emitted BudgetAlert objects.
    """

    def __init__(self, warning_threshold: float = 0.8) -> None:
        self.warning_threshold = warning_threshold
        self.alerts: list[BudgetAlert] = []

    def check_budget(self, task: Task, current_usage: TokenUsage) -> Optional[BudgetAlert]:
        """Check if a task's cost is approaching or exceeding its budget.

        Args:
            task: The Task with budget_limit.
            current_usage: Current TokenUsage with estimated_cost_usd.

        Returns:
            BudgetAlert if warning threshold crossed or budget exceeded,
            None if within budget.

        TODO:
            - Compare current_usage.estimated_cost_usd against task.budget_limit
            - Emit BUDGET_WARNING at warning_threshold
            - Emit BUDGET_EXCEEDED and trigger task termination at limit
            - Store alert in self.alerts
        """
        # TODO: Implement budget checking
        raise NotImplementedError("BudgetEnforcer.check_budget not yet implemented")

    async def enforce(self, task: Task, current_usage: TokenUsage) -> bool:
        """Enforce the budget limit, potentially terminating the task.

        Args:
            task: The Task to enforce budget on.
            current_usage: Current token usage.

        Returns:
            True if the task should continue, False if it should be terminated.

        TODO:
            - Call check_budget()
            - If exceeded, trigger ProcessManager.terminate(task.id)
            - Emit BUDGET_EXCEEDED event via WebSocket
        """
        # TODO: Implement enforcement
        raise NotImplementedError("BudgetEnforcer.enforce not yet implemented")

    def get_alerts_for_task(self, task_id: str) -> list[BudgetAlert]:
        """Get all budget alerts for a specific task.

        Args:
            task_id: The task to filter for.

        Returns:
            List of BudgetAlert objects for the task.
        """
        return [a for a in self.alerts if a.task_id == task_id]
