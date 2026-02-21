"""Tests for the translation layer: pattern matching, ANSI stripping, error detection."""
from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio

from app.config import Settings
from app.translation.patterns import template_translate, strip_ansi
from app.translation.translator import TranslationLayer
from shared.schemas import RawStreamEvent, TranslatedEvent
from datetime import datetime, timezone


class TestStripAnsi:
    def test_strips_color_codes(self):
        assert strip_ansi("\x1b[32mOK\x1b[0m") == "OK"

    def test_passthrough_clean_text(self):
        assert strip_ansi("hello world") == "hello world"

    def test_strips_cursor_codes(self):
        assert "\x1b" not in strip_ansi("\x1b[2Jhello")


class TestTemplateTranslate:
    def test_npm_install(self):
        result = template_translate("npm install express")
        assert isinstance(result, TranslatedEvent)
        assert not result.is_error
        assert result.category == "setup"

    def test_pip_install(self):
        result = template_translate("pip install -r requirements.txt")
        assert isinstance(result, TranslatedEvent)
        assert result.category == "setup"

    def test_traceback_is_error(self):
        result = template_translate("Traceback (most recent call last):\n  File test.py")
        assert result.is_error
        assert result.severity == "error"
        assert result.category == "debugging"

    def test_syntax_error(self):
        result = template_translate("SyntaxError: unexpected token")
        assert result.is_error

    def test_import_error(self):
        result = template_translate("ImportError: No module named pandas")
        assert result.is_error

    def test_test_passed(self):
        result = template_translate("15 passed")
        assert not result.is_error
        assert result.category == "testing"

    def test_test_failed(self):
        result = template_translate("3 failed")
        assert result.is_error
        assert result.category == "testing"

    def test_empty_input(self):
        result = template_translate("")
        assert isinstance(result, TranslatedEvent)
        assert result.status == "Agent is working…"

    def test_ansi_stripped(self):
        result = template_translate("\x1b[32m15 passed\x1b[0m")
        assert "\x1b" not in result.status

    def test_fallback_generic(self):
        result = template_translate("random gibberish 12345")
        assert result.status == "Agent is working…"


class TestTranslationLayer:
    @pytest.fixture
    def settings(self):
        return Settings(USE_NEMOTRON=False)

    @pytest.mark.asyncio
    async def test_translate_returns_translated_event(self, settings):
        tl = TranslationLayer(settings)
        raw = RawStreamEvent(
            task_id="t1", stream_type="stdout",
            raw_content="pip install flask",
            timestamp=datetime.now(timezone.utc),
        )
        result = await tl.translate(raw)
        assert isinstance(result, TranslatedEvent)
        assert result.task_id == "t1"

    @pytest.mark.asyncio
    async def test_translate_preserves_task_id(self, settings):
        tl = TranslationLayer(settings)
        raw = RawStreamEvent(
            task_id="my-task-42", stream_type="stderr",
            raw_content="Traceback (most recent call last):\n  TypeError: bad argument",
            timestamp=datetime.now(timezone.utc),
        )
        result = await tl.translate(raw)
        assert result.task_id == "my-task-42"
        assert result.is_error
