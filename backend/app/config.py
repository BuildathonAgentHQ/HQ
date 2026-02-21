"""
backend/app/config.py — Application settings via pydantic-settings.

Reads configuration from environment variables (or .env file) and
exposes a single ``settings`` instance used throughout the backend.

Feature flags allow graceful degradation — if an external service is
not configured, Agent HQ falls back to mock implementations so the
demo always works.
"""

from __future__ import annotations

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Centralized application configuration.

    All values can be overridden via environment variables or a ``.env`` file.
    Feature flags (``use_*``) control graceful degradation to mocks.
    """

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── API Keys ─────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    NEMOTRON_API_KEY: str = ""
    NEMOTRON_API_URL: str = "https://integrate.api.nvidia.com/v1"
    NIA_API_KEY: str = ""
    NIA_MCP_URL: str = "http://localhost:3001"
    GITHUB_TOKEN: str = ""
    GITHUB_REPO: str = ""

    # ── Databricks / MLflow ──────────────────────────────────────────────
    DATABRICKS_HOST: str = ""
    DATABRICKS_TOKEN: str = ""
    MLFLOW_TRACKING_URI: str = "sqlite:///mlruns.db"

    # ── Budgets ──────────────────────────────────────────────────────────
    BUDGET_LIMIT_PER_TASK: float = 2.0

    # ── Server ───────────────────────────────────────────────────────────
    WS_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:3000"

    # ── Feature flags (graceful degradation) ─────────────────────────────
    USE_NEMOTRON: bool = False
    """False = use regex template fallback (mock_nemotron.py).
    True  = call NVIDIA Nemotron API for real translation."""

    USE_NIA_MCP: bool = False
    """False = skip context layer entirely.
    True  = connect to Nia MCP server for knowledge retrieval."""

    USE_DATABRICKS: bool = False
    """False = use local SQLite MLflow (or MockMLflowClient).
    True  = connect to Databricks-hosted MLflow."""

    USE_GITHUB: bool = False
    """False = use mock GitHub data (mock_github.py).
    True  = connect to GitHub REST API with GITHUB_TOKEN."""





# Singleton settings instance — import this everywhere
settings = Settings()
