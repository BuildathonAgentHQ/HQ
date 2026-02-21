"""Tests for telemetry: token tracking, budget enforcement, radar metrics."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import Settings
from app.telemetry.agent_telemetry import AgentTelemetry
from app.telemetry.budget_enforcer import BudgetEnforcer
from app.telemetry.token_tracker import TokenTracker
from shared.schemas import Task, TelemetryMetrics


@pytest.fixture
def settings():
    return Settings(USE_DATABRICKS=False, USE_NEMOTRON=False)


@pytest.fixture
def telemetry(settings):
    return AgentTelemetry(settings)


@pytest.fixture
def mock_event_router():
    router = MagicMock()
    router.emit = AsyncMock()
    router.emit_budget_exceeded = AsyncMock()
    router.emit_status_update = AsyncMock()
    return router


class TestAgentTelemetry:
    @pytest.mark.asyncio
    async def test_start_and_end_tracking(self, telemetry):
        task = Task(
            id="t-tel", task="Test", engine="claude-code",
            agent_type="general", status="running", budget_limit=2.0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        run_id = await telemetry.start_tracking(task)
        assert run_id is not None
        await telemetry.end_tracking(task)

    @pytest.mark.asyncio
    async def test_get_radar_metrics_returns_valid(self, telemetry):
        metrics = await telemetry.get_radar_metrics()
        assert isinstance(metrics, TelemetryMetrics)
        assert 0 <= metrics.security <= 100
        assert 0 <= metrics.stability <= 100
        assert 0 <= metrics.quality <= 100
        assert 0 <= metrics.speed <= 100


class TestTokenTracker:
    @pytest.mark.asyncio
    async def test_track_usage_returns_cost(self, telemetry):
        tracker = TokenTracker(telemetry)
        cost = await tracker.track_usage("t1", 1000, 500)
        assert isinstance(cost, float)
        assert cost > 0

    @pytest.mark.asyncio
    async def test_get_usage_returns_dict(self, telemetry):
        tracker = TokenTracker(telemetry)
        await tracker.track_usage("t1", 1000, 500)
        usage = tracker.get_usage("t1")
        assert usage is not None
        assert "input_tokens" in usage
        assert "output_tokens" in usage
        assert "cost" in usage

    @pytest.mark.asyncio
    async def test_accumulates_across_calls(self, telemetry):
        tracker = TokenTracker(telemetry)
        await tracker.track_usage("t1", 1000, 500)
        await tracker.track_usage("t1", 2000, 1000)
        usage = tracker.get_usage("t1")
        assert usage["input_tokens"] == 3000
        assert usage["output_tokens"] == 1500


class TestBudgetEnforcer:
    @pytest.mark.asyncio
    async def test_green_zone_returns_true(self, mock_event_router):
        enforcer = BudgetEnforcer(None, mock_event_router, default_limit=2.0)
        result = await enforcer.check_budget("t1", 1.0, 2.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_warning_zone_at_80_pct(self, mock_event_router):
        enforcer = BudgetEnforcer(None, mock_event_router, default_limit=2.0)
        result = await enforcer.check_budget("t1", 1.70, 2.0)
        assert result is True
        assert mock_event_router.emit_status_update.called

    @pytest.mark.asyncio
    async def test_exceeded_zone_returns_false(self, mock_event_router):
        enforcer = BudgetEnforcer(None, mock_event_router, default_limit=2.0)
        result = await enforcer.check_budget("t1", 2.50, 2.0)
        assert result is False
