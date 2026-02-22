"""
backend/tests/test_process_manager.py — Tests for ProcessManager cross-platform orchestration.
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.config import settings
from backend.app.orchestrator.process_manager import ProcessManager, ManagedProcess
from shared.schemas import ContextPayload, Task


@pytest.fixture
def mock_event_router():
    router = MagicMock()
    router.emit = AsyncMock()
    return router


@pytest.fixture
def mock_task_manager():
    manager = MagicMock()
    manager.get_task = MagicMock(return_value=None)
    manager.update_task = MagicMock()
    return manager


@pytest.fixture
def process_manager(mock_event_router, mock_task_manager):
    return ProcessManager(event_router=mock_event_router, task_manager=mock_task_manager)


# ═══════════════════════════════════════════════════════════════════════════════
#  Command Building Tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_build_command_claude(process_manager):
    task = Task(id="t1", task="Build a feature", engine="claude-code", agent_type="general", budget_limit=1.0)
    cmd = process_manager._build_command(task, None)
    
    assert cmd[0] == "claude"
    assert "Build a feature" in cmd[2]
    assert "--dangerously-skip-permissions" in cmd


def test_build_command_with_context(process_manager):
    task = Task(id="t1", task="Build a feature", engine="cursor-cli", agent_type="general", budget_limit=1.0)
    context = ContextPayload(architectural_context="Use React", business_requirements=["Must be fast"])
    
    cmd = process_manager._build_command(task, context)
    
    assert cmd[0] == "cursor"
    assert "Architecture: Use React" in cmd[3]
    assert "Requirements: Must be fast" in cmd[3]
    assert "Task: Build a feature" in cmd[3]

# ═══════════════════════════════════════════════════════════════════════════════
#  Workspace Preparation Tests
# ═══════════════════════════════════════════════════════════════════════════════

@patch("subprocess.run")
def test_prepare_workspace_with_github(mock_run, process_manager):
    settings.GITHUB_REPO = "TestOrg/TestRepo"
    settings.GITHUB_TOKEN = "test-token"
    mock_run.return_value = MagicMock(returncode=0)
    
    workspace = process_manager._prepare_workspace("testing-task-12345")
    
    assert "testing-task" in str(workspace)
    assert mock_run.call_count == 3  # clone, config email, config name
    
    # Check the clone command contains the token
    clone_cmd = mock_run.call_args_list[0][0][0]
    assert "git" in clone_cmd
    assert "clone" in clone_cmd
    assert "https://x-access-token:test-token@github.com/TestOrg/TestRepo.git" in clone_cmd

# ═══════════════════════════════════════════════════════════════════════════════
#  Process Lifecycle Tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch("os.kill")
async def test_suspend_process(mock_kill, process_manager):
    mock_process = MagicMock(pid=12345)
    process_manager.active_processes["t1"] = ManagedProcess(
        task_id="t1", process=mock_process, master_fd=1, slave_fd=2
    )

    await process_manager.suspend_process("t1")
    
    if sys.platform != "win32":
        mock_kill.assert_called_once_with(12345, signal.SIGSTOP)
    
    # ensure it broadcasts the event
    process_manager._event_router.emit.assert_called_once()


@pytest.mark.asyncio
@patch("os.kill")
async def test_resume_process(mock_kill, process_manager):
    mock_process = MagicMock(pid=12345)
    process_manager.active_processes["t1"] = ManagedProcess(
        task_id="t1", process=mock_process, master_fd=1, slave_fd=2
    )

    await process_manager.resume_process("t1")
    
    if sys.platform != "win32":
        mock_kill.assert_called_once_with(12345, signal.SIGCONT)
    
    process_manager._event_router.emit.assert_called_once()

@pytest.mark.asyncio
@patch("os.kill")
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_kill_process(mock_sleep, mock_kill, process_manager):
    mock_process = MagicMock(pid=12345, returncode=-1)
    
    # Mock `.poll()` to always return None meaning it hasn't exited gracefully
    mock_process.poll.return_value = None
    
    process_manager.active_processes["t1"] = ManagedProcess(
        task_id="t1", process=mock_process, master_fd=1, slave_fd=2
    )

    await process_manager.kill_process("t1")
    
    if sys.platform == "win32":
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
    else:
        # First term, then kill since we simulated that it didn't exit
        assert mock_kill.call_count == 2
        mock_kill.assert_any_call(12345, signal.SIGTERM)
        mock_kill.assert_any_call(12345, signal.SIGKILL)
    
    # Ensure active processes is cleaned up
    assert "t1" not in process_manager.active_processes

# ═══════════════════════════════════════════════════════════════════════════════
#  Prompt Injection Tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch("os.write")
async def test_inject_prompt_pty(mock_write, process_manager):
    # Mocking HAS_PTY inside the module
    with patch("backend.app.orchestrator.process_manager.HAS_PTY", True):
        mock_process = MagicMock()
        process_manager.active_processes["t1"] = ManagedProcess(
            task_id="t1", process=mock_process, master_fd=99, slave_fd=100
        )
        
        await process_manager.inject_prompt("t1", "Fix the bug")
        
        mock_write.assert_called_once_with(99, b"Fix the bug\n")


@pytest.mark.asyncio
async def test_inject_prompt_no_pty(process_manager):
    with patch("backend.app.orchestrator.process_manager.HAS_PTY", False):
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        process_manager.active_processes["t1"] = ManagedProcess(
            task_id="t1", process=mock_process, master_fd=99, slave_fd=100
        )
        
        await process_manager.inject_prompt("t1", "Fix the bug")
        
        # In non-PTY environments, we write directly to the stdin pipe
        mock_process.stdin.write.assert_called_once_with(b"Fix the bug\n")
        mock_process.stdin.flush.assert_called_once()
