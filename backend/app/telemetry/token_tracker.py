"""
backend/app/telemetry/token_tracker.py — Real-time token/cost tracking.

Monitors token consumption across agent tasks and calculates
estimated cost based on per-model pricing.
"""

from __future__ import annotations

from shared.schemas import AgentEngine, TokenUsage


# ── Per-model pricing (USD per 1K tokens) ────────────────────────────────────
# TODO: Update with actual pricing
MODEL_PRICING: dict[AgentEngine, dict[str, float]] = {
    AgentEngine.CLAUDE: {"input": 0.003, "output": 0.015},
    AgentEngine.CODEX: {"input": 0.002, "output": 0.010},
    AgentEngine.GEMINI: {"input": 0.001, "output": 0.005},
    AgentEngine.CUSTOM: {"input": 0.001, "output": 0.005},
}


class TokenTracker:
    """Tracks token usage and estimates cost per task in real-time.

    Attributes:
        usage_by_task: Dict mapping task_id → accumulated TokenUsage.
    """

    def __init__(self) -> None:
        self.usage_by_task: dict[str, TokenUsage] = {}

    def record_tokens(
        self,
        task_id: str,
        engine: AgentEngine,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> TokenUsage:
        """Record token usage for a task and update running totals.

        Args:
            task_id: The task to record for.
            engine: The agent engine (for cost calculation).
            input_tokens: Number of input tokens consumed.
            output_tokens: Number of output tokens generated.

        Returns:
            Updated TokenUsage with new totals and estimated cost.

        TODO:
            - Get or create TokenUsage for task_id
            - Add input_tokens and output_tokens to running totals
            - Calculate cost based on MODEL_PRICING
            - Emit TOKEN_UPDATE event via WebSocket
        """
        # TODO: Implement token recording
        raise NotImplementedError("TokenTracker.record_tokens not yet implemented")

    def get_usage(self, task_id: str) -> TokenUsage:
        """Get current token usage for a task.

        Args:
            task_id: The task to look up.

        Returns:
            TokenUsage for the task, or empty TokenUsage if not found.
        """
        return self.usage_by_task.get(task_id, TokenUsage())

    def estimate_cost(
        self,
        engine: AgentEngine,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate cost in USD for a given token count.

        Args:
            engine: Agent engine for pricing lookup.
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.

        Returns:
            Estimated cost in USD.

        TODO:
            - Look up pricing for the engine
            - Calculate: (input * input_rate + output * output_rate) / 1000
        """
        # TODO: Implement cost estimation
        pricing = MODEL_PRICING.get(engine, MODEL_PRICING[AgentEngine.CUSTOM])
        return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1000
