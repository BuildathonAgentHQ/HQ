"""
backend/app/telemetry/_shared.py — Shared AgentTelemetry singleton.

Importing ``telemetry`` from this module gives every consumer the
**same** ``AgentTelemetry`` instance so we only open one connection to
Databricks MLflow (or one MockMLflowClient).
"""

from __future__ import annotations

from backend.app.config import settings
from backend.app.telemetry.agent_telemetry import AgentTelemetry

# Single instance — created once on first import
telemetry = AgentTelemetry(settings)
