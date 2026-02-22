"""
shared/mocks/mock_mlflow.py — In-memory MLflow-compatible tracking client.

Implements the same interface as ``mlflow`` so the telemetry module can
run without a live MLflow server.  All data is stored in plain dicts.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


class MockMLflowClient:
    """In-memory mock of the MLflow tracking client.

    Implements ``start_run``, ``log_metric``, ``log_param``, ``set_tag``,
    ``end_run``, and ``search_runs`` with dict-backed storage so the
    telemetry collector works identically in dev and CI.

    Attributes:
        runs: All runs keyed by run_id.
    """

    def __init__(self) -> None:
        self.runs: dict[str, dict[str, Any]] = {}

    # ── Run lifecycle ───────────────────────────────────────────────────────

    def start_run(
        self,
        task_id: str | None = None,
        engine: str | None = None,
    ) -> str:
        """Start a new mock run and return its ID.

        Args:
            task_id: Optional Agent HQ task UUID to associate.
            engine: Optional engine name tag.

        Returns:
            A unique run ID string.
        """
        run_id = f"run-{uuid.uuid4().hex[:12]}"
        self.runs[run_id] = {
            "run_id": run_id,
            "status": "RUNNING",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": None,
            "metrics": {},
            "params": {},
            "tags": {},
            "artifacts": {},
        }
        if task_id:
            self.runs[run_id]["tags"]["task_id"] = task_id
        if engine:
            self.runs[run_id]["tags"]["engine"] = engine
        return run_id

    def log_metric(self, key: str, value: float, run_id: str | None = None) -> None:
        """Log a metric value to a run.

        If ``run_id`` is ``None``, the metric is logged to the most
        recently started run.

        Args:
            key: Metric name (e.g. ``"tokens_used"``, ``"cost_usd"``).
            value: Numeric metric value.
            run_id: Target run ID.  Defaults to the latest run.
        """
        rid = run_id or self._latest_run_id()
        if rid and rid in self.runs:
            self.runs[rid]["metrics"][key] = value

    def log_param(self, key: str, value: str, run_id: str | None = None) -> None:
        """Log a parameter to a run.

        Args:
            key: Param name (e.g. ``"agent_type"``, ``"budget_limit"``).
            value: Param value (always stored as string).
            run_id: Target run ID.  Defaults to the latest run.
        """
        rid = run_id or self._latest_run_id()
        if rid and rid in self.runs:
            self.runs[rid]["params"][key] = value

    def set_tag(self, key: str, value: str, run_id: str | None = None) -> None:
        """Set a tag on a run.

        Args:
            key: Tag name.
            value: Tag value.
            run_id: Target run ID.  Defaults to the latest run.
        """
        rid = run_id or self._latest_run_id()
        if rid and rid in self.runs:
            self.runs[rid]["tags"][key] = value

    def end_run(self, run_id: str | None = None, status: str = "FINISHED") -> None:
        """Mark a run as complete.

        Args:
            run_id: Run to end.  Defaults to the latest run.
            status: Final status (``"FINISHED"``, ``"FAILED"``, etc.).
        """
        rid = run_id or self._latest_run_id()
        if rid and rid in self.runs:
            self.runs[rid]["status"] = status
            self.runs[rid]["end_time"] = datetime.now(timezone.utc).isoformat()

    def log_text(self, text: str, artifact_file: str, run_id: str | None = None) -> None:
        """Mock storing text as an artifact."""
        rid = run_id or self._latest_run_id()
        if rid and rid in self.runs:
            self.runs[rid]["artifacts"][artifact_file] = text

    def get_artifact_text(self, artifact_file: str, run_id: str) -> str | None:
        """Mock retrieving text from an artifact."""
        if run_id in self.runs:
            return self.runs[run_id]["artifacts"].get(artifact_file)
        return None

    # ── Querying ────────────────────────────────────────────────────────────

    def search_runs(
        self,
        filter_string: str = "",
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        """Search stored runs with optional filtering.

        Supports simple ``tag.key = 'value'`` filters on tags.  Unrecognised
        filter strings return all runs.

        Args:
            filter_string: e.g. ``"tag.engine = 'claude-code'"``.
            max_results: Maximum number of runs to return.

        Returns:
            List of run dicts matching the filter.
        """
        results = list(self.runs.values())

        # Very basic tag filter: tag.{key} = '{value}'
        if filter_string:
            import re
            m = re.match(r"tag\.(\w+)\s*=\s*'([^']*)'", filter_string.strip())
            if m:
                tag_key, tag_val = m.group(1), m.group(2)
                results = [
                    r for r in results
                    if r["tags"].get(tag_key) == tag_val
                ]

        return results[:max_results]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Retrieve a single run by ID.

        Args:
            run_id: The run ID to look up.

        Returns:
            The run dict, or ``None`` if not found.
        """
        return self.runs.get(run_id)

    # ── Internals ───────────────────────────────────────────────────────────

    def _latest_run_id(self) -> str | None:
        """Return the ID of the most recently started run, or None."""
        if not self.runs:
            return None
        return list(self.runs.keys())[-1]

    @property
    def run_count(self) -> int:
        """Total number of runs tracked."""
        return len(self.runs)
