"""
backend/app/claude_client/client.py — Central Claude API client for Agent HQ.

Every module that needs Claude intelligence imports ClaudeClient from here.
Handles retries, token tracking, JSON parsing, and cost estimation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any

import httpx

from backend.app.config import Settings

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  Exceptions
# ═══════════════════════════════════════════════════════════════════════════════


class AuthError(Exception):
    """Raised when the Anthropic API returns 401 (invalid / missing key)."""


class RateLimitError(Exception):
    """Raised after exhausting all rate-limit retries."""


# ═══════════════════════════════════════════════════════════════════════════════
#  ClaudeClient
# ═══════════════════════════════════════════════════════════════════════════════


class ClaudeClient:
    """Reusable async client for the Anthropic Messages API.

    Usage::

        client = ClaudeClient(settings)
        result = await client.complete("You are helpful.", "Explain async IO.")
        print(result["text"])
    """

    # Pricing for Claude Sonnet (per 1M tokens)
    _INPUT_COST_PER_M = 3.0   # $3 / 1M input tokens
    _OUTPUT_COST_PER_M = 15.0  # $15 / 1M output tokens

    # Retry configuration
    _MAX_RATE_LIMIT_RETRIES = 3
    _INITIAL_BACKOFF_SECONDS = 1.0

    def __init__(self, settings: Settings) -> None:
        api_key = settings.ANTHROPIC_API_KEY
        if not api_key:
            logger.warning(
                "ANTHROPIC_API_KEY is not set — ClaudeClient will fail on requests."
            )

        self.model: str = settings.CLAUDE_MODEL
        self._http = httpx.AsyncClient(
            base_url="https://api.anthropic.com",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout=httpx.Timeout(120.0),
        )

        # Cumulative token counters
        self._total_input_tokens: int = 0
        self._total_output_tokens: int = 0

    # ── Core completion ──────────────────────────────────────────────────

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """Send a single-turn message to the Claude API.

        Returns::

            {"text": str, "input_tokens": int, "output_tokens": int}

        Raises:
            AuthError: on 401
            RateLimitError: after exhausting retries on 429
            httpx.HTTPStatusError: on unexpected HTTP errors
        """
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_message}],
        }

        response_data = await self._post_with_retries("/v1/messages", body)

        # Extract text from content blocks
        text = ""
        for block in response_data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")

        usage = response_data.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        # Track cumulative usage
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens

        return {
            "text": text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

    # ── JSON completion ──────────────────────────────────────────────────

    async def complete_with_json(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Like ``complete()`` but forces a JSON-only response.

        Appends a JSON-only instruction to the system prompt, then
        attempts to parse the response.  Falls back to raw-text extraction
        if strict parsing fails.
        """
        json_suffix = (
            "\n\nRespond ONLY with valid JSON. "
            "No markdown, no explanation, just the JSON object."
        )
        augmented_prompt = system_prompt + json_suffix

        result = await self.complete(
            system_prompt=augmented_prompt,
            user_message=user_message,
            max_tokens=max_tokens,
            temperature=0.0,
        )

        raw_text: str = result["text"]
        parsed = self._try_parse_json(raw_text)

        return {
            **parsed,
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
        }

    # ── Code analysis convenience ────────────────────────────────────────

    async def analyze_code(
        self,
        code: str,
        file_path: str,
        instruction: str,
    ) -> dict[str, Any]:
        """Convenience wrapper for code-analysis tasks.

        Returns the parsed JSON response from Claude.
        """
        system_prompt = (
            "You are an expert code reviewer. "
            "Analyze the following code and respond in JSON."
        )
        user_message = (
            f"File: {file_path}\n\n"
            f"```\n{code}\n```\n\n"
            f"Instruction: {instruction}"
        )
        return await self.complete_with_json(
            system_prompt=system_prompt,
            user_message=user_message,
        )

    # ── Usage stats ──────────────────────────────────────────────────────

    def get_usage_stats(self) -> dict[str, Any]:
        """Return cumulative token usage and estimated cost."""
        input_cost = (self._total_input_tokens / 1_000_000) * self._INPUT_COST_PER_M
        output_cost = (self._total_output_tokens / 1_000_000) * self._OUTPUT_COST_PER_M
        return {
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "estimated_cost_usd": round(input_cost + output_cost, 6),
        }

    # ── Private helpers ──────────────────────────────────────────────────

    async def _post_with_retries(
        self, path: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """POST to the Anthropic API with retry logic.

        - 401 → raise ``AuthError`` immediately
        - 429 → exponential backoff (up to ``_MAX_RATE_LIMIT_RETRIES``)
        - 500 → retry once
        - Other errors → raise ``httpx.HTTPStatusError``
        """
        last_exc: Exception | None = None
        retries_on_500 = 1

        for attempt in range(self._MAX_RATE_LIMIT_RETRIES + 1):
            start = time.monotonic()
            try:
                resp = await self._http.post(path, json=body)
                latency = time.monotonic() - start

                if resp.status_code == 200:
                    data = resp.json()
                    usage = data.get("usage", {})
                    logger.info(
                        "Claude request: model=%s input_tokens=%d output_tokens=%d latency=%.2fs",
                        self.model,
                        usage.get("input_tokens", 0),
                        usage.get("output_tokens", 0),
                        latency,
                    )
                    return data

                if resp.status_code == 401:
                    raise AuthError(
                        "Invalid or missing ANTHROPIC_API_KEY. "
                        f"Response: {resp.text}"
                    )

                if resp.status_code == 429:
                    backoff = self._INITIAL_BACKOFF_SECONDS * (2**attempt)
                    logger.warning(
                        "Rate limited (429). Retrying in %.1fs (attempt %d/%d)",
                        backoff,
                        attempt + 1,
                        self._MAX_RATE_LIMIT_RETRIES,
                    )
                    await asyncio.sleep(backoff)
                    continue

                if resp.status_code >= 500 and retries_on_500 > 0:
                    retries_on_500 -= 1
                    logger.warning(
                        "Server error (%d). Retrying once…", resp.status_code
                    )
                    await asyncio.sleep(1.0)
                    continue

                # Unexpected status — raise immediately
                resp.raise_for_status()

            except (AuthError, httpx.HTTPStatusError):
                raise
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.error("Unexpected error calling Claude API: %s", exc)
                break

        if last_exc:
            raise last_exc
        raise RateLimitError(
            f"Rate limit exceeded after {self._MAX_RATE_LIMIT_RETRIES} retries."
        )

    @staticmethod
    def _try_parse_json(text: str) -> dict[str, Any]:
        """Attempt to parse ``text`` as JSON.

        Falls back to extracting the first ``{ ... }`` or ``[ ... ]`` block
        if strict parsing fails.  Returns an error dict as a last resort.
        """
        # 1. Try strict parse
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

        # 2. Try to extract JSON object / array from surrounding text
        for pattern in (
            r"\{[\s\S]*\}",   # JSON object
            r"\[[\s\S]*\]",   # JSON array
        ):
            match = re.search(pattern, text)
            if match:
                try:
                    return json.loads(match.group())
                except (json.JSONDecodeError, TypeError):
                    continue

        # 3. Give up
        return {"error": "parse_failed", "raw": text}
