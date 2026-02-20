"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { WebSocketEvent } from "@/lib/types";

const MAX_EVENTS = 100;
const MAX_BACKOFF_MS = 30_000;

interface UseWebSocketReturn {
    /** Last 100 events received, newest first. */
    events: WebSocketEvent[];
    /** Whether the WebSocket is currently connected. */
    isConnected: boolean;
    /** Send an arbitrary JSON message to the server. */
    sendMessage: (msg: unknown) => void;
}

/**
 * Custom React hook for WebSocket connectivity with auto-reconnect.
 *
 * - Connects on mount, reconnects on disconnect with exponential backoff
 *   (1 s → 2 s → 4 s … capped at 30 s).
 * - Parses incoming messages as `WebSocketEvent`.
 * - Keeps the last 100 events in state (newest first).
 * - `sendMessage` is stable across renders.
 */
export function useWebSocket(url: string): UseWebSocketReturn {
    const [events, setEvents] = useState<WebSocketEvent[]>([]);
    const [isConnected, setIsConnected] = useState(false);

    const wsRef = useRef<WebSocket | null>(null);
    const backoffRef = useRef(1_000);
    const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const mountedRef = useRef(true);

    // ── connect ----------------------------------------------------------
    const connect = useCallback(() => {
        if (!mountedRef.current) return;

        try {
            const ws = new WebSocket(url);
            wsRef.current = ws;

            ws.onopen = () => {
                if (!mountedRef.current) return;
                setIsConnected(true);
                backoffRef.current = 1_000; // reset backoff on success
            };

            ws.onmessage = (event) => {
                if (!mountedRef.current) return;
                try {
                    const data = JSON.parse(event.data) as WebSocketEvent;
                    setEvents((prev) => [data, ...prev].slice(0, MAX_EVENTS));
                } catch {
                    // silently ignore malformed messages
                }
            };

            ws.onclose = () => {
                if (!mountedRef.current) return;
                setIsConnected(false);
                scheduleReconnect();
            };

            ws.onerror = () => {
                // onclose will fire after onerror — reconnect handled there
                ws.close();
            };
        } catch {
            scheduleReconnect();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [url]);

    // ── reconnect with exponential backoff --------------------------------
    const scheduleReconnect = useCallback(() => {
        if (!mountedRef.current) return;
        const delay = backoffRef.current;
        backoffRef.current = Math.min(delay * 2, MAX_BACKOFF_MS);
        reconnectTimerRef.current = setTimeout(() => {
            connect();
        }, delay);
    }, [connect]);

    // ── lifecycle ----------------------------------------------------------
    useEffect(() => {
        mountedRef.current = true;
        connect();

        return () => {
            mountedRef.current = false;
            if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
            wsRef.current?.close();
        };
    }, [connect]);

    // ── sendMessage (stable ref) ------------------------------------------
    const sendMessage = useCallback((msg: unknown) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(msg));
        }
    }, []);

    return { events, isConnected, sendMessage };
}
