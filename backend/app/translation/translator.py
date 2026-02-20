"""
backend/app/translation/translator.py — Raw stdout → plain English.

Uses the NVIDIA Nemotron model to translate cryptic agent terminal output
into human-readable summaries that appear in the activity stream.
"""

from __future__ import annotations

from typing import Optional

import httpx

from backend.app.config import settings
from shared.schemas import TranslationChunk


class Translator:
    """Translates raw agent output into plain English via Nemotron.

    Attributes:
        api_key: Nemotron API key.
        api_url: Nemotron API endpoint.
        client: httpx async client.
    """

    def __init__(self) -> None:
        self.api_key: str = settings.NEMOTRON_API_KEY
        self.api_url: str = settings.NEMOTRON_API_URL
        self.client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        """Initialize the HTTP client for Nemotron API calls.

        TODO:
            - Create httpx.AsyncClient with auth headers
            - Validate API key with a test call
        """
        # TODO: Implement client initialization
        pass

    async def translate(self, task_id: str, raw_output: str) -> TranslationChunk:
        """Translate a chunk of raw agent output into plain English.

        Args:
            task_id: The task this output belongs to.
            raw_output: Raw stdout/stderr text from the agent.

        Returns:
            TranslationChunk with both raw and translated text.

        TODO:
            - Build prompt with system instruction for translation
            - Call Nemotron API with the raw output
            - Parse response and extract translated text
            - Fall back to template-based translation if API fails
            - Emit TRANSLATION_CHUNK event via WebSocket
        """
        # TODO: Implement Nemotron API call
        raise NotImplementedError("Translator.translate not yet implemented")

    async def close(self) -> None:
        """Close the HTTP client.

        TODO:
            - Close httpx client gracefully
        """
        if self.client:
            await self.client.aclose()
