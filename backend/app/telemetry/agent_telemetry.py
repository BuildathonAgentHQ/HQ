"""
backend/app/telemetry/agent_telemetry.py — MLflow run lifecycle.

Integrates with MLflow to track agent task executions as experiment runs,
logging parameters, metrics, and artifacts for analysis.
"""

from __future__ import annotations

from typing import Any, Optional

from shared.schemas import AgentEngine, Task, TokenUsage


class AgentTelemetry:
    """Manages MLflow experiment tracking for agent tasks.

    Attributes:
        tracking_uri: MLflow tracking server URI.
        experiment_name: MLflow experiment name.
        active_runs: Dict mapping task_id → MLflow run_id.
    """

    def __init__(self, tracking_uri: str, experiment_name: str = "agent-hq") -> None:
        self.tracking_uri = tracking_uri
        self.experiment_name = experiment_name
        self.active_runs: dict[str, str] = {}
        # TODO: Initialize MLflow client with tracking_uri

    async def start_run(self, task: Task) -> str:
        """Start an MLflow run for a task.

        Args:
            task: The Task being started.

        Returns:
            MLflow run_id.

        TODO:
            - Create MLflow run with task metadata as parameters
            - Log: task_id, engine, prompt, repo_path, budget_limit
            - Store run_id in active_runs
        """
        # TODO: Implement MLflow run start
        raise NotImplementedError("AgentTelemetry.start_run not yet implemented")

    async def log_metrics(
        self,
        task_id: str,
        metrics: dict[str, float],
        step: Optional[int] = None,
    ) -> None:
        """Log metrics to an active MLflow run.

        Args:
            task_id: The task whose run to log to.
            metrics: Key-value pairs of metric names → values.
            step: Optional step number for time-series metrics.

        TODO:
            - Resolve task_id → run_id
            - Log each metric via MLflow client
        """
        # TODO: Implement metric logging
        raise NotImplementedError("AgentTelemetry.log_metrics not yet implemented")

    async def end_run(self, task_id: str, status: str = "FINISHED") -> None:
        """End an MLflow run.

        Args:
            task_id: The task whose run to end.
            status: Final run status (FINISHED, FAILED, KILLED).

        TODO:
            - End the MLflow run with the given status
            - Remove from active_runs
        """
        # TODO: Implement run end
        raise NotImplementedError("AgentTelemetry.end_run not yet implemented")

    async def log_token_usage(self, task_id: str, usage: TokenUsage) -> None:
        """Log token usage metrics for a task.

        Args:
            task_id: The task to log for.
            usage: TokenUsage with input/output/total tokens and cost.

        TODO:
            - Log input_tokens, output_tokens, total_tokens, cost_usd
        """
        # TODO: Implement token usage logging
        raise NotImplementedError("AgentTelemetry.log_token_usage not yet implemented")
