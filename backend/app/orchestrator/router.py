"""
backend/app/orchestrator/router.py — Task CRUD + agent lifecycle endpoints.

Mounted at ``/api/tasks`` in ``main.py``.  Routes are wired to the real
``TaskManager`` and ``ProcessManager``.  The ``ProcessManager`` gracefully
falls back when engine binaries are unavailable (dev machines).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from shared.events import EventType
from shared.schemas import GuardrailEvent, Task, TaskCreate, WebSocketEvent
from backend.app.guardrails.escalation import EscalationManager

from backend.app.orchestrator.task_manager import TaskManager
from backend.app.orchestrator.process_manager import ProcessManager
from backend.app.websocket.events import event_router

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Module-level singletons (created once at import time) ───────────────────
task_manager = TaskManager(seed_mock=True)
process_manager = ProcessManager(event_router=event_router)
escalation_manager = EscalationManager(process_manager=process_manager, event_router=event_router)

async def _on_guardrail_triggered(ws_event: WebSocketEvent) -> None:
    """Invoked globally when the JanitorWatcher emits a guardrail event."""
    try:
        ge = GuardrailEvent(**ws_event.payload)
        if ge.passed:
            await escalation_manager.handle_guardrail_success(ge.task_id)
        else:
            await escalation_manager.handle_guardrail_failure(ge.task_id, ge)
    except Exception as e:
        logger.error(f"Failed to process guardrail event in orchestrator: {e}")

event_router.register_handler(EventType.GUARDRAIL_TRIGGERED, _on_guardrail_triggered)



# ═══════════════════════════════════════════════════════════════════════════════
#  CRUD endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/", response_model=Task)
async def create_task(payload: TaskCreate) -> Task:
    """Create a new agent task and optionally spawn the agent process."""
    task = task_manager.create_task(payload)
    logger.info("Task created: %s (engine=%s)", task.id, task.engine)

    # Try to spawn the agent — but don't fail the API call if the
    # engine binary isn't installed.
    try:
        logger.info("Attempting to spawn agent for task %s...", task.id)
        await process_manager.spawn_agent(task)
        task = task_manager.update_task(task.id, status="running") or task
        logger.info("Agent spawned successfully for task %s (status=%s)", task.id, task.status)
    except FileNotFoundError:
        logger.warning(
            "Engine '%s' not found on PATH — task %s stays pending.",
            task.engine, task.id,
        )
    except Exception:
        logger.exception("Failed to spawn agent for task %s", task.id)

    return task


@router.get("/", response_model=list[Task])
async def list_tasks() -> list[Task]:
    """List all tasks, sorted by creation date (newest first)."""
    return task_manager.list_tasks()


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: str) -> Task:
    """Get a single task by ID.

    Raises:
        HTTPException 404: if the task does not exist.
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


@router.delete("/{task_id}")
async def cancel_task(task_id: str) -> dict[str, str]:
    """Cancel / kill a running task.

    If the task has an active process, it is killed via SIGTERM/SIGKILL.
    The task status is set to ``"failed"``.

    Raises:
        HTTPException 404: if the task does not exist.
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    # Kill the process if running
    if task_id in process_manager.active_processes:
        try:
            await process_manager.kill_process(task_id)
        except Exception:
            logger.exception("Error killing process for task %s", task_id)

    task_manager.update_task(task_id, status="failed")
    return {"status": "cancelled", "task_id": task_id}


# ═══════════════════════════════════════════════════════════════════════════════
#  Agent lifecycle endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/{task_id}/approve")
async def approve_action(task_id: str, option: str = "Approve") -> dict[str, str]:
    """Respond to a human-in-the-loop approval request.

    If the agent process is active, the approval response is injected
    into its PTY stdin so the CLI tool can act on it.

    Args:
        task_id: UUID of the task.
        option: The chosen approval option (e.g. ``"Approve"``).

    Raises:
        HTTPException 404: if the task does not exist.
    """
    if not task_manager.get_task(task_id):
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    # Inject the approval response into the running agent
    if task_id in process_manager.active_processes:
        try:
            await process_manager.inject_prompt(task_id, option)
        except Exception:
            logger.exception("Failed to inject approval for task %s", task_id)

    return {"status": "approved", "task_id": task_id, "option": option}


@router.post("/{task_id}/suspend")
async def suspend_task(task_id: str) -> dict[str, str]:
    """Suspend a running task (SIGSTOP).

    Raises:
        HTTPException 404: if the task does not exist.
        HTTPException 409: if the task has no active process.
    """
    if not task_manager.get_task(task_id):
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    if task_id not in process_manager.active_processes:
        raise HTTPException(status_code=409, detail="Task has no active process")

    await process_manager.suspend_process(task_id)
    task_manager.update_task(task_id, status="suspended")
    return {"status": "suspended", "task_id": task_id}


@router.post("/{task_id}/resume")
async def resume_task(task_id: str) -> dict[str, str]:
    """Resume a suspended task (SIGCONT).

    Raises:
        HTTPException 404: if the task does not exist.
        HTTPException 409: if the task has no active process.
    """
    if not task_manager.get_task(task_id):
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    if task_id not in process_manager.active_processes:
        raise HTTPException(status_code=409, detail="Task has no active process")

    await process_manager.resume_process(task_id)
    task_manager.update_task(task_id, status="running")
    return {"status": "running", "task_id": task_id}


@router.post("/{task_id}/inject")
async def inject_prompt(task_id: str, prompt: str) -> dict[str, str]:
    """Inject a prompt into a running agent's PTY stdin.

    This is used by the Janitor Protocol to send fix-it commands.

    Args:
        task_id: UUID of the task.
        prompt: Text to inject.

    Raises:
        HTTPException 404: if the task does not exist.
        HTTPException 409: if the task has no active process.
    """
    if not task_manager.get_task(task_id):
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    if task_id not in process_manager.active_processes:
        raise HTTPException(status_code=409, detail="Task has no active process")

    await process_manager.inject_prompt(task_id, prompt)
    return {"status": "injected", "task_id": task_id}
