"""Tests for guardrails: destructive command detection, linter runner, approval gate, escalation."""
from __future__ import annotations

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.guardrails.destructive_interceptor import DestructiveActionInterceptor
from app.guardrails.linter_runner import LinterRunner
from app.guardrails.approval_gate import ApprovalGate
from app.guardrails.escalation import EscalationManager
from shared.schemas import ApprovalRequest, GuardrailEvent


class TestDestructiveInterceptor:
    @pytest.fixture
    def interceptor(self):
        return DestructiveActionInterceptor()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("cmd", [
        "rm -rf /home/user/project",
        "rm -rf .",
        "rm -r /src",
        "DROP TABLE users;",
        "drop database production;",
        "TRUNCATE TABLE orders;",
        "git push --force origin main",
        "git push -f",
        "git reset --hard HEAD~5",
        "DELETE FROM users WHERE 1=1",
        "chmod 777 /etc/passwd",
        "sudo rm -rf /",
        "dd if=/dev/zero of=/dev/sda",
    ])
    async def test_blocks_dangerous_commands(self, interceptor, cmd):
        result = await interceptor.scan_command("t1", cmd)
        assert result is not None, f"MISSED dangerous command: {cmd}"
        assert isinstance(result, ApprovalRequest)
        assert len(result.description) > 10

    @pytest.mark.asyncio
    @pytest.mark.parametrize("cmd", [
        "ls -la",
        "cat README.md",
        "python manage.py runserver",
        "npm test",
        "git add .",
        'git commit -m "fix bug"',
        "git push origin feature-branch",
        "pip install requests",
        "mkdir new_directory",
        "cp file1.txt file2.txt",
        "ruff check .",
    ])
    async def test_allows_safe_commands(self, interceptor, cmd):
        result = await interceptor.scan_command("t1", cmd)
        assert result is None, f"FALSE POSITIVE on safe command: {cmd}"

    @pytest.mark.asyncio
    async def test_approval_request_has_options(self, interceptor):
        """ApprovalRequest should always have exactly 2 options."""
        result = await interceptor.scan_command("t1", "rm -rf /important")
        assert result is not None
        assert len(result.options) == 2
        assert "Approve" in result.options[0]
        assert "Reject" in result.options[1]


class TestLinterRunner:
    @pytest.fixture
    def runner(self):
        return LinterRunner()

    @pytest.mark.asyncio
    async def test_returns_guardrail_event(self, runner):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def hello():\n    return 'world'\n")
            path = f.name
        try:
            result = await runner.run_checks(path) if asyncio.iscoroutinefunction(runner.run_checks) else runner.run_checks(path)
            assert isinstance(result, GuardrailEvent)
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_handles_nonexistent_file(self, runner):
        result = await runner.run_checks("/nonexistent/file.py") if asyncio.iscoroutinefunction(runner.run_checks) else runner.run_checks("/nonexistent/file.py")
        assert isinstance(result, GuardrailEvent)

    @pytest.mark.asyncio
    async def test_unknown_extension_passes(self, runner):
        """Files with unrecognized extensions should pass (no linter to run)."""
        result = await runner.run_checks("/some/file.txt")
        assert isinstance(result, GuardrailEvent)
        assert result.passed is True


class TestApprovalGate:
    def test_add_and_get_pending(self):
        gate = ApprovalGate()
        req = ApprovalRequest(
            task_id="t1", action_type="destructive_cmd",
            command="rm -rf /", description="Delete everything",
            options=["Approve", "Reject"],
        )
        gate.add_pending("t1", req)
        pending = gate.get_pending("t1")
        assert pending is not None
        assert pending.task_id == "t1"

    def test_resolve_removes_pending(self):
        gate = ApprovalGate()
        req = ApprovalRequest(
            task_id="t1", action_type="destructive_cmd",
            command="rm -rf /", description="Delete everything",
            options=["Approve", "Reject"],
        )
        gate.add_pending("t1", req)
        gate.resolve("t1", "reject")
        assert gate.get_pending("t1") is None

    def test_resolve_returns_choice(self):
        gate = ApprovalGate()
        req = ApprovalRequest(
            task_id="t1", action_type="destructive_cmd",
            command="rm -rf /", description="Delete everything",
            options=["Approve", "Reject"],
        )
        gate.add_pending("t1", req)
        choice = gate.resolve("t1", "Approve")
        assert choice == "Approve"

    def test_resolve_unknown_returns_none(self):
        gate = ApprovalGate()
        result = gate.resolve("unknown-task", "Approve")
        assert result is None

    def test_get_pending_unknown_returns_none(self):
        gate = ApprovalGate()
        assert gate.get_pending("no-such-task") is None


class TestEscalationManager:
    @pytest.fixture
    def mock_process_manager(self):
        pm = MagicMock()
        pm.inject_prompt = AsyncMock()
        pm.suspend_process = AsyncMock()
        return pm

    @pytest.fixture
    def mock_event_router(self):
        er = MagicMock()
        er.emit = AsyncMock()
        return er

    @pytest.fixture
    def manager(self, mock_process_manager, mock_event_router):
        return EscalationManager(mock_process_manager, mock_event_router)

    @pytest.fixture
    def failing_event(self):
        return GuardrailEvent(
            task_id="t1",
            file_path="src/main.py",
            check_type="lint",
            passed=False,
            error_msg="ruff: F401 'os' imported but unused at line 5",
            strike_count=1,
        )

    @pytest.mark.asyncio
    async def test_first_strike_injects_fix_prompt(self, manager, mock_process_manager, failing_event):
        await manager.handle_guardrail_failure("t1", failing_event)
        assert manager._strikes["t1"] == 1
        mock_process_manager.inject_prompt.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_success_resets_strikes(self, manager, failing_event):
        await manager.handle_guardrail_failure("t1", failing_event)
        assert manager._strikes["t1"] == 1
        await manager.handle_guardrail_success("t1")
        assert manager._strikes["t1"] == 0

    @pytest.mark.asyncio
    async def test_three_strikes_suspends_agent(self, manager, mock_process_manager, failing_event):
        """Three consecutive failures should suspend and trigger debate."""
        for _ in range(3):
            await manager.handle_guardrail_failure("t1", failing_event)
        assert manager._strikes["t1"] == 3
        mock_process_manager.suspend_process.assert_awaited_once_with("t1")

    @pytest.mark.asyncio
    async def test_success_on_unknown_task_is_noop(self, manager):
        """Calling success on a task with no strikes should not error."""
        await manager.handle_guardrail_success("unknown-task")
        assert manager._strikes.get("unknown-task", 0) == 0
