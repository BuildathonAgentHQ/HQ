"""
backend/app/telemetry/agent_telemetry.py — MLflow run lifecycle.

Integrates with MLflow (real Databricks-hosted or in-memory mock) to track
agent task executions as experiment runs, logging parameters, metrics,
and artifacts for the radar chart and leaderboard.

Graceful degradation:
  * ``settings.USE_DATABRICKS = True``  → real ``mlflow`` library
  * ``settings.USE_DATABRICKS = False`` → ``MockMLflowClient`` (no external deps)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from backend.app.config import Settings
from shared.schemas import (
    AgentLeaderboardEntry,
    GuardrailEvent,
    Task,
    TelemetryMetrics,
)

logger = logging.getLogger(__name__)


class AgentTelemetry:
    """Manages MLflow experiment tracking for agent tasks.

    Parameters
    ----------
    settings:
        Application settings.  ``USE_DATABRICKS`` controls whether the real
        ``mlflow`` library or the in-memory ``MockMLflowClient`` is used.
    """

    def __init__(self, settings: Settings) -> None:
        self.active_runs: dict[str, str] = {}  # task_id → run_id
        self._use_databricks: bool = settings.USE_DATABRICKS
        self._client: Any = None  # MockMLflowClient or real mlflow module

        if self._use_databricks:
            try:
                import mlflow

                mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
                mlflow.set_experiment("agent-hq")
                self._client = mlflow
                logger.info(
                    "AgentTelemetry: Databricks MLflow enabled → %s",
                    settings.MLFLOW_TRACKING_URI,
                )
            except Exception:
                logger.warning(
                    "AgentTelemetry: mlflow import failed; falling back to mock",
                    exc_info=True,
                )
                self._use_databricks = False
                self._init_mock()
        else:
            self._init_mock()

    # ── Helpers ──────────────────────────────────────────────────────────

    def _init_mock(self) -> None:
        from shared.mocks.mock_mlflow import MockMLflowClient

        self._client = MockMLflowClient()
        logger.info("AgentTelemetry: Using MockMLflowClient (in-memory)")

    # ── Run lifecycle ────────────────────────────────────────────────────

    async def start_tracking(self, task: Task) -> str:
        """Start an MLflow run for *task* and return its ``run_id``.

        Tags logged: ``tool``, ``task_uuid``, ``agent_type``,
        ``task_description`` (first 100 chars).
        """
        if self._use_databricks:
            run = self._client.start_run(run_name=f"task-{task.id[:8]}")
            run_id: str = run.info.run_id

            self._client.log_param(run_id, "start_time", datetime.now(timezone.utc).isoformat())
            self._client.set_tag(run_id, "tool", task.engine)
            self._client.set_tag(run_id, "task_uuid", task.id)
            self._client.set_tag(run_id, "agent_type", task.agent_type)
            self._client.set_tag(run_id, "task_description", task.task[:100])
        else:
            run_id = self._client.start_run(task_id=task.id, engine=task.engine)

            self._client.log_param("start_time", datetime.now(timezone.utc).isoformat(), run_id=run_id)
            self._client.set_tag("tool", task.engine, run_id=run_id)
            self._client.set_tag("task_uuid", task.id, run_id=run_id)
            self._client.set_tag("agent_type", task.agent_type, run_id=run_id)
            self._client.set_tag("task_description", task.task[:100], run_id=run_id)

        self.active_runs[task.id] = run_id
        logger.info("Started tracking task %s → run %s", task.id, run_id)
        return run_id

    async def log_token_usage(self, task_id: str, tokens: int, cost: float) -> None:
        """Log token consumption metrics for an active run."""
        run_id = self.active_runs.get(task_id)
        if not run_id:
            logger.warning("log_token_usage: no active run for task %s", task_id)
            return

        if self._use_databricks:
            self._client.log_metric(run_id, "token_count", tokens)
            self._client.log_metric(run_id, "cumulative_cost", cost)
        else:
            self._client.log_metric("token_count", tokens, run_id=run_id)
            self._client.log_metric("cumulative_cost", cost, run_id=run_id)

    async def log_guardrail_event(self, task_id: str, event: GuardrailEvent) -> None:
        """Log a guardrail check result as MLflow metrics and tags."""
        run_id = self.active_runs.get(task_id)
        if not run_id:
            logger.warning("log_guardrail_event: no active run for task %s", task_id)
            return

        if self._use_databricks:
            # Increment counters
            self._client.log_metric(run_id, "guardrail_checks", 1)
            if not event.passed:
                self._client.log_metric(run_id, "guardrail_failures", 1)
            self._client.set_tag(run_id, f"guardrail_{event.check_type}", str(event.passed))
        else:
            self._client.log_metric("guardrail_checks", 1, run_id=run_id)
            if not event.passed:
                self._client.log_metric("guardrail_failures", 1, run_id=run_id)
            self._client.set_tag(f"guardrail_{event.check_type}", str(event.passed), run_id=run_id)

    async def end_tracking(self, task: Task) -> None:
        """End the MLflow run and log final metrics."""
        run_id = self.active_runs.pop(task.id, None)
        if not run_id:
            logger.warning("end_tracking: no active run for task %s", task.id)
            return

        duration = (task.updated_at - task.created_at).total_seconds()

        if self._use_databricks:
            self._client.log_metric(run_id, "exit_code", float(task.exit_code if task.exit_code is not None else -1))
            self._client.log_metric(run_id, "total_duration_seconds", duration)
            self._client.log_metric(run_id, "total_tokens", float(task.token_count))
            self._client.log_metric(run_id, "total_cost", float(task.budget_used))
            self._client.set_tag(run_id, "status", task.status)
            self._client.end_run()
        else:
            self._client.log_metric("exit_code", float(task.exit_code if task.exit_code is not None else -1), run_id=run_id)
            self._client.log_metric("total_duration_seconds", duration, run_id=run_id)
            self._client.log_metric("total_tokens", float(task.token_count), run_id=run_id)
            self._client.log_metric("total_cost", float(task.budget_used), run_id=run_id)
            self._client.set_tag("status", task.status, run_id=run_id)
            self._client.end_run(run_id=run_id, status="FINISHED" if task.status == "success" else "FAILED")

        logger.info("Ended tracking for task %s (run %s)", task.id, run_id)

    # ── Analytics ────────────────────────────────────────────────────────

    async def get_radar_metrics(self, days: int = 30) -> TelemetryMetrics:
        """Compute radar-chart scores from MLflow runs over the last *days*.

        Scores:
            - **security**: % of runs with no security guardrail failures
            - **stability**: % of runs that exited successfully
            - **quality**: % of runs with no lint guardrail failures
            - **speed**: normalized inverse of average duration

        All values are scaled to 0–100 using ``MinMaxScaler``.
        Missing data defaults to 50 (middle score).
        """
        runs = self._search_all_runs()
        if not runs:
            return TelemetryMetrics(security=50, stability=50, quality=50, speed=50)

        df = self._runs_to_dataframe(runs, days=days)
        if df.empty:
            return TelemetryMetrics(security=50, stability=50, quality=50, speed=50)

        # ── Security: fraction of runs with no security failures ─────────
        security_raw = self._safe_ratio(
            df, tag_key="guardrail_security", pass_value="True"
        )

        # ── Stability: fraction of successful exit codes (0) ─────────────
        if "exit_code" in df.columns:
            success_count = (df["exit_code"] == 0).sum()
            stability_raw = (success_count / len(df)) * 100 if len(df) else 50
        else:
            stability_raw = 50.0

        # ── Quality: fraction of runs with no lint failures ──────────────
        quality_raw = self._safe_ratio(
            df, tag_key="guardrail_lint", pass_value="True"
        )

        # ── Speed: inverse normalisation (faster = higher) ───────────────
        if "total_duration_seconds" in df.columns:
            durations = df["total_duration_seconds"].dropna()
            if len(durations) > 0 and durations.max() > 0:
                # Invert: shorter duration → higher score
                speed_raw = (1 - durations.mean() / durations.max()) * 100
                speed_raw = max(0.0, min(100.0, speed_raw))
            else:
                speed_raw = 50.0
        else:
            speed_raw = 50.0

        # ── Normalise to 0-100 via MinMaxScaler ──────────────────────────
        # Values are already computed as 0–100 percentages.
        # Clamp to bounds and return directly.
        def _clamp(v: float) -> float:
            return max(0.0, min(100.0, v))

        return TelemetryMetrics(
            security=round(_clamp(security_raw), 1),
            stability=round(_clamp(stability_raw), 1),
            quality=round(_clamp(quality_raw), 1),
            speed=round(_clamp(speed_raw), 1),
        )

    async def get_leaderboard(self) -> list[AgentLeaderboardEntry]:
        """Build the agent efficiency leaderboard grouped by engine.

        Sorted by ``success_rate`` descending.
        """
        runs = self._search_all_runs()
        if not runs:
            return []

        df = self._runs_to_dataframe(runs)
        if df.empty or "engine" not in df.columns:
            return []

        results: list[AgentLeaderboardEntry] = []

        for engine, group in df.groupby("engine"):
            total = len(group)
            success = (group.get("exit_code", pd.Series(dtype=float)) == 0).sum()

            results.append(
                AgentLeaderboardEntry(
                    engine=str(engine),
                    tasks_completed=total,
                    success_rate=round(float(success / total), 3) if total else 0.0,
                    avg_duration_seconds=round(
                        float(group.get("total_duration_seconds", pd.Series(dtype=float)).mean() or 0), 2
                    ),
                    avg_cost_dollars=round(
                        float(group.get("total_cost", pd.Series(dtype=float)).mean() or 0), 4
                    ),
                    total_tokens=int(group.get("total_tokens", pd.Series(dtype=float)).sum() or 0),
                )
            )

        results.sort(key=lambda e: e.success_rate, reverse=True)
        return results

    # ── Internal helpers ─────────────────────────────────────────────────

    def _search_all_runs(self) -> list[dict[str, Any]]:
        """Retrieve all runs from the MLflow back-end."""
        try:
            if self._use_databricks:
                import mlflow

                experiment = mlflow.get_experiment_by_name("agent-hq")
                if experiment is None:
                    return []
                runs = mlflow.search_runs(
                    experiment_ids=[experiment.experiment_id],
                    output_format="list",
                )
                # Convert MLflow Run objects → dicts
                return [
                    {
                        "run_id": r.info.run_id,
                        "status": r.info.status,
                        "start_time": r.info.start_time,
                        "end_time": r.info.end_time,
                        "metrics": r.data.metrics,
                        "params": r.data.params,
                        "tags": r.data.tags,
                    }
                    for r in runs
                ]
            else:
                return self._client.search_runs()
        except Exception:
            logger.warning("Failed to search runs", exc_info=True)
            return []

    def _runs_to_dataframe(
        self,
        runs: list[dict[str, Any]],
        days: Optional[int] = None,
    ) -> pd.DataFrame:
        """Flatten runs into a pandas DataFrame for aggregation.

        Columns include top-level fields, plus all metrics and tags
        promoted to columns.
        """
        rows: list[dict[str, Any]] = []
        for r in runs:
            row: dict[str, Any] = {
                "run_id": r.get("run_id"),
                "status": r.get("status"),
                "start_time": r.get("start_time"),
                "end_time": r.get("end_time"),
            }
            row.update(r.get("metrics", {}))
            row.update(r.get("tags", {}))
            rows.append(row)

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        # ── Time filtering ───────────────────────────────────────────────
        if days is not None and "start_time" in df.columns:
            try:
                df["start_time"] = pd.to_datetime(df["start_time"], utc=True)
                cutoff = datetime.now(timezone.utc) - pd.Timedelta(days=days)
                df = df[df["start_time"] >= cutoff]
            except Exception:
                pass  # If timestamps are malformed, skip filtering

        return df

    @staticmethod
    def _safe_ratio(
        df: pd.DataFrame,
        tag_key: str,
        pass_value: str = "True",
    ) -> float:
        """Percentage of rows where *tag_key* equals *pass_value*.

        Returns 50.0 (neutral) if the column does not exist.
        """
        if tag_key not in df.columns:
            return 50.0
        col = df[tag_key]
        total = col.notna().sum()
        if total == 0:
            return 50.0
        passed = (col == pass_value).sum()
        return (passed / total) * 100
