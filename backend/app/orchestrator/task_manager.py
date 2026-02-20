"""
backend/app/orchestrator/task_manager.py — In-memory task CRUD.

Provides a ``TaskManager`` class that stores tasks in a plain dict.
In the hackathon sprint this is sufficient; production would swap the
dict for a database-backed repository with the same interface.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from shared.schemas import Task, TaskCreate
from shared.mocks.mock_data import SAMPLE_TASKS

logger = logging.getLogger(__name__)


class TaskManager:
    """In-memory task store with CRUD operations.

    The store is seeded with ``SAMPLE_TASKS`` from the mock data layer so
    the API has data from the moment it boots.

    Attributes:
        _tasks: Internal dict mapping ``task_id`` → ``Task``.
    """

    def __init__(self, seed_mock: bool = True) -> None:
        """
        Args:
            seed_mock: If ``True``, pre-populate with sample tasks from
                ``shared/mocks/mock_data.py``.
        """
        self._tasks: dict[str, Task] = {}
        if seed_mock:
            for t in SAMPLE_TASKS:
                self._tasks[t.id] = t
        logger.info(
            "TaskManager initialised with %d tasks (seed_mock=%s)",
            len(self._tasks), seed_mock,
        )

    # ── CRUD ────────────────────────────────────────────────────────────────

    def create_task(self, payload: TaskCreate) -> Task:
        """Create a new task from a ``TaskCreate`` payload.

        Generates a UUID, sets status to ``"pending"``, and stores the
        task in the internal dict.

        Args:
            payload: The creation payload from the frontend.

        Returns:
            The fully-formed ``Task`` object.
        """
        now = datetime.now(timezone.utc)
        task = Task(
            id=str(uuid.uuid4()),
            task=payload.task,
            engine=payload.engine,
            agent_type=payload.agent_type,
            status="pending",
            budget_limit=payload.budget_limit,
            budget_used=0.0,
            created_at=now,
            updated_at=now,
        )
        self._tasks[task.id] = task
        logger.info("Created task %s (engine=%s)", task.id, task.engine)
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Return a task by its ID, or ``None`` if not found.

        Args:
            task_id: UUID of the task.
        """
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[Task]:
        """Return all tasks, sorted by ``created_at`` descending (newest first)."""
        return sorted(
            self._tasks.values(),
            key=lambda t: t.created_at,
            reverse=True,
        )

    def update_task(self, task_id: str, **kwargs: object) -> Optional[Task]:
        """Update one or more fields on a task.

        Automatically sets ``updated_at`` to now.

        Args:
            task_id: UUID of the task to update.
            **kwargs: Field name → new value pairs (must be valid ``Task`` fields).

        Returns:
            The updated ``Task``, or ``None`` if the task was not found.
        """
        task = self._tasks.get(task_id)
        if not task:
            return None
        kwargs["updated_at"] = datetime.now(timezone.utc)
        updated = task.model_copy(update=kwargs)
        self._tasks[task_id] = updated
        logger.debug("Updated task %s: %s", task_id, list(kwargs.keys()))
        return updated

    def delete_task(self, task_id: str) -> bool:
        """Remove a task from the store.

        Args:
            task_id: UUID of the task to delete.

        Returns:
            ``True`` if the task existed and was removed, ``False`` otherwise.
        """
        if task_id in self._tasks:
            del self._tasks[task_id]
            logger.info("Deleted task %s", task_id)
            return True
        return False

    @property
    def count(self) -> int:
        """Total number of tasks in the store."""
        return len(self._tasks)
