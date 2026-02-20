"""
backend/app/guardrails/file_watcher.py — watchdog-based file monitoring.

Monitors the working directory during agent execution and emits
FILE_CHANGED events for each created, modified, or deleted file.
"""

from __future__ import annotations

from typing import Callable, Optional

from shared.schemas import FileChangeEvent


class FileWatcher:
    """Watches a directory tree for file changes using the watchdog library.

    Attributes:
        watch_path: Root directory being monitored.
        on_change: Callback invoked with FileChangeEvent for each change.
        observer: watchdog Observer instance.
    """

    def __init__(
        self,
        watch_path: str,
        on_change: Optional[Callable[[FileChangeEvent], None]] = None,
    ) -> None:
        self.watch_path = watch_path
        self.on_change = on_change
        self._observer = None  # TODO: Initialize watchdog.observers.Observer

    async def start(self) -> None:
        """Start watching the directory tree.

        TODO:
            - Create a watchdog Observer and EventHandler
            - Schedule recursive watching on watch_path
            - Filter out __pycache__, node_modules, .git, etc.
            - Start the observer in a background thread
        """
        # TODO: Implement file watching
        raise NotImplementedError("FileWatcher.start not yet implemented")

    async def stop(self) -> None:
        """Stop the file watcher and clean up.

        TODO:
            - Stop and join the watchdog observer
        """
        # TODO: Implement stop
        raise NotImplementedError("FileWatcher.stop not yet implemented")

    def _handle_event(self, event_type: str, file_path: str, task_id: str) -> FileChangeEvent:
        """Create a FileChangeEvent from a watchdog event.

        Args:
            event_type: One of "created", "modified", "deleted".
            file_path: Absolute path to the changed file.
            task_id: The task that triggered the change.

        Returns:
            FileChangeEvent to broadcast via WebSocket.

        TODO:
            - Build FileChangeEvent and call on_change callback
            - Trigger linting for modified files
        """
        # TODO: Implement event creation
        raise NotImplementedError("FileWatcher._handle_event not yet implemented")
