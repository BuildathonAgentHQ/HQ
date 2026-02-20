"""
backend/app/translation/batch_processor.py — 2-second batching logic.

Collects raw agent output over a 2-second window before sending it
to the Translator, reducing API calls and producing more coherent translations.
"""

from __future__ import annotations

import asyncio
from typing import Callable, Optional

from shared.schemas import TranslationChunk


class BatchProcessor:
    """Batches raw output into 2-second windows before translation.

    Attributes:
        batch_interval: Seconds to wait before flushing (default 2.0).
        buffers: Dict mapping task_id → accumulated output text.
        translate_fn: Callback to invoke with batched output.
    """

    def __init__(
        self,
        translate_fn: Callable[[str, str], TranslationChunk],
        batch_interval: float = 2.0,
    ) -> None:
        self.batch_interval = batch_interval
        self.translate_fn = translate_fn
        self.buffers: dict[str, str] = {}
        self._tasks: dict[str, asyncio.Task] = {}  # type: ignore[type-arg]

    async def add_output(self, task_id: str, chunk: str) -> None:
        """Add a chunk of raw output to the buffer for a task.

        Args:
            task_id: The task producing the output.
            chunk: Raw output text to buffer.

        TODO:
            - Append chunk to the task's buffer
            - If no flush timer is running, start one
            - The timer should call _flush() after batch_interval seconds
        """
        # TODO: Implement buffering + timer logic
        raise NotImplementedError("BatchProcessor.add_output not yet implemented")

    async def _flush(self, task_id: str) -> Optional[TranslationChunk]:
        """Flush the buffer for a task and send it for translation.

        Args:
            task_id: The task whose buffer to flush.

        Returns:
            TranslationChunk from the translator, or None if buffer was empty.

        TODO:
            - Read and clear the buffer
            - Call translate_fn with the accumulated output
            - Clean up the timer task
        """
        # TODO: Implement buffer flush
        raise NotImplementedError("BatchProcessor._flush not yet implemented")

    async def flush_all(self) -> list[TranslationChunk]:
        """Flush all active buffers (e.g., on task completion).

        Returns:
            List of TranslationChunks from flushing all buffers.

        TODO:
            - Iterate over all buffered tasks and flush each
        """
        # TODO: Implement flush all
        return []
