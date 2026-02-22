"""
backend/app/websocket/manager.py — WebSocket connection manager.

Singleton ``ConnectionManager`` that every backend module imports to
broadcast real-time events to the frontend.  Supports both fan-out to
ALL connected clients and targeted delivery to clients watching a
specific task.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

from shared.schemas import WebSocketEvent

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and event broadcasting.

    This is the single gateway through which all real-time messages reach the
    frontend.  Other modules should never call ``websocket.send_*`` directly —
    always go through ``manager.broadcast()`` or ``manager.send_to_task()``.

    Attributes:
        active_connections: All connected WebSocket clients.
        task_subscriptions: Mapping of task_id → set of WebSockets that are
            interested in events for that task.
    """

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self.task_subscriptions: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    # ── Connection lifecycle ────────────────────────────────────────────────

    async def connect(self, websocket: WebSocket) -> None:
        """Accept an incoming WebSocket and register it.

        Args:
            websocket: The incoming WebSocket connection to accept.
        """
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.info(
            "WebSocket connected — %d active connection(s)",
            len(self.active_connections),
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket from the active pool and all task subscriptions.

        Safe to call even if the socket was never added.

        Args:
            websocket: The disconnected WebSocket.
        """
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
            # Clean up any task subscriptions for this socket
            empty_keys: list[str] = []
            for task_id, sockets in self.task_subscriptions.items():
                sockets.discard(websocket)
                if not sockets:
                    empty_keys.append(task_id)
            for key in empty_keys:
                del self.task_subscriptions[key]
        logger.info(
            "WebSocket disconnected — %d active connection(s)",
            len(self.active_connections),
        )

    # ── Subscriptions ───────────────────────────────────────────────────────

    async def subscribe(self, websocket: WebSocket, task_id: str) -> None:
        """Subscribe a client to events for a specific task.

        Args:
            websocket: The client WebSocket.
            task_id: UUID of the task to follow.
        """
        async with self._lock:
            self.task_subscriptions.setdefault(task_id, set()).add(websocket)
        logger.debug("Client subscribed to task %s", task_id)

    async def unsubscribe(self, websocket: WebSocket, task_id: str) -> None:
        """Unsubscribe a client from a specific task's events.

        Args:
            websocket: The client WebSocket.
            task_id: UUID of the task to stop following.
        """
        async with self._lock:
            if task_id in self.task_subscriptions:
                self.task_subscriptions[task_id].discard(websocket)
                if not self.task_subscriptions[task_id]:
                    del self.task_subscriptions[task_id]

    # ── Sending ─────────────────────────────────────────────────────────────

    async def broadcast(self, event: WebSocketEvent) -> None:
        """Send an event to ALL connected clients."""
        payload = event.model_dump(mode="json")
        logger.info(f"Broadcasting event {event.event_type} to {len(self.active_connections)} clients")
        dead: list[WebSocket] = []

        for ws in self.active_connections:
            try:
                await ws.send_json(payload)
            except Exception as e:
                logger.error(f"Failed to send to {id(ws)}: {e}")
                dead.append(ws)

        for ws in dead:
            await self.disconnect(ws)

    async def send_to_task(self, task_id: str, event: WebSocketEvent) -> None:
        """Send an event only to clients subscribed to a specific task.

        Falls back to broadcasting to ALL clients if no subscriptions exist
        for the given task — this ensures events are never silently dropped
        during early development.

        Args:
            task_id: UUID of the task.
            event: A ``WebSocketEvent`` envelope to deliver.
        """
        subscribers = self.task_subscriptions.get(task_id)

        if not subscribers:
            # No explicit subscribers → broadcast so nothing is lost
            await self.broadcast(event)
            return

        payload = event.model_dump(mode="json")
        dead: list[WebSocket] = []

        for ws in subscribers:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)

        for ws in dead:
            await self.disconnect(ws)

    async def send_personal(
        self, websocket: WebSocket, event: WebSocketEvent
    ) -> None:
        """Send an event to a single specific client.

        Args:
            websocket: The target WebSocket.
            event: A ``WebSocketEvent`` envelope to send.
        """
        try:
            await websocket.send_json(event.model_dump(mode="json"))
        except Exception as e:
            await self.disconnect(websocket)
            from starlette.websockets import WebSocketDisconnect
            raise WebSocketDisconnect(code=1006, reason=str(e))

    # ── Introspection ───────────────────────────────────────────────────────

    @property
    def connection_count(self) -> int:
        """Number of currently active WebSocket connections."""
        return len(self.active_connections)

    @property
    def subscription_count(self) -> int:
        """Number of active task subscriptions across all clients."""
        return sum(len(s) for s in self.task_subscriptions.values())


# ─── Module-level singleton ─────────────────────────────────────────────────
# Import and use this instance everywhere:
#
#   from backend.app.websocket.manager import manager
#   await manager.broadcast(event)
#
manager = ConnectionManager()
