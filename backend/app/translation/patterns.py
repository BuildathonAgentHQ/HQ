"""
backend/app/translation/patterns.py — Template-based fallback patterns.

When the Nemotron API is unavailable or slow, these regex/template patterns
provide basic translations for common agent output patterns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class TranslationPattern:
    """A template for pattern-based output translation.

    Attributes:
        name: Human-readable pattern name.
        regex: Compiled regex pattern to match against raw output.
        template: Template string with {group_name} placeholders.
    """
    name: str
    regex: re.Pattern[str]
    template: str


# ── Built-in patterns ───────────────────────────────────────────────────────

PATTERNS: list[TranslationPattern] = [
    # TODO: Add more patterns for common agent output
    TranslationPattern(
        name="file_created",
        regex=re.compile(r"Creat(?:ed|ing)\s+(?:file\s+)?(.+\.(?:py|ts|tsx|js|jsx))"),
        template="Creating file {0}",
    ),
    TranslationPattern(
        name="test_result",
        regex=re.compile(r"(\d+)\s+passed.*?(\d+)\s+failed"),
        template="{0} tests passed, {1} failed",
    ),
    TranslationPattern(
        name="installing_deps",
        regex=re.compile(r"(?:pip install|npm install|yarn add)\s+(.+)"),
        template="Installing dependencies: {0}",
    ),
    TranslationPattern(
        name="git_commit",
        regex=re.compile(r"commit\s+([a-f0-9]{7,40})"),
        template="Created commit {0}",
    ),
]


def match_pattern(raw_output: str) -> str | None:
    """Try to match raw output against known patterns.

    Args:
        raw_output: Raw agent output text.

    Returns:
        A translated string if a pattern matches, None otherwise.

    TODO:
        - Support multi-line pattern matching
        - Add confidence scoring for partial matches
        - Allow runtime registration of new patterns
    """
    for pattern in PATTERNS:
        match = pattern.regex.search(raw_output)
        if match:
            try:
                return pattern.template.format(*match.groups())
            except (IndexError, KeyError):
                return pattern.template
    return None
