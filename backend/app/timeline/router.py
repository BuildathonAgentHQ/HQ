"""
backend/app/timeline/router.py — Task timeline & activity endpoints.

Mounted at ``/api/timeline`` in ``main.py``.  Provides endpoints for
viewing task history as a timeline. Shows real task lifecycle events
from the task store.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/")
async def get_timeline(request: Request) -> list[dict[str, Any]]:
    """Return task lifecycle events as a timeline.

    Each entry includes task_id, description, status, engine, and timestamps.
    Returns the most recent tasks, newest first.
    """
    task_manager = request.app.state.task_manager
    tasks = task_manager.list_tasks()

    timeline: list[dict[str, Any]] = []
    for t in tasks:
        # Status icon mapping
        status_icon = {
            "pending": "⏳",
            "running": "🔄",
            "success": "✅",
            "failed": "❌",
            "suspended": "⏸️",
        }.get(t.status, "❓")

        timeline.append({
            "sha": t.id[:12],
            "message": f"{status_icon} {t.task[:80]}",
            "author": t.engine,
            "date": t.updated_at.isoformat() if t.updated_at else t.created_at.isoformat(),
            "status": t.status,
            "engine": t.engine,
            "task_id": t.id,
        })

    return timeline[:20]
