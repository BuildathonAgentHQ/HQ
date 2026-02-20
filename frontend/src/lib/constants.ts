/**
 * frontend/src/lib/constants.ts — API URLs, WebSocket URLs, and event-type constants.
 *
 * Centralised configuration for the frontend.  Values can be overridden
 * via environment variables (NEXT_PUBLIC_ prefix for Next.js).
 *
 * The EventType object MUST stay in sync with the EventType enum in
 * shared/events.py — same keys, same string values.
 */

// ── Connection URLs ────────────────────────────────────────────────────────

/** Base URL for the REST API. */
export const API_BASE_URL: string =
    process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

/** WebSocket URL for real-time activity stream. */
export const WS_URL: string =
    process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws/activity";

// ── Defaults ───────────────────────────────────────────────────────────────

/** Default budget limit per task in USD. */
export const DEFAULT_BUDGET_LIMIT: number = 2.0;

/** Batch interval for translation in milliseconds. */
export const TRANSLATION_BATCH_INTERVAL_MS: number = 2000;

/** Maximum events to keep in the activity stream buffer. */
export const MAX_EVENT_BUFFER_SIZE: number = 500;

/** WebSocket reconnection delay in milliseconds (initial). */
export const WS_RECONNECT_DELAY_MS: number = 1000;

/** Maximum WebSocket reconnection delay in milliseconds. */
export const WS_MAX_RECONNECT_DELAY_MS: number = 30000;

/** Heartbeat interval in milliseconds. */
export const HEARTBEAT_INTERVAL_MS: number = 30000;

// ── Event Types (mirrors shared/events.py EventType enum) ──────────────────

/**
 * WebSocket event-type string constants.
 *
 * These values correspond 1:1 with the `EventType` enum in `shared/events.py`
 * and the `WebSocketEvent.event_type` Literal union in `shared/schemas.py`.
 */
export const EventType = {
    STATUS_UPDATE: "status_update",
    ERROR: "error",
    APPROVAL_REQUIRED: "approval_required",
    BUDGET_EXCEEDED: "budget_exceeded",
    DEBATE: "debate",
    GUARDRAIL: "guardrail",
    TASK_LIFECYCLE: "task_lifecycle",
} as const;

/** Union type of all valid event-type string values. */
export type EventTypeValue = (typeof EventType)[keyof typeof EventType];
