"""
backend/tests/test_orchestrator.py — Baseline tests for TaskManager and API.

Confirms the core scaffold works.  Teammates will add engine-specific
and process-lifecycle tests once their modules are integrated.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from shared.schemas import Task, TaskCreate


# ═══════════════════════════════════════════════════════════════════════════════
#  TaskManager unit tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTaskManagerCreate:
    """TaskManager.create_task produces a valid Task."""

    def test_create_returns_pending_task_with_uuid(self, task_manager):
        payload = TaskCreate(
            task="Add integration tests",
            engine="claude-code",
            agent_type="test_writer",
            budget_limit=1.5,
            context_sources=[],
        )
        task = task_manager.create_task(payload)

        # UUID is valid
        uuid.UUID(task.id)  # raises ValueError if malformed

        assert task.status == "pending"
        assert task.task == "Add integration tests"
        assert task.engine == "claude-code"
        assert task.agent_type == "test_writer"
        assert task.budget_limit == 1.5
        assert task.budget_used == 0.0
        assert task.exit_code is None
        assert task.token_count == 0
        assert task.strike_count == 0


class TestTaskManagerList:
    """TaskManager.list_tasks returns all tasks newest-first."""

    def test_list_returns_all_seeded_tasks(self, task_manager):
        tasks = task_manager.list_tasks()
        assert len(tasks) == 3

    def test_list_ordered_newest_first(self, task_manager):
        tasks = task_manager.list_tasks()
        timestamps = [t.created_at for t in tasks]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_list_includes_newly_created_task(self, task_manager):
        payload = TaskCreate(
            task="New task",
            engine="cursor-cli",
            agent_type="general",
            budget_limit=2.0,
            context_sources=[],
        )
        task_manager.create_task(payload)
        assert len(task_manager.list_tasks()) == 4


class TestTaskManagerUpdate:
    """TaskManager.update_task modifies fields correctly."""

    def test_update_status_to_running(self, task_manager):
        tasks = task_manager.list_tasks()
        task_id = tasks[0].id

        updated = task_manager.update_task(task_id, status="running")

        assert updated is not None
        assert updated.status == "running"
        assert updated.updated_at > tasks[0].created_at

    def test_update_nonexistent_returns_none(self, task_manager):
        result = task_manager.update_task("nonexistent-id", status="failed")
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
#  API integration tests
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_post_tasks_returns_valid_task(async_client):
    """POST /api/tasks/ should create and return a valid Task."""
    response = await async_client.post(
        "/api/tasks/",
        json={
            "task": "Write documentation for the API",
            "engine": "claude-code",
            "agent_type": "doc",
            "budget_limit": 1.0,
            "context_sources": [],
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Validate shape
    assert "id" in data
    uuid.UUID(data["id"])  # valid UUID
    assert data["task"] == "Write documentation for the API"
    assert data["engine"] == "claude-code"
    assert data["agent_type"] == "doc"
    assert data["budget_limit"] == 1.0
    # Status should be pending (engine binary not on PATH in CI)
    # or running if claude happens to be installed
    assert data["status"] in ("pending", "running")


@pytest.mark.asyncio
async def test_get_tasks_returns_list(async_client):
    """GET /api/tasks/ should return a list of Task objects."""
    response = await async_client.get("/api/tasks/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Should have at least the seeded mock tasks
    assert len(data) >= 1
