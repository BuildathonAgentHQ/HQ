"""
backend/app/telemetry/token_tracker.py — Real-time token/cost tracking.

Monitors token consumption across agent tasks and calculates estimated
cost.  Supports both explicit token counts (when available from the API)
and a character-based heuristic for subprocess-style agents where token
counts are not directly accessible.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Default pricing (USD per 1 M tokens) ────────────────────────────────────
# Configurable via the pricing dict passed to __init__.

DEFAULT_PRICING: dict[str, dict[str, float]] = {
    "claude-code": {"input": 3.00, "output": 15.00},
    "cursor-cli":  {"input": 2.00, "output": 10.00},
    "default":     {"input": 1.00, "output": 5.00},
}


@dataclass
class TokenUsageRecord:
    """Running totals for a single task."""

    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0


class TokenTracker:
    """Tracks token usage and cost per task in real-time.

    Parameters
    ----------
    telemetry:
        ``AgentTelemetry`` instance — ``log_token_usage`` is called on
        every update so MLflow stays in sync.
    pricing:
        Per-engine pricing (USD per 1 M tokens).  Keys are engine names
        (e.g. ``"claude-code"``), values are dicts with ``"input"`` and
        ``"output"`` keys.  Falls back to ``DEFAULT_PRICING``.
    """

    def __init__(
        self,
        telemetry: Any,  # AgentTelemetry — use Any to avoid circular import
        pricing: dict[str, dict[str, float]] | None = None,
    ) -> None:
        from backend.app.telemetry.agent_telemetry import AgentTelemetry

        self._telemetry: AgentTelemetry = telemetry
        self._pricing = pricing or DEFAULT_PRICING
        self.token_counts: dict[str, TokenUsageRecord] = {}

    # ── Core tracking ────────────────────────────────────────────────────

    async def track_usage(
        self,
        task_id: str,
        input_tokens: int,
        output_tokens: int,
        engine: str = "claude-code",
    ) -> float:
        """Accumulate tokens for *task_id*, calculate cost, log to telemetry.

        Parameters
        ----------
        task_id:
            UUID of the task.
        input_tokens:
            Number of input (prompt) tokens consumed in this increment.
        output_tokens:
            Number of output (completion) tokens consumed in this increment.
        engine:
            Engine name for pricing lookup.

        Returns
        -------
        float
            Updated **cumulative** cost for this task (USD).
        """
        record = self.token_counts.setdefault(task_id, TokenUsageRecord())

        record.input_tokens += input_tokens
        record.output_tokens += output_tokens

        # Cost for THIS increment
        prices = self._pricing.get(engine, self._pricing.get("default", DEFAULT_PRICING["default"]))
        increment_cost = (
            (input_tokens / 1_000_000) * prices["input"]
            + (output_tokens / 1_000_000) * prices["output"]
        )
        record.cost += increment_cost

        # Sync with MLflow
        total_tokens = record.input_tokens + record.output_tokens
        await self._telemetry.log_token_usage(task_id, total_tokens, record.cost)

        return record.cost

    # ── Heuristic estimator ──────────────────────────────────────────────

    async def estimate_from_chars(
        self,
        task_id: str,
        char_count: int,
        engine: str = "claude-code",
        chars_per_token: float = 4.0,
        safety_margin: float = 1.3,
    ) -> float:
        """Estimate token usage from raw character count.

        When we don't have direct access to token counts (e.g. from a
        subprocess's stdout), we can approximate: ~4 characters per token,
        multiplied by a 1.3× safety margin.

        The estimated tokens are split 50/50 between input and output for
        costing purposes (a rough but directional approximation).

        Returns the updated cumulative cost.
        """
        estimated_tokens = int((char_count / chars_per_token) * safety_margin)
        half = estimated_tokens // 2
        return await self.track_usage(task_id, half, half, engine)

    # ── Query ────────────────────────────────────────────────────────────

    def get_usage(self, task_id: str) -> dict[str, Any]:
        """Return current totals for *task_id*.

        Returns
        -------
        dict
            ``{"input_tokens": int, "output_tokens": int, "cost": float}``
        """
        record = self.token_counts.get(task_id, TokenUsageRecord())
        return {
            "input_tokens": record.input_tokens,
            "output_tokens": record.output_tokens,
            "cost": record.cost,
        }
