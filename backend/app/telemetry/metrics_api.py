"""
backend/app/telemetry/metrics_api.py — Radar chart, leaderboard & history.

Mounted at ``/api/metrics`` in ``main.py``.  Returns mock telemetry data
from ``shared/mocks/mock_data.py`` until the real collector is wired.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query

from shared.schemas import AgentLeaderboardEntry, TelemetryMetrics
from shared.mocks.mock_data import SAMPLE_LEADERBOARD, SAMPLE_RADAR_METRICS

router = APIRouter()


@router.get("/radar", response_model=TelemetryMetrics)
async def get_radar_metrics() -> TelemetryMetrics:
    """Return normalised 0-100 radar-chart scores.

    Used by the frontend Health Radar component.
    """
    return SAMPLE_RADAR_METRICS


@router.get("/leaderboard", response_model=list[AgentLeaderboardEntry])
async def get_leaderboard() -> list[AgentLeaderboardEntry]:
    """Return the agent efficiency leaderboard, sorted by success rate."""
    return sorted(SAMPLE_LEADERBOARD, key=lambda e: e.success_rate, reverse=True)


@router.get("/history", response_model=list[TelemetryMetrics])
async def get_metrics_history(
    since: Optional[datetime] = Query(
        None,
        description="ISO-8601 timestamp; return metrics recorded after this time.",
    ),
) -> list[TelemetryMetrics]:
    """Return historical radar-chart snapshots.

    In mock mode this returns 5 data points with slightly varied scores
    so the frontend can render a trend graph.

    Args:
        since: Optional lower-bound timestamp (ignored in mock mode).
    """
    import random

    base = SAMPLE_RADAR_METRICS
    history: list[TelemetryMetrics] = []
    for i in range(5):
        jitter = lambda v: round(max(0, min(100, v + random.uniform(-5, 5))), 1)
        history.append(
            TelemetryMetrics(
                security=jitter(base.security),
                stability=jitter(base.stability),
                quality=jitter(base.quality),
                speed=jitter(base.speed),
                timestamp=datetime(2026, 2, 20, 10 + i, 0, tzinfo=timezone.utc),
            )
        )
    return history
