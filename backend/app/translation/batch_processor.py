"""
backend/app/translation/batch_processor.py — 2-second batching logic.

Raw terminal output arrives line-by-line at high frequency.  Sending every
single line to the Nemotron API would be expensive and slow, so this
``BatchProcessor`` accumulates output for each task in a short time window
and then translates the combined text in one shot.

Error-containing lines bypass the timer and trigger an immediate flush so
that problems surface in the UI without delay.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from backend.app.translation.translator import TranslationLayer
from backend.app.websocket.events import EventRouter
from shared.schemas import RawStreamEvent

logger = logging.getLogger(__name__)

# ── Patterns that trigger an immediate flush ────────────────────────────────
_ERROR_MARKERS = re.compile(
    r"Traceback|Error[:\s]|FAILED|FATAL|panic:|Segmentation fault",
    re.IGNORECASE,
)


class BatchProcessor:
    """Batches raw agent output into time windows before translation.

    Lines are accumulated per ``task_id``.  Every *batch_interval* seconds
    the buffer is flushed: the combined text is translated via the
    ``TranslationLayer`` and the result is broadcast as a ``WebSocketEvent``
    through the ``EventRouter``.

    Lines containing obvious error markers are flushed immediately so
    errors appear in the dashboard without delay.

    Parameters
    ----------
    translator:
        The ``TranslationLayer`` instance used to translate batched text.
    event_router:
        The ``EventRouter`` singleton used to emit ``status_update`` events.
    batch_interval:
        Seconds between automatic flushes (default ``2.0``).
    """

    def __init__(
        self,
        translator: TranslationLayer,
        event_router: EventRouter,
        batch_interval: float = 2.0,
    ) -> None:
        self._translator = translator
        self._event_router = event_router
        self.batch_interval = batch_interval

        # task_id → list of raw output lines buffered in this window
        self.buffer: dict[str, list[str]] = {}

        # Background flush loop task handle
        self._flush_task: Optional[asyncio.Task] = None  # type: ignore[type-arg]
        self._running = False

    # ── Public API ───────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the background flush loop."""
        if self._running:
            return
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info(
            "BatchProcessor started (interval=%.1fs)", self.batch_interval
        )

    async def stop(self) -> None:
        """Stop the background flush loop and flush remaining buffers."""
        self._running = False
        if self._flush_task is not None:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None

        # Drain anything left in the buffers
        await self._flush()
        logger.info("BatchProcessor stopped")

    async def add_line(self, raw_event: RawStreamEvent) -> None:
        """Buffer a single raw output line for later translation.

        If the line contains an error marker (``Traceback``, ``*Error``,
        ``FAILED``, etc.) the buffer for that task is flushed immediately.

        Parameters
        ----------
        raw_event:
            The ``RawStreamEvent`` captured from the agent subprocess.
        """
        task_id = raw_event.task_id
        content = raw_event.raw_content

        if task_id not in self.buffer:
            self.buffer[task_id] = []
        self.buffer[task_id].append(content)

        # Immediate flush for errors — don't wait for the batch timer
        if _ERROR_MARKERS.search(content):
            logger.debug(
                "Error marker detected for task %s — flushing immediately",
                task_id,
            )
            await self._immediate_flush(task_id)

    # ── Internal ─────────────────────────────────────────────────────────

    async def _flush_loop(self) -> None:
        """Background loop that flushes all buffers every *batch_interval*."""
        try:
            while self._running:
                await asyncio.sleep(self.batch_interval)
                await self._flush()
        except asyncio.CancelledError:
            pass  # graceful shutdown

    async def _flush(self) -> None:
        """Flush **all** buffered tasks — join lines, translate, emit."""
        if not self.buffer:
            return

        # Snapshot keys so we can mutate the dict safely
        task_ids = list(self.buffer.keys())
        for task_id in task_ids:
            await self._flush_task_buffer(task_id)

    async def _immediate_flush(self, task_id: str) -> None:
        """Flush only the buffer for *task_id* right now."""
        if task_id in self.buffer and self.buffer[task_id]:
            await self._flush_task_buffer(task_id)

    async def _flush_task_buffer(self, task_id: str) -> None:
        """Translate the accumulated buffer for one task and emit the event."""
        lines = self.buffer.pop(task_id, [])
        if not lines:
            return

        combined = "\n".join(lines)

        # Build a synthetic RawStreamEvent with the combined text
        raw_event = RawStreamEvent(
            task_id=task_id,
            stream_type="stdout",
            raw_content=combined,
            timestamp=datetime.now(timezone.utc),
        )

        try:
            translated = await self._translator.translate(raw_event)

            # Emit as a WebSocket status_update event
            await self._event_router.emit_status_update(
                task_id=task_id,
                payload=translated.model_dump(),
            )
        except Exception:
            logger.exception(
                "Failed to translate/emit batch for task %s", task_id
            )
