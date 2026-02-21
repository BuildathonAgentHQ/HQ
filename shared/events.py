"""
shared/events.py — WebSocket event-type registry and helper utilities.

All event names used between backend and frontend are defined here to ensure
consistency.  Frontend TypeScript constants should mirror the ``EventType``
enum values exactly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from shared.schemas import WebSocketEvent


# ─── EventType Enum ─────────────────────────────────────────────────────────
#
# Each value here corresponds to a valid ``WebSocketEvent.event_type``.
# They are intentionally kept in sync with the Literal type on that field.
# ─────────────────────────────────────────────────────────────────────────────


class EventType(str, Enum):
    """All recognised WebSocket event types.

    These MUST remain in sync with the ``Literal`` union on
    ``WebSocketEvent.event_type`` in ``shared/schemas.py``.
    """

    STATUS_UPDATE = "status_update"
    ERROR = "error"
    APPROVAL_REQUIRED = "approval_required"
    BUDGET_EXCEEDED = "budget_exceeded"
    DEBATE = "debate"
    DEBATE_STARTED = "debate"
    GUARDRAIL = "guardrail"
    GUARDRAIL_TRIGGERED = "guardrail"
    TASK_LIFECYCLE = "task_lifecycle"


# ─── Helper ─────────────────────────────────────────────────────────────────


def create_ws_event(
    task_id: str,
    event_type: EventType | str,
    payload: dict[str, Any] | None = None,
) -> WebSocketEvent:
    """Construct a properly timestamped ``WebSocketEvent``.

    This is the **only** sanctioned way to build WS messages.  Using this
    helper guarantees that timestamps are always UTC and that the event_type
    value is valid.

    Args:
        task_id: UUID of the task this event relates to.
        event_type: One of the ``EventType`` enum members (or its string
            value).
        payload: Arbitrary dict of sub-event data.  Defaults to ``{}``.

    Returns:
        A fully-populated ``WebSocketEvent`` instance ready for
        ``.model_dump_json()`` serialisation over the WebSocket.

    Example::

        from shared.events import EventType, create_ws_event
        from shared.schemas import TranslatedEvent

        translated = TranslatedEvent(
            task_id="abc-123",
            status="Installing dependencies…",
            severity="info",
            category="setup",
        )
        event = create_ws_event(
            task_id="abc-123",
            event_type=EventType.STATUS_UPDATE,
            payload=translated.model_dump(),
        )
    """
    # Accept both EventType enum members and raw strings.
    raw_type: str = event_type.value if isinstance(event_type, EventType) else event_type

    return WebSocketEvent(
        task_id=task_id,
        event_type=raw_type,  # type: ignore[arg-type]
        payload=payload or {},
        timestamp=datetime.now(timezone.utc),
    )
