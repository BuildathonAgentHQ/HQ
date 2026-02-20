"""
backend/app/translation/translator.py — Raw stdout → plain English.

Provides the ``TranslationLayer`` class that converts raw agent terminal output
into human-readable ``TranslatedEvent`` objects.  Two backends are supported:

1. **NVIDIA Nemotron** (``settings.USE_NEMOTRON = True``):
   Sends raw text to ``nvidia/llama-3.1-nemotron-nano-8b-v1`` and parses the
   structured JSON response.

2. **Template-based fallback** (default):
   Uses the comprehensive regex library in ``patterns.py``.

Nemotron errors are caught gracefully — the system always degrades to
templates and never crashes.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

from backend.app.config import Settings
from backend.app.translation.patterns import template_translate
from shared.schemas import RawStreamEvent, TranslatedEvent

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

_NEMOTRON_MODEL = "nvidia/llama-3.1-nemotron-nano-8b-v1"

_SYSTEM_PROMPT = (
    "You are a translation layer for a coding agent monitoring system. "
    "Convert the following raw terminal output into a single, clear, "
    "plain-English status sentence suitable for a non-technical engineering "
    "manager. Be concise (max 15 words). Also classify: is this an error? "
    "What severity (info/warning/error)? What category "
    "(setup/coding/testing/debugging/deploying/waiting/completed)? "
    'Respond ONLY in this JSON format: '
    '{"status": "...", "is_error": bool, "severity": "...", "category": "..."}'
)


# ── TranslationLayer ────────────────────────────────────────────────────────


class TranslationLayer:
    """Convert ``RawStreamEvent`` objects into ``TranslatedEvent`` objects.

    Parameters
    ----------
    settings:
        Application settings instance.  The fields ``USE_NEMOTRON``,
        ``NEMOTRON_API_URL``, and ``NEMOTRON_API_KEY`` control which
        backend is used.
    """

    def __init__(self, settings: Settings) -> None:
        self._use_nemotron: bool = settings.USE_NEMOTRON
        self._client: Optional[httpx.AsyncClient] = None

        if self._use_nemotron:
            self._api_url: str = settings.NEMOTRON_API_URL.rstrip("/") + "/chat/completions"
            self._client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {settings.NEMOTRON_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(10.0, connect=5.0),
            )
            logger.info(
                "TranslationLayer: Nemotron enabled → %s (model %s)",
                self._api_url,
                _NEMOTRON_MODEL,
            )
        else:
            self._api_url = ""
            logger.info("TranslationLayer: Using template-based fallback")

    # ── Public API ───────────────────────────────────────────────────────

    async def translate(self, raw_event: RawStreamEvent) -> TranslatedEvent:
        """Translate a single ``RawStreamEvent`` into a ``TranslatedEvent``.

        If Nemotron is enabled the raw content is sent to the LLM.  On any
        failure (network, parsing, unexpected schema) the method silently
        falls back to regex-based template translation so the caller never
        sees an exception.
        """
        if self._use_nemotron and self._client is not None:
            try:
                return await self._translate_via_nemotron(raw_event)
            except Exception:  # noqa: BLE001 — intentionally broad
                logger.warning(
                    "Nemotron translation failed for task %s; falling back to templates",
                    raw_event.task_id,
                    exc_info=True,
                )

        return self._translate_via_templates(raw_event)

    async def close(self) -> None:
        """Shut down the HTTP client gracefully."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ── Private helpers ──────────────────────────────────────────────────

    async def _translate_via_nemotron(self, raw_event: RawStreamEvent) -> TranslatedEvent:
        """Call the Nemotron chat-completions endpoint and parse its JSON."""
        assert self._client is not None  # guarded by caller

        payload: dict[str, Any] = {
            "model": _NEMOTRON_MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": raw_event.raw_content},
            ],
            "temperature": 0.2,
            "max_tokens": 150,
        }

        resp = await self._client.post(self._api_url, json=payload)
        resp.raise_for_status()

        data = resp.json()
        content_str = data["choices"][0]["message"]["content"]

        # Nemotron may wrap JSON in a markdown fence — strip it.
        content_str = content_str.strip()
        if content_str.startswith("```"):
            content_str = content_str.split("\n", 1)[-1]
            content_str = content_str.rsplit("```", 1)[0].strip()

        parsed: dict[str, Any] = json.loads(content_str)

        return TranslatedEvent(
            task_id=raw_event.task_id,
            status=str(parsed.get("status", "Agent is working…")),
            is_error=bool(parsed.get("is_error", False)),
            severity=self._clamp_severity(parsed.get("severity", "info")),
            category=self._clamp_category(parsed.get("category", "coding")),
        )

    @staticmethod
    def _translate_via_templates(raw_event: RawStreamEvent) -> TranslatedEvent:
        """Use the regex pattern library as the translation backend."""
        result = template_translate(raw_event.raw_content)
        return TranslatedEvent(
            task_id=raw_event.task_id,
            **result,
        )

    # ── Value clamping helpers ───────────────────────────────────────────

    @staticmethod
    def _clamp_severity(value: Any) -> str:
        """Ensure *value* is a valid severity literal; default ``"info"``."""
        valid = {"info", "warning", "error"}
        return str(value) if str(value) in valid else "info"

    @staticmethod
    def _clamp_category(value: Any) -> str:
        """Ensure *value* is a valid category literal; default ``"coding"``."""
        valid = {
            "setup", "coding", "testing", "debugging",
            "deploying", "waiting", "completed",
        }
        return str(value) if str(value) in valid else "coding"
