"""
backend/app/guardrails/file_watcher.py — Background repository file watcher.

Monitors the repository for code modifications and automatically triggers the
LinterRunner, pumping GuardrailEvents straight to the frontend via the EventRouter.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from backend.app.guardrails.linter_runner import LinterRunner

logger = logging.getLogger(__name__)


class GuardrailEventHandler(FileSystemEventHandler):
    """Custom handler interpreting watchdog filesystem events."""

    def __init__(self, runner: LinterRunner, event_router: Any, loop: asyncio.AbstractEventLoop) -> None:
        self.runner = runner
        self.event_router = event_router
        self.loop = loop
        
        self._valid_extensions = {".py", ".js", ".ts", ".jsx", ".tsx"}
        self._ignored_dirs = {".git", ".venv", "venv", "node_modules", "__pycache__", ".next"}

    def on_modified(self, event: FileSystemEvent) -> None:
        """Triggered when a file or directory is modified."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        
        # Exclude ignored directories
        if any(ignored in file_path.parts for ignored in self._ignored_dirs):
            return
            
        # Exclude non-code files
        if file_path.suffix.lower() not in self._valid_extensions:
            return
            
        logger.info(f"JanitorWatcher detected file modification: {file_path}")
        
        # Schedule the async check in the main event loop
        asyncio.run_coroutine_threadsafe(self._handle_file(str(file_path)), self.loop)

    async def _handle_file(self, file_path: str) -> None:
        """Run linters and emit the resulting event via the event router."""
        event = await self.runner.run_checks(file_path)
        logger.debug(f"Linting completed for {file_path}: Passed={event.passed}")
        
        try:
            from shared.events import EventType, create_ws_event
            ws_event = create_ws_event(
                task_id=event.task_id,
                event_type=EventType.GUARDRAIL_TRIGGERED,
                payload=event.model_dump(mode="json"),
            )
            await self.event_router.emit(ws_event)
        except Exception as e:
            logger.error(f"Failed to emit GuardrailEvent: {e}")


class JanitorWatcher:
    """Manages the watchdog observer thread running in the background."""

    def __init__(self, watch_path: str, event_router: Any) -> None:
        self.watch_path = watch_path
        self.event_router = event_router
        self.runner = LinterRunner()
        self.observer = Observer()
        self.loop = asyncio.get_event_loop()
        
        self.handler = GuardrailEventHandler(self.runner, self.event_router, self.loop)
        self.observer.schedule(self.handler, self.watch_path, recursive=True)

    def start(self) -> None:
        """Start the background watchdog thread."""
        logger.info(f"Starting JanitorWatcher on directory: {self.watch_path}")
        self.observer.start()

    def stop(self) -> None:
        """Stop the background watchdog thread cleanly."""
        logger.info("Stopping JanitorWatcher.")
        self.observer.stop()
        self.observer.join()
