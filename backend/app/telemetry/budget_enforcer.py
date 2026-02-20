"""
backend/app/telemetry/budget_enforcer.py — $2/task hard-limit enforcement.

Monitors token costs in real-time and gates agent execution when spending
approaches or exceeds the per-task budget.

Three zones:
    1. **Green** (< 80 % budget) — continue normally.
    2. **Warning** (≥ 80 %) — emit a warning event, continue.
    3. **Exceeded** (≥ 100 %) — suspend the process, emit
       ``budget_exceeded`` + ``ApprovalRequest``, pause until the user
       responds.
"""

from __future__ import annotations

import logging
from typing import Any

from shared.events import EventType, create_ws_event
from shared.schemas import ApprovalRequest

logger = logging.getLogger(__name__)


class BudgetEnforcer:
    """Enforces per-task budget limits and gates agent execution.

    Parameters
    ----------
    process_manager:
        ``ProcessManager`` instance used to suspend / resume / kill
        agent subprocesses.
    event_router:
        ``EventRouter`` singleton for emitting WebSocket events.
    default_limit:
        Fall-back budget in USD when the task has no explicit limit.
    """

    def __init__(
        self,
        process_manager: Any,
        event_router: Any,
        default_limit: float = 2.0,
    ) -> None:
        self._pm = process_manager
        self._router = event_router
        self.default_limit = default_limit

        # task_id → effective budget limit (can be increased via add_funds)
        self._limits: dict[str, float] = {}

    # ── Budget check ─────────────────────────────────────────────────────

    async def check_budget(
        self,
        task_id: str,
        current_cost: float,
        budget_limit: float | None = None,
    ) -> bool:
        """Check whether the task is still within budget.

        Parameters
        ----------
        task_id:
            UUID of the task.
        current_cost:
            Cumulative USD spent so far.
        budget_limit:
            Explicit limit for this task.  Falls back to any previously
            stored limit, then to ``self.default_limit``.

        Returns
        -------
        bool
            ``True`` if the task may continue, ``False`` if it has been
            suspended due to budget exhaustion.
        """
        limit = budget_limit or self._limits.get(task_id, self.default_limit)
        self._limits[task_id] = limit

        # ── Exceeded ─────────────────────────────────────────────────
        if current_cost >= limit:
            logger.warning(
                "Task %s exceeded budget ($%.4f / $%.2f) — suspending",
                task_id,
                current_cost,
                limit,
            )

            # Suspend the agent process
            try:
                self._pm.suspend_process(task_id)
            except (KeyError, Exception):
                logger.warning(
                    "Could not suspend process for task %s", task_id, exc_info=True,
                )

            # Emit budget_exceeded event
            overage = round(current_cost - limit, 4)
            await self._router.emit_budget_exceeded(
                task_id=task_id,
                payload={
                    "task_id": task_id,
                    "current_cost": round(current_cost, 4),
                    "budget_limit": limit,
                    "overage": overage,
                },
            )

            # Create an approval request so the UI can prompt the user
            approval = ApprovalRequest(
                task_id=task_id,
                action_type="budget_overrun",
                description=(
                    f"Task has spent ${current_cost:.4f} of its "
                    f"${limit:.2f} budget (${overage:.4f} over). "
                    "Approve additional funds or terminate the task."
                ),
                options=["add_funds", "terminate"],
            )
            await self._router.emit(
                create_ws_event(
                    task_id,
                    EventType.APPROVAL_REQUIRED,
                    approval.model_dump(),
                )
            )

            return False

        # ── Warning (≥ 80 %) ─────────────────────────────────────────
        if current_cost >= limit * 0.8:
            pct = round((current_cost / limit) * 100, 1)
            logger.info(
                "Task %s at %s%% of budget ($%.4f / $%.2f)",
                task_id,
                pct,
                current_cost,
                limit,
            )
            await self._router.emit_status_update(
                task_id=task_id,
                payload={
                    "status": f"Budget warning: {pct}% consumed (${current_cost:.4f} / ${limit:.2f})",
                    "is_error": False,
                    "severity": "warning",
                    "category": "waiting",
                },
            )
            return True

        # ── Green ────────────────────────────────────────────────────
        return True

    # ── User responses ───────────────────────────────────────────────────

    async def handle_budget_response(self, task_id: str, action: str) -> None:
        """Handle the user's response to a budget-exceeded prompt.

        Parameters
        ----------
        task_id:
            UUID of the suspended task.
        action:
            ``"add_funds"`` — increase the limit by $2.00 and resume.
            ``"terminate"`` — kill the process.
        """
        if action == "add_funds":
            old_limit = self._limits.get(task_id, self.default_limit)
            new_limit = old_limit + 2.0
            self._limits[task_id] = new_limit
            logger.info(
                "Task %s budget raised from $%.2f → $%.2f — resuming",
                task_id,
                old_limit,
                new_limit,
            )

            try:
                self._pm.resume_process(task_id)
            except (KeyError, Exception):
                logger.warning(
                    "Could not resume process for task %s", task_id, exc_info=True,
                )

            await self._router.emit_status_update(
                task_id=task_id,
                payload={
                    "status": f"Budget increased to ${new_limit:.2f} — resuming",
                    "is_error": False,
                    "severity": "info",
                    "category": "waiting",
                },
            )

        elif action == "terminate":
            logger.info("Task %s terminated by user after budget overrun", task_id)
            try:
                self._pm.kill_process(task_id)
            except (KeyError, Exception):
                logger.warning(
                    "Could not kill process for task %s", task_id, exc_info=True,
                )

            await self._router.emit_status_update(
                task_id=task_id,
                payload={
                    "status": "Task terminated — budget exceeded",
                    "is_error": True,
                    "severity": "error",
                    "category": "completed",
                },
            )
        else:
            logger.warning(
                "Unknown budget response action '%s' for task %s", action, task_id,
            )
