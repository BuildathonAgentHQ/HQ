"""
backend/app/telemetry/metrics_api.py — Radar chart, leaderboard, history,
FinOps & CSV export.

Mounted at ``/api/metrics`` in ``main.py``.  All endpoints delegate to
``AgentTelemetry`` which reads from MLflow (real or mock).
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.app.config import Settings, settings
from backend.app.telemetry.agent_telemetry import AgentTelemetry
from shared.schemas import AgentLeaderboardEntry, TelemetryMetrics

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Module-level telemetry instance ──────────────────────────────────────────
_telemetry = AgentTelemetry(settings)


# ── FinOps Pydantic model ────────────────────────────────────────────────────


class TopCostTask(BaseModel):
    """A single high-cost task entry for the FinOps report."""

    task_id: str
    engine: str = ""
    cost: float = Field(..., ge=0)


class FinOpsReport(BaseModel):
    """Aggregate financial operations data."""

    total_spend_today: float = Field(0.0, ge=0, description="Sum of all task costs today (UTC).")
    total_spend_30d: float = Field(0.0, ge=0, description="Sum of all task costs in the last 30 days.")
    avg_cost_per_task: float = Field(0.0, ge=0, description="Average cost per task (30d).")
    projected_monthly_burn: float = Field(
        0.0, ge=0, description="Extrapolated 30-day spend from daily average."
    )
    top_cost_tasks: list[TopCostTask] = Field(
        default_factory=list,
        description="Top 5 most expensive tasks.",
    )


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/radar", response_model=TelemetryMetrics)
async def get_radar_metrics() -> TelemetryMetrics:
    """Return normalised 0-100 radar-chart scores.

    Used by the frontend Health Radar component.  Returns default 50s
    on a fresh install with no data.
    """
    return await _telemetry.get_radar_metrics()


@router.get("/leaderboard", response_model=list[AgentLeaderboardEntry])
async def get_leaderboard() -> list[AgentLeaderboardEntry]:
    """Return the agent efficiency leaderboard, sorted by success rate."""
    return await _telemetry.get_leaderboard()


@router.get("/history", response_model=list[TelemetryMetrics])
async def get_metrics_history(
    since: Optional[datetime] = Query(
        None,
        description="ISO-8601 timestamp; return metrics recorded after this time.",
    ),
) -> list[TelemetryMetrics]:
    """Return historical radar-chart snapshots for the time-travel slider.

    Splits the period between *since* and now into 10 evenly-spaced
    buckets and produces a ``TelemetryMetrics`` snapshot per bucket.
    """
    now = datetime.now(timezone.utc)
    if since is None:
        since = now - pd.Timedelta(days=7)
    elif since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)

    total_seconds = (now - since).total_seconds()
    if total_seconds <= 0:
        return []

    num_buckets = 10
    bucket_size = total_seconds / num_buckets

    history: list[TelemetryMetrics] = []
    for i in range(num_buckets):
        bucket_end_days_ago = ((num_buckets - i) * bucket_size) / 86400
        metrics = await _telemetry.get_radar_metrics(days=max(1, int(bucket_end_days_ago)))
        metrics.timestamp = since + pd.Timedelta(seconds=bucket_size * (i + 1))
        history.append(metrics)

    return history


@router.get("/finops", response_model=FinOpsReport)
async def get_finops() -> FinOpsReport:
    """Return aggregate financial data for the FinOps dashboard."""
    runs = _telemetry._search_all_runs()
    if not runs:
        return FinOpsReport()

    df = _telemetry._runs_to_dataframe(runs)
    if df.empty:
        return FinOpsReport()

    # ── Total spend: last 30 days ────────────────────────────────────
    now = datetime.now(timezone.utc)
    cost_col = "total_cost"
    if cost_col not in df.columns:
        cost_col = "cumulative_cost"
    if cost_col not in df.columns:
        return FinOpsReport()

    df[cost_col] = pd.to_numeric(df[cost_col], errors="coerce").fillna(0)

    # Parse start_time for date filtering
    if "start_time" in df.columns:
        df["start_time"] = pd.to_datetime(df["start_time"], utc=True, errors="coerce")
        cutoff_30d = now - pd.Timedelta(days=30)
        df_30d = df[df["start_time"] >= cutoff_30d]
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        df_today = df[df["start_time"] >= today_start]
    else:
        df_30d = df
        df_today = df

    total_spend_today = float(df_today[cost_col].sum())
    total_spend_30d = float(df_30d[cost_col].sum())
    n_tasks_30d = len(df_30d)
    avg_cost = total_spend_30d / n_tasks_30d if n_tasks_30d else 0.0

    # Daily average → projected monthly burn
    if "start_time" in df_30d.columns and len(df_30d) > 0:
        span_days = max(1, (now - df_30d["start_time"].min()).days)
        daily_avg = total_spend_30d / span_days
        projected = daily_avg * 30
    else:
        projected = 0.0

    # ── Top 5 most expensive tasks ───────────────────────────────────
    task_id_col = "task_uuid" if "task_uuid" in df_30d.columns else "task_id"
    engine_col = "engine" if "engine" in df_30d.columns else "tool"

    top_df = df_30d.nlargest(5, cost_col)
    top_cost_tasks = [
        TopCostTask(
            task_id=str(row.get(task_id_col, "unknown")),
            engine=str(row.get(engine_col, "")),
            cost=round(float(row.get(cost_col, 0)), 4),
        )
        for _, row in top_df.iterrows()
    ]

    return FinOpsReport(
        total_spend_today=round(total_spend_today, 4),
        total_spend_30d=round(total_spend_30d, 4),
        avg_cost_per_task=round(avg_cost, 4),
        projected_monthly_burn=round(projected, 4),
        top_cost_tasks=top_cost_tasks,
    )


@router.get("/export")
async def export_csv() -> StreamingResponse:
    """Export all telemetry data as CSV.

    Columns: task_id, engine, agent_type, status, duration_seconds,
    token_count, cost, created_at.
    """
    runs = _telemetry._search_all_runs()
    df = _telemetry._runs_to_dataframe(runs) if runs else pd.DataFrame()

    buf = io.StringIO()
    writer = csv.writer(buf)

    # Header
    columns = [
        "task_id", "engine", "agent_type", "status",
        "duration_seconds", "token_count", "cost", "created_at",
    ]
    writer.writerow(columns)

    if not df.empty:
        # Resolve column aliases
        task_col = "task_uuid" if "task_uuid" in df.columns else "task_id"
        engine_col = "engine" if "engine" in df.columns else "tool"
        cost_col = "total_cost" if "total_cost" in df.columns else "cumulative_cost"
        duration_col = "total_duration_seconds"
        tokens_col = "total_tokens" if "total_tokens" in df.columns else "token_count"
        time_col = "start_time"

        for _, row in df.iterrows():
            writer.writerow([
                row.get(task_col, ""),
                row.get(engine_col, ""),
                row.get("agent_type", ""),
                row.get("status", ""),
                round(float(row.get(duration_col, 0) or 0), 2),
                int(float(row.get(tokens_col, 0) or 0)),
                round(float(row.get(cost_col, 0) or 0), 6),
                row.get(time_col, ""),
            ])

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=agent_hq_telemetry.csv"},
    )
