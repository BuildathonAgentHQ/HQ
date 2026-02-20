"""
backend/app/websocket/events.py — Central event router (the "nervous system").

All backend modules emit events through the ``EventRouter`` here.
The router forwards them to the ``ConnectionManager`` for WebSocket delivery
and dispatches them to any registered in-process handler callbacks.

Usage::

    from backend.app.websocket.events import event_router
    from shared.events import EventType, create_ws_event

    event = create_ws_event(task_id, EventType.STATUS_UPDATE, payload)
    await event_router.emit(event)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable

from shared.events import EventType, create_ws_event
from shared.schemas import WebSocketEvent

from backend.app.websocket.manager import manager

logger = logging.getLogger(__name__)

# Type alias for handler functions
HandlerFn = Callable[[WebSocketEvent], Awaitable[None]]


class EventRouter:
    """Central event bus that sits between backend producers and the WebSocket
    connection manager.

    Responsibilities:
        1. Accept ``WebSocketEvent`` objects from any backend module.
        2. Forward them to ``ConnectionManager.broadcast`` (or
           ``send_to_task`` when the event carries a ``task_id``).
        3. Dispatch the event to any registered in-process handler callbacks
           (e.g., telemetry logging, guardrail triggers).

    All modules should emit events through this router — never directly via
    the ``ConnectionManager`` — so that cross-cutting concerns (logging,
    metrics, etc.) are handled in one place.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[HandlerFn]] = defaultdict(list)

    # ── Handler registration ────────────────────────────────────────────────

    def register_handler(
        self, event_type: EventType | str, handler_fn: HandlerFn
    ) -> None:
        """Register an async callback for a specific event type.

        Multiple handlers can be registered per event type; they are called
        in registration order.  Handlers receive the full ``WebSocketEvent``
        and can inspect ``event.payload`` for typed sub-event data.

        Args:
            event_type: The ``EventType`` enum member (or its raw string
                value) to listen for.
            handler_fn: An async callable ``(WebSocketEvent) -> None``.

        Example::

            async def on_guardrail(event: WebSocketEvent) -> None:
                print(f"Guardrail fired for task {event.task_id}")

            event_router.register_handler(EventType.GUARDRAIL, on_guardrail)
        """
        key = event_type.value if isinstance(event_type, EventType) else event_type
        self._handlers[key].append(handler_fn)
        logger.debug(
            "Registered handler %s for event type '%s'",
            handler_fn.__name__,
            key,
        )

    def unregister_handler(
        self, event_type: EventType | str, handler_fn: HandlerFn
    ) -> None:
        """Remove a previously registered handler.

        Args:
            event_type: Event type to unregister from.
            handler_fn: The exact function reference to remove.
        """
        key = event_type.value if isinstance(event_type, EventType) else event_type
        try:
            self._handlers[key].remove(handler_fn)
        except ValueError:
            pass  # silently ignore if not found

    # ── Emission ────────────────────────────────────────────────────────────

    async def emit(self, event: WebSocketEvent) -> None:
        """Route a ``WebSocketEvent`` to WebSocket clients and in-process
        handlers.

        Steps:
            1. Broadcast the event via the ``ConnectionManager``.  If the
               event has a ``task_id`` it is sent to task-subscribers first;
               otherwise it fans out to every client.
            2. Invoke all registered handler callbacks for this event type.

        Args:
            event: The ``WebSocketEvent`` to dispatch.
        """
        logger.debug(
            "Emitting event type='%s' task_id='%s'",
            event.event_type,
            event.task_id,
        )

        # 1. Broadcast over WebSocket
        if event.task_id:
            await manager.send_to_task(event.task_id, event)
        else:
            await manager.broadcast(event)

        # 2. Run in-process handlers
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                logger.exception(
                    "Handler %s failed for event type '%s'",
                    handler.__name__,
                    event.event_type,
                )

    # ── Convenience emitters ────────────────────────────────────────────────
    #
    # Thin wrappers so callers don't have to manually build WebSocketEvent
    # objects every time.  They all delegate to create_ws_event + self.emit.

    async def emit_status_update(
        self, task_id: str, payload: dict[str, Any]
    ) -> None:
        """Shorthand: emit a STATUS_UPDATE event.

        Args:
            task_id: UUID of the relevant task.
            payload: Serialised ``TranslatedEvent`` or similar dict.
        """
        event = create_ws_event(task_id, EventType.STATUS_UPDATE, payload)
        await self.emit(event)

    async def emit_error(
        self, task_id: str, payload: dict[str, Any]
    ) -> None:
        """Shorthand: emit an ERROR event.

        Args:
            task_id: UUID of the relevant task.
            payload: Error details dict.
        """
        event = create_ws_event(task_id, EventType.ERROR, payload)
        await self.emit(event)

    async def emit_approval_required(
        self, task_id: str, payload: dict[str, Any]
    ) -> None:
        """Shorthand: emit an APPROVAL_REQUIRED event.

        Args:
            task_id: UUID of the relevant task.
            payload: Serialised ``ApprovalRequest`` dict.
        """
        event = create_ws_event(task_id, EventType.APPROVAL_REQUIRED, payload)
        await self.emit(event)

    async def emit_budget_exceeded(
        self, task_id: str, payload: dict[str, Any]
    ) -> None:
        """Shorthand: emit a BUDGET_EXCEEDED event.

        Args:
            task_id: UUID of the relevant task.
            payload: Budget / cost details dict.
        """
        event = create_ws_event(task_id, EventType.BUDGET_EXCEEDED, payload)
        await self.emit(event)

    async def emit_guardrail(
        self, task_id: str, payload: dict[str, Any]
    ) -> None:
        """Shorthand: emit a GUARDRAIL event.

        Args:
            task_id: UUID of the relevant task.
            payload: Serialised ``GuardrailEvent`` dict.
        """
        event = create_ws_event(task_id, EventType.GUARDRAIL, payload)
        await self.emit(event)

    async def emit_debate(
        self, task_id: str, payload: dict[str, Any]
    ) -> None:
        """Shorthand: emit a DEBATE event.

        Args:
            task_id: UUID of the relevant task.
            payload: Serialised ``DebateResult`` dict.
        """
        event = create_ws_event(task_id, EventType.DEBATE, payload)
        await self.emit(event)

    async def emit_task_lifecycle(
        self, task_id: str, payload: dict[str, Any]
    ) -> None:
        """Shorthand: emit a TASK_LIFECYCLE event.

        Args:
            task_id: UUID of the relevant task.
            payload: Serialised ``Task`` dict with lifecycle state.
        """
        event = create_ws_event(task_id, EventType.TASK_LIFECYCLE, payload)
        await self.emit(event)

    # ── Introspection ───────────────────────────────────────────────────────

    @property
    def handler_count(self) -> int:
        """Total number of registered handler callbacks across all types."""
        return sum(len(h) for h in self._handlers.values())


# ─── Module-level singleton ─────────────────────────────────────────────────
# Import and use this instance everywhere:
#
#   from backend.app.websocket.events import event_router
#   await event_router.emit(event)
#
event_router = EventRouter()
