"""Tests for guardrails: destructive command detection and linter runner."""
from __future__ import annotations

import asyncio
import os
import tempfile

import pytest

from app.guardrails.destructive_interceptor import DestructiveActionInterceptor
from app.guardrails.linter_runner import LinterRunner
from app.guardrails.approval_gate import ApprovalGate
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
