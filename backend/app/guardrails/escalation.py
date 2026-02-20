"""
backend/app/guardrails/escalation.py — Guardrail Strike Tracker & Debate Trigger.

Tracks consecutive guardrail failures for an agent. If the agent fails three
times in a row, the primary agent is suspended, and a secondary review agent
is spawned to "debate" the failure, triggering a human-in-the-loop approval.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.app.orchestrator.process_manager import ProcessManager
from shared.events import EventType, create_ws_event
from shared.schemas import ApprovalRequest, DebateOption, DebateResult, GuardrailEvent

logger = logging.getLogger(__name__)


class EscalationManager:
    """Tracks guardrail strikes and triggers agent debates on repeated failures."""

    def __init__(self, process_manager: ProcessManager, event_router: Any) -> None:
        self.process_manager = process_manager
        self.event_router = event_router
        # Tracks the number of consecutive failed checks per task
        self._strikes: dict[str, int] = {}

    async def handle_guardrail_success(self, task_id: str) -> None:
        """Reset the strike count upon a successful code check."""
        if self._strikes.get(task_id, 0) > 0:
            logger.info(f"Task {task_id} passed guardrails. Resetting strikes to 0.")
            self._strikes[task_id] = 0

    async def handle_guardrail_failure(self, task_id: str, event: GuardrailEvent) -> None:
        """Increment strike count. Inject fix-it prompt or escalate to debate."""
        current_strikes = self._strikes.get(task_id, 0) + 1
        self._strikes[task_id] = current_strikes
        
        logger.warning(f"Task {task_id} failed a guardrail check ({event.check_type}). Strike {current_strikes}/3.")

        if current_strikes < 3:
            # Auto-remediation attempt: Instruct the agent to fix it
            fix_prompt = (
                f"Your last change failed the {event.check_type} check. "
                f"The error was: {event.error_msg}. Please fix this issue immediately."
            )
            
            try:
                # Inject the failure directly into the agent's PTY
                await self.process_manager.inject_prompt(task_id, fix_prompt)
                logger.info(f"Injected Guardrail fix-it prompt into Task {task_id}.")
                
                # Emit generic guardrail WebSocket event containing strike info
                # Note: We don't spam the UI with every syntax error; we just record it.
                ws_event = create_ws_event(
                    task_id=task_id,
                    event_type=EventType.GUARDRAIL_TRIGGERED,
                    payload={
                        "task_id": task_id,
                        "file_path": event.file_path,
                        "check_type": event.check_type,
                        "passed": False,
                        "error_msg": event.error_msg,
                        "strike_count": current_strikes,
                    }
                )
                await self.event_router.emit(ws_event)
                
            except KeyError:
                logger.error(f"Cannot inject prompt: Task {task_id} is not running.")
                
        else:
            # Escalation triggered (3 strikes)
            logger.error(f"Task {task_id} hit 3 consecutive guardrail strikes. Escalating...")
            
            # 1. Suspend the primary agent
            try:
                await self.process_manager.suspend_process(task_id)
            except KeyError:
                pass
                
            # 2. Inform the frontend
            ws_event = create_ws_event(
                task_id=task_id,
                event_type=EventType.DEBATE_STARTED,
                payload={
                    "message": "Agent has failed 3 consecutive lint checks. Spawning second opinion..."
                }
            )
            await self.event_router.emit(ws_event)
            
            # 3. Spawn background task to conduct the debate
            loop = asyncio.get_running_loop()
            loop.create_task(self.trigger_debate(task_id, event))

    async def trigger_debate(self, task_id: str, last_event: GuardrailEvent) -> None:
        """Spawn a secondary review agent, summarize findings, and request user approval."""
        logger.info(f"Starting secondary Debate Agent for failed task {task_id}...")
        
        # 1. Gather context (Normally you might run `git diff` here to get the uncommitted changes)
        # For this sprint simulation, we will construct a direct prompt about the broken file:
        prompt = (
            f"Review the code change in {last_event.file_path} and explain precisely why it might "
            f"be failing the {last_event.check_type} check with this error: {last_event.error_msg}."
        )
        
        # 2. Spawn the secondary agent using subprocess for an independent analysis (using claude-code)
        try:
            process = await asyncio.create_subprocess_exec(
                "claude", "-p", prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            stdout, _ = await process.communicate()
            secondary_output = stdout.decode("utf-8").strip() if stdout else "Secondary agent failed to respond."
        except Exception as e:
            logger.error(f"Failed to execute secondary debate agent: {e}")
            secondary_output = "Fallback: Syntactical divergence detected. Manual intervention strictly required."

        # 3. Simulate translation layer summarization
        debate_summary = (
            f"The primary agent repeatedly failed automated checks in {last_event.file_path}. "
            f"The secondary review agent notes:\n{secondary_output[:300]}..."
        )
        
        # 4. Create the DebateResult schema
        debate_result = DebateResult(
            task_id=task_id,
            agent_a_position=f"The primary agent attempted to edit {last_event.file_path} but introduced a recurring syntax/linting error ({last_event.error_msg}).",
            agent_b_position=secondary_output[:500],
            summary=debate_summary,
            options=[
                DebateOption(
                    label="Resume Primary Agent",
                    description="Allow the original agent to try fixing it one more time.",
                    recommended_by="Primary Agent"
                ),
                DebateOption(
                    label="Revert Changes & Use Alternate Approach",
                    description="Revert the broken file and instruct the agent to try a completely different strategy.",
                    recommended_by="Secondary Review Agent"
                )
            ]
        )
        
        # 5. Format to an ApprovalRequest for the Human-in-the-loop Gate
        approval_req = ApprovalRequest(
            task_id=task_id,
            action_type="debate_resolution",
            command=None,
            description=debate_summary,
            options=[opt.label for opt in debate_result.options]
        )
        
        # 6. Push the debate approval to the Event Router / Gate
        # In a real flow, this hooks into your ApprovalGate or emits a specific WS event.
        ws_event = create_ws_event(
            task_id=task_id,
            event_type=EventType.APPROVAL_REQUIRED,
            payload=approval_req.model_dump(mode="json")
        )
        await self.event_router.emit(ws_event)
