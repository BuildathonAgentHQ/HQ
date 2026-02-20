"""
shared/mocks/mock_nemotron.py — Regex-based translation fallback.

Provides ``mock_translate()`` which converts raw terminal output into a
human-readable ``TranslatedEvent`` using pattern matching.  This serves
two purposes:

1. **Mock layer** — lets teammates develop without Nemotron API access.
2. **Production fallback** — used automatically if the Nemotron API is
   unavailable or returns an error.
"""

from __future__ import annotations

import re
from typing import Literal

from shared.schemas import TranslatedEvent


# ── Pattern table ───────────────────────────────────────────────────────────
# (compiled_regex, status_message, is_error, severity, category)

_PATTERNS: list[
    tuple[
        re.Pattern[str],
        str,
        bool,
        Literal["info", "warning", "error"],
        Literal["setup", "coding", "testing", "debugging", "deploying", "waiting", "completed"],
    ]
] = [
    # — Setup patterns —
    (re.compile(r"npm\s+install|yarn\s+(install|add)", re.IGNORECASE),
     "Agent is installing Node.js dependencies", False, "info", "setup"),
    (re.compile(r"pip\s+install|poetry\s+(install|add)|pipenv\s+install", re.IGNORECASE),
     "Agent is installing Python dependencies", False, "info", "setup"),
    (re.compile(r"(cargo|go\s+get|bundle\s+install)", re.IGNORECASE),
     "Agent is installing project dependencies", False, "info", "setup"),
    (re.compile(r"Cloning\s+into|git\s+clone", re.IGNORECASE),
     "Agent is cloning a repository", False, "info", "setup"),
    (re.compile(r"Initializ(e|ing)|Setting\s+up", re.IGNORECASE),
     "Agent is initialising the environment", False, "info", "setup"),

    # — Error / debugging patterns —
    (re.compile(r"Traceback\s+\(most\s+recent", re.IGNORECASE),
     "Agent encountered a Python exception and is investigating", True, "error", "debugging"),
    (re.compile(r"Error:|ERROR:|error\[", re.IGNORECASE),
     "Agent encountered an error and is investigating", True, "error", "debugging"),
    (re.compile(r"Warning:|WARN:|⚠", re.IGNORECASE),
     "Agent received a warning — reviewing impact", False, "warning", "debugging"),
    (re.compile(r"FAIL(ED)?|AssertionError|assert\s+.*failed", re.IGNORECASE),
     "A test assertion failed — agent is debugging", True, "warning", "debugging"),
    (re.compile(r"ModuleNotFoundError|ImportError", re.IGNORECASE),
     "Agent hit a missing-module error and is resolving it", True, "error", "debugging"),

    # — Testing patterns —
    (re.compile(r"PASSED|tests?\s+passed|OK\s*$|✓\s+\d+\s+pass", re.IGNORECASE),
     "All tests passing", False, "info", "testing"),
    (re.compile(r"pytest|jest|mocha|vitest|cargo\s+test|go\s+test", re.IGNORECASE),
     "Agent is running the test suite", False, "info", "testing"),
    (re.compile(r"coverage|--cov", re.IGNORECASE),
     "Agent is generating a test coverage report", False, "info", "testing"),

    # — Coding patterns —
    (re.compile(r"\bdef\s+\w+|class\s+\w+|function\s+\w+|const\s+\w+\s*=", re.IGNORECASE),
     "Agent is writing code", False, "info", "coding"),
    (re.compile(r"Creating\s+file|Writing\s+to|Saving", re.IGNORECASE),
     "Agent is creating a new file", False, "info", "coding"),
    (re.compile(r"Refactor(ing)?|Extract(ing)?|Mov(e|ing)", re.IGNORECASE),
     "Agent is refactoring code", False, "info", "coding"),

    # — Deploying patterns —
    (re.compile(r"docker\s+build|docker\s+push|Deploying|deploy", re.IGNORECASE),
     "Agent is deploying the application", False, "info", "deploying"),
    (re.compile(r"kubectl|helm|terraform", re.IGNORECASE),
     "Agent is running infrastructure commands", False, "info", "deploying"),

    # — Completion patterns —
    (re.compile(r"Done|Complete(d)?|Finish(ed)?|Success(ful)?", re.IGNORECASE),
     "Task completed successfully", False, "info", "completed"),
]


def mock_translate(
    raw_output: str,
    task_id: str = "unknown",
) -> TranslatedEvent:
    """Translate raw subprocess output into a human-readable TranslatedEvent.

    Scans ``raw_output`` against a table of compiled regexes and returns the
    first matching translation.  Falls back to a generic "Agent is working…"
    event if nothing matches.

    Args:
        raw_output: The raw stdout/stderr text from the agent subprocess.
        task_id: UUID of the associated task (passed through to the event).

    Returns:
        A ``TranslatedEvent`` with appropriate status, severity, and category.
    """
    for pattern, status, is_error, severity, category in _PATTERNS:
        if pattern.search(raw_output):
            return TranslatedEvent(
                task_id=task_id,
                status=status,
                is_error=is_error,
                severity=severity,
                category=category,
            )

    # Default fallback
    return TranslatedEvent(
        task_id=task_id,
        status="Agent is working…",
        is_error=False,
        severity="info",
        category="coding",
    )
