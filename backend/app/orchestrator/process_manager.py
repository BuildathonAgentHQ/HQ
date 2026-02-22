"""
backend/app/orchestrator/process_manager.py — PTY-based agent execution engine.

Spawns agent subprocesses inside pseudo-terminals, streams their output
in real-time through the ``EventRouter``, and provides lifecycle control
(suspend / resume / kill / inject-prompt).

Design notes:
    - Each agent runs inside a ``pty`` so it behaves identically to an
      interactive terminal (colour codes, prompts, etc.).
    - Output is read asynchronously via ``asyncio.get_event_loop().add_reader``
      so it never blocks the FastAPI event loop.
    - The class is **not** a singleton — the router creates one at import
      time and shares it.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
try:
    import pty
    HAS_PTY = True
except ImportError:
    HAS_PTY = False
import shutil
import signal
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from shared.events import EventType, create_ws_event
from shared.schemas import ContextPayload, RawStreamEvent, Task

from backend.app.config import settings
from backend.app.translation.translator import TranslationLayer
from backend.app.telemetry._shared import telemetry as _telemetry
from backend.app.telemetry.token_tracker import TokenTracker

logger = logging.getLogger(__name__)


# ── Data container for a running process ────────────────────────────────────


@dataclass
class ManagedProcess:
    """Metadata kept for every active subprocess."""

    task_id: str
    process: subprocess.Popen[bytes]
    master_fd: int
    slave_fd: int
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    _monitoring_task: Optional[asyncio.Task[None]] = field(
        default=None, repr=False
    )
    _streaming_task: Optional[asyncio.Task[None]] = field(
        default=None, repr=False
    )


# ── ProcessManager ──────────────────────────────────────────────────────────


class ProcessManager:
    """Manages agent subprocess lifecycles.

    Attributes:
        active_processes: Mapping of ``task_id`` → ``ManagedProcess``.
    """

    MCP_CONFIG_PATH = ".agent_hq/mcp.json"
    WORKSPACES_DIR = Path(tempfile.gettempdir()) / "agent_hq_workspaces"

    def __init__(self, event_router: Any, task_manager: Any = None) -> None:
        """
        Args:
            event_router: The ``EventRouter`` singleton used to emit events
                to WebSocket clients and in-process handlers.
            task_manager: Optional ``TaskManager`` to update task records.
        """
        self._event_router = event_router
        self._task_manager = task_manager
        self._translator = TranslationLayer(settings)
        self._token_tracker = TokenTracker(_telemetry)
        self.active_processes: dict[str, ManagedProcess] = {}
        self.task_output_buffers: dict[str, list[str]] = {}  # task_id → output lines
        self.WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("ProcessManager initialised (translator=%s)",
                    "nemotron" if settings.USE_NEMOTRON else "templates")

    # ── Spawn ───────────────────────────────────────────────────────────────

    async def spawn_agent(
        self,
        task: Task,
        context: Optional[ContextPayload] = None,
    ) -> None:
        """Launch an agent subprocess for the given task.

        Builds the engine-specific command, creates a PTY, starts the
        process, and kicks off background tasks to stream its output and
        monitor its exit code.

        Args:
            task: The ``Task`` to execute.
            context: Optional ``ContextPayload`` to inject into the prompt.

        Raises:
            RuntimeError: If the task is already running.
            FileNotFoundError: If the engine binary is not on ``$PATH``.
        """
        if task.id in self.active_processes:
            raise RuntimeError(f"Task {task.id} is already running")

        # ── Build command ───────────────────────────────────────────────
        cmd = self._build_command(task, context)
        logger.info("Spawning agent for task %s: %s", task.id, " ".join(cmd))

        # ── Prepare workspace (clone repo) ──────────────────────────────
        workspace_dir = self._prepare_workspace(task.id)
        logger.info("Workspace for task %s: %s", task.id, workspace_dir)

        # ── Build environment with GitHub token ─────────────────────────
        env = os.environ.copy()
        if settings.GITHUB_TOKEN:
            env["GITHUB_TOKEN"] = settings.GITHUB_TOKEN
            env["GH_TOKEN"] = settings.GITHUB_TOKEN

        # ── Create PTY pair ─────────────────────────────────────────────
        master_fd, slave_fd = pty.openpty()

        # ── Start subprocess ────────────────────────────────────────────
        try:
            if HAS_PTY:
                master_fd, slave_fd = pty.openpty()
                process = subprocess.Popen(
                    cmd,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    close_fds=True,
                    start_new_session=True,
                    cwd=str(workspace_dir),
                    env=env,
                )
                # Close slave in the parent — only the child uses it
                os.close(slave_fd)
            else:
                creationflags = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=str(workspace_dir),
                    env=env,
                    creationflags=creationflags,
                )
                master_fd = process.stdout.fileno()
        except FileNotFoundError:
            if HAS_PTY:
                os.close(master_fd)
                os.close(slave_fd)
            logger.error("Engine binary not found: %s", cmd[0])
            raise

        managed = ManagedProcess(
            task_id=task.id,
            process=process,
            master_fd=master_fd,
            slave_fd=-1,  # already closed or unused
        )
        self.active_processes[task.id] = managed

        # ── Background tasks ────────────────────────────────────────────
        loop = asyncio.get_running_loop()
        managed._streaming_task = loop.create_task(
            self._stream_output(task.id, master_fd),
            name=f"stream-{task.id[:8]}",
        )
        managed._monitoring_task = loop.create_task(
            self._monitor_process(task.id, process),
            name=f"monitor-{task.id[:8]}",
        )

        # ── Emit lifecycle event ────────────────────────────────────────
        await self._emit_lifecycle(task.id, "running", exit_code=None)
        logger.info("Agent spawned for task %s (pid %d)", task.id, process.pid)

    # ── Output streaming ────────────────────────────────────────────────────

    async def _stream_output(self, task_id: str, fd: int) -> None:
        """Read PTY output, translate it, and emit ``TranslatedEvent`` events.

        Raw bytes from the PTY are decoded, converted to ``RawStreamEvent``,
        passed through the ``TranslationLayer`` to produce a human-friendly
        ``TranslatedEvent``, and finally broadcast to WebSocket clients.

        Args:
            task_id: UUID of the owning task.
            fd: The master side of the PTY file descriptor.
        """
        loop = asyncio.get_running_loop()

        try:
            while True:
                # Wait until data is ready on the fd
                data: bytes = await loop.run_in_executor(
                    None, self._read_fd, fd
                )
                if not data:
                    break  # EOF — child closed its side

                text = data.decode("utf-8", errors="replace").strip()
                if not text:
                    continue  # skip empty chunks

                raw_event = RawStreamEvent(
                    task_id=task_id,
                    stream_type="stdout",
                    raw_content=text,
                )

                # ── Store raw output for later retrieval ───────────────
                if task_id not in self.task_output_buffers:
                    self.task_output_buffers[task_id] = []
                self.task_output_buffers[task_id].append(text)

                # ── Translate raw output → human-friendly event ────────
                translated = await self._translator.translate(raw_event)

                # ── Estimate tokens and cost ──────────────────────────
                # Heuristic: estimate from character count.
                # Find the task so we know the engine for pricing.
                engine = "claude-code"
                if self._task_manager:
                    task = self._task_manager.get_task(task_id)
                    if task:
                        engine = task.engine
                
                char_count = len(text)
                cumulative_cost = await self._token_tracker.estimate_from_chars(
                    task_id, char_count, engine=engine
                )
                
                # Update task in memory if possible
                if self._task_manager:
                    usage = self._token_tracker.get_usage(task_id)
                    self._task_manager.update_task(
                        task_id,
                        token_count=usage["input_tokens"] + usage["output_tokens"],
                        budget_used=usage["cost"]
                    )

                ws_event = create_ws_event(
                    task_id=task_id,
                    event_type=EventType.STATUS_UPDATE,
                    payload=translated.model_dump(mode="json"),
                )
                await self._event_router.emit(ws_event)

        except OSError:
            # PTY closed — expected when process exits
            logger.debug("PTY closed for task %s", task_id)
        except asyncio.CancelledError:
            logger.debug("Stream reader cancelled for task %s", task_id)
        finally:
            try:
                os.close(fd)
            except OSError:
                pass

    @staticmethod
    def _read_fd(fd: int) -> bytes:
        """Blocking read from a file descriptor (run in executor).

        Returns empty bytes on EOF or error.
        """
        try:
            return os.read(fd, 4096)
        except OSError:
            return b""

    # ── Process monitoring ──────────────────────────────────────────────────

    async def _monitor_process(
        self,
        task_id: str,
        process: subprocess.Popen[bytes],
    ) -> None:
        """Poll the subprocess every 0.5 s until it exits.

        On exit, emits a ``task_lifecycle`` event with the final status
        and cleans up ``active_processes``.

        Args:
            task_id: UUID of the owning task.
            process: The ``Popen`` handle.
        """
        try:
            while True:
                exit_code = process.poll()
                if exit_code is not None:
                    status = "success" if exit_code == 0 else "failed"
                    logger.info(
                        "Task %s exited with code %d → %s",
                        task_id, exit_code, status,
                    )
                    await self._emit_lifecycle(task_id, status, exit_code)
                    self._cleanup(task_id)
                    self._cleanup_workspace(task_id)
                    return
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            logger.debug("Monitor cancelled for task %s", task_id)

    # ── Lifecycle control ───────────────────────────────────────────────────

    async def suspend_process(self, task_id: str) -> None:
        """Send ``SIGSTOP`` to the agent and emit a lifecycle event.

        Args:
            task_id: UUID of the task to suspend.

        Raises:
            KeyError: If the task has no active process.
        """
        managed = self._get(task_id)
        if sys.platform != "win32":
            os.kill(managed.process.pid, signal.SIGSTOP)
        await self._emit_lifecycle(task_id, "suspended")
        logger.info("Suspended task %s (pid %d)", task_id, managed.process.pid)

    async def resume_process(self, task_id: str) -> None:
        """Send ``SIGCONT`` to a suspended agent.

        Args:
            task_id: UUID of the task to resume.

        Raises:
            KeyError: If the task has no active process.
        """
        managed = self._get(task_id)
        if sys.platform != "win32":
            os.kill(managed.process.pid, signal.SIGCONT)
        await self._emit_lifecycle(task_id, "running")
        logger.info("Resumed task %s (pid %d)", task_id, managed.process.pid)

    async def kill_process(self, task_id: str) -> None:
        """Gracefully terminate an agent: SIGTERM, wait 5 s, then SIGKILL.

        Args:
            task_id: UUID of the task to kill.

        Raises:
            KeyError: If the task has no active process.
        """
        managed = self._get(task_id)
        pid = managed.process.pid
        logger.info("Killing task %s (pid %d) — sending SIGTERM", task_id, pid)

        if sys.platform == "win32":
            try:
                managed.process.terminate()
            except Exception:
                pass
        else:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

        # Give it 5 seconds to die gracefully
        for _ in range(10):
            if managed.process.poll() is not None:
                break
            await asyncio.sleep(0.5)
        else:
            # Still alive — force kill
            logger.warning("Task %s did not exit after SIGTERM — sending SIGKILL", task_id)
            if sys.platform == "win32":
                try:
                    managed.process.kill()
                except Exception:
                    pass
            else:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

        await self._emit_lifecycle(task_id, "failed", managed.process.returncode)
        self._cleanup(task_id)

    # ── Prompt injection ────────────────────────────────────────────────────

    async def inject_prompt(self, task_id: str, prompt: str) -> None:
        """Write text into the agent's PTY stdin.

        This is how the Janitor Protocol sends fix-it commands and how
        approval responses are relayed to the agent.

        Args:
            task_id: UUID of the target task.
            prompt: Text to write (a newline is appended automatically).

        Raises:
            KeyError: If the task has no active process.
        """
        managed = self._get(task_id)
        try:
            if not HAS_PTY and managed.process.stdin:
                managed.process.stdin.write((prompt + "\n").encode("utf-8"))
                managed.process.stdin.flush()
            else:
                data = (prompt + "\n").encode("utf-8")
                os.write(managed.master_fd, data)
            logger.debug("Injected prompt into task %s", task_id)
        except OSError:
            logger.error("Failed to inject prompt into task %s — PTY/pipe closed?", task_id)
            raise

    # ── Internals ───────────────────────────────────────────────────────────

    def _prepare_workspace(self, task_id: str) -> Path:
        """Clone the configured GitHub repo into a temp workspace.

        If `GITHUB_REPO` is set, clones it using the token for auth.
        Otherwise creates an empty temp directory.

        Returns:
            Path to the workspace directory.
        """
        workspace = self.WORKSPACES_DIR / task_id[:12]
        # Always start fresh
        if workspace.exists():
            shutil.rmtree(workspace, ignore_errors=True)

        repo = settings.GITHUB_REPO  # e.g. "BuildathonAgentHQ/test"
        token = settings.GITHUB_TOKEN

        if repo and token:
            clone_url = f"https://x-access-token:{token}@github.com/{repo}.git"
            logger.info("Cloning %s into workspace %s", repo, workspace)
            try:
                result = subprocess.run(
                    ["git", "clone", "--depth", "1", clone_url, str(workspace)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode != 0:
                    logger.error("git clone failed (rc=%d): %s", result.returncode, result.stderr)
                    # Create dir anyway as fallback
                    workspace.mkdir(parents=True, exist_ok=True)
                else:
                    logger.info("Cloned %s successfully into %s", repo, workspace)
                    # Configure git user for commits
                    subprocess.run(
                        ["git", "config", "user.email", "agent-hq@example.com"],
                        cwd=str(workspace), capture_output=True,
                    )
                    subprocess.run(
                        ["git", "config", "user.name", "Agent HQ"],
                        cwd=str(workspace), capture_output=True,
                    )
            except subprocess.TimeoutExpired:
                logger.error("git clone timed out for %s", repo)
                workspace.mkdir(parents=True, exist_ok=True)
            except FileNotFoundError:
                logger.error("git binary not found — cannot clone repo")
                workspace.mkdir(parents=True, exist_ok=True)
        else:
            logger.warning("No GITHUB_REPO/TOKEN configured — workspace is empty")
            workspace.mkdir(parents=True, exist_ok=True)

        return workspace

    def _cleanup_workspace(self, task_id: str) -> None:
        """Remove the workspace directory for a completed task."""
        workspace = self.WORKSPACES_DIR / task_id[:12]
        if workspace.exists():
            shutil.rmtree(workspace, ignore_errors=True)
            logger.info("Cleaned up workspace for task %s", task_id)

    def _build_command(
        self,
        task: Task,
        context: Optional[ContextPayload],
    ) -> list[str]:
        """Build the shell command for the given engine.

        Args:
            task: Task object containing engine, task prompt, etc.
            context: Optional context to prepend to the prompt.

        Returns:
            Command as a list of strings.
        """
        prompt = task.task

        # Prepend context if provided
        if context:
            ctx_parts: list[str] = []
            if context.architectural_context:
                ctx_parts.append(f"Architecture: {context.architectural_context}")
            if context.business_requirements:
                reqs = "; ".join(context.business_requirements)
                ctx_parts.append(f"Requirements: {reqs}")
            if ctx_parts:
                prompt = "\n".join(ctx_parts) + "\n\nTask: " + prompt

        # Always append PR instructions so agents commit & raise PRs
        pr_instruction = (
            "\n\nIMPORTANT: After completing the task, commit all your changes, "
            "push to a new branch (not main), and create a Pull Request with a "
            "clear title and description of what was changed."
        )
        prompt = prompt + pr_instruction

        if task.engine == "claude-code":
            cmd = ["claude", "-p", prompt, "--dangerously-skip-permissions"]
            mcp_path = Path(self.MCP_CONFIG_PATH)
            if settings.USE_NIA_MCP and mcp_path.exists():
                cmd.extend(["--mcp-config", str(mcp_path)])
            return cmd

        elif task.engine == "cursor-cli":
            return ["cursor", "--cli", "--prompt", prompt]

        elif task.engine == "gemini-cli":
            return ["gemini", "-p", prompt]

        elif task.engine == "codex":
            return ["codex", "--prompt", prompt, "--auto-edit"]

        else:
            logger.warning("Unknown engine '%s' — falling back to echo", task.engine)
            return ["echo", f"[mock] Would execute task: {prompt}"]

    def _get(self, task_id: str) -> ManagedProcess:
        """Look up a managed process, raising ``KeyError`` on miss."""
        if task_id not in self.active_processes:
            raise KeyError(f"No active process for task {task_id}")
        return self.active_processes[task_id]

    def _cleanup(self, task_id: str) -> None:
        """Remove a process from tracking and cancel its background tasks."""
        managed = self.active_processes.pop(task_id, None)
        if managed:
            if managed._streaming_task and not managed._streaming_task.done():
                managed._streaming_task.cancel()
            if managed._monitoring_task and not managed._monitoring_task.done():
                managed._monitoring_task.cancel()
            try:
                os.close(managed.master_fd)
            except OSError:
                pass

    async def _emit_lifecycle(
        self,
        task_id: str,
        status: str,
        exit_code: Optional[int] = None,
    ) -> None:
        """Emit a ``task_lifecycle`` WebSocket event.

        Args:
            task_id: UUID of the task.
            status: New lifecycle status (``"running"``, ``"success"``, etc.).
            exit_code: Process exit code (``None`` while still running).
        """
        event = create_ws_event(
            task_id=task_id,
            event_type=EventType.TASK_LIFECYCLE,
            payload={
                "task_id": task_id,
                "status": status,
                "exit_code": exit_code,
            },
        )
        await self._event_router.emit(event)

    @property
    def active_count(self) -> int:
        """Number of currently running agent processes."""
        return len(self.active_processes)
