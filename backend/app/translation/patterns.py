"""
backend/app/translation/patterns.py — Template-based fallback patterns.

When the Nemotron API is unavailable or slow, these regex/template patterns
provide reliable translations for common agent output patterns.  This library
IS the production fallback — it must be comprehensive enough for the demo to
work without any LLM calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from shared.schemas import TranslatedEvent


# ── ANSI escape code stripper ────────────────────────────────────────────────

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x1b\].*?\x07")


def strip_ansi(text: str) -> str:
    """Remove ANSI color / cursor escape sequences from *text*."""
    return _ANSI_RE.sub("", text)


# ── Pattern dataclass ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PatternEntry:
    """One row of the pattern map.

    Attributes:
        name:      Human-readable pattern ID.
        regex:     Compiled pattern to ``search`` against stripped output.
        status:    Template using ``{0}``, ``{1}`` … for captured groups.
        is_error:  Whether this pattern signals an error condition.
        severity:  Severity level for UI colouring/filtering.
        category:  High-level activity bucket for timeline grouping.
    """

    name: str
    regex: re.Pattern[str]
    status: str
    is_error: bool = False
    severity: Literal["info", "warning", "error"] = "info"
    category: Literal[
        "setup", "coding", "testing", "debugging", "deploying", "waiting", "completed"
    ] = "coding"


# ── Comprehensive pattern map (30+ patterns) ─────────────────────────────────
#
# Order matters — the first match wins.  More specific patterns should appear
# before broader catch-alls.

PATTERN_MAP: list[PatternEntry] = [
    # ── Package installation ─────────────────────────────────────────────
    PatternEntry(
        name="pip_install",
        regex=re.compile(r"pip install\s+(.+)", re.IGNORECASE),
        status="Installing Python packages: {0}",
        category="setup",
    ),
    PatternEntry(
        name="pip_success",
        regex=re.compile(
            r"Successfully installed\s+(.+)", re.IGNORECASE
        ),
        status="Successfully installed {0}",
        category="setup",
    ),
    PatternEntry(
        name="npm_install",
        regex=re.compile(r"npm install\s*(.*)", re.IGNORECASE),
        status="Installing npm packages{0}",
        category="setup",
    ),
    PatternEntry(
        name="npm_added",
        regex=re.compile(r"added (\d+) packages?", re.IGNORECASE),
        status="Added {0} npm packages",
        category="setup",
    ),
    PatternEntry(
        name="yarn_add",
        regex=re.compile(r"yarn add\s+(.+)", re.IGNORECASE),
        status="Adding packages via Yarn: {0}",
        category="setup",
    ),
    PatternEntry(
        name="cargo_install",
        regex=re.compile(r"cargo install\s+(.+)", re.IGNORECASE),
        status="Installing Rust crate: {0}",
        category="setup",
    ),
    # ── Git operations ───────────────────────────────────────────────────
    PatternEntry(
        name="git_clone",
        regex=re.compile(r"git clone\s+(\S+)", re.IGNORECASE),
        status="Cloning repository {0}",
        category="setup",
    ),
    PatternEntry(
        name="git_pull",
        regex=re.compile(r"git pull", re.IGNORECASE),
        status="Pulling latest changes from remote",
        category="setup",
    ),
    PatternEntry(
        name="git_push",
        regex=re.compile(r"git push", re.IGNORECASE),
        status="Pushing changes to remote",
        category="deploying",
    ),
    PatternEntry(
        name="git_commit",
        regex=re.compile(r"commit\s+([a-f0-9]{7,40})", re.IGNORECASE),
        status="Created commit {0}",
        category="coding",
    ),
    PatternEntry(
        name="git_checkout",
        regex=re.compile(r"git checkout\s+(.+)", re.IGNORECASE),
        status="Switching to branch {0}",
        category="coding",
    ),
    # ── Test execution ───────────────────────────────────────────────────
    PatternEntry(
        name="pytest_failed",
        regex=re.compile(r"(\d+)\s+failed"),
        status="{0} tests failed",
        is_error=True,
        severity="error",
        category="testing",
    ),
    PatternEntry(
        name="pytest_passed",
        regex=re.compile(r"(\d+)\s+passed"),
        status="{0} tests passed",
        category="testing",
    ),
    PatternEntry(
        name="pytest_collecting",
        regex=re.compile(r"collecting\s+\.\.\.", re.IGNORECASE),
        status="Collecting test cases",
        category="testing",
    ),
    PatternEntry(
        name="jest_pass",
        regex=re.compile(r"Tests?:\s+(\d+)\s+passed", re.IGNORECASE),
        status="{0} Jest tests passed",
        category="testing",
    ),
    PatternEntry(
        name="jest_fail",
        regex=re.compile(r"Tests?:\s+(\d+)\s+failed", re.IGNORECASE),
        status="{0} Jest tests failed",
        is_error=True,
        severity="error",
        category="testing",
    ),
    PatternEntry(
        name="mocha_passing",
        regex=re.compile(r"(\d+)\s+passing", re.IGNORECASE),
        status="{0} Mocha tests passing",
        category="testing",
    ),
    # ── Compilation / build ──────────────────────────────────────────────
    PatternEntry(
        name="webpack_compiled",
        regex=re.compile(r"compiled\s+successfully", re.IGNORECASE),
        status="Build compiled successfully",
        category="coding",
    ),
    PatternEntry(
        name="webpack_error",
        regex=re.compile(r"ERROR\s+in\s+(.+)", re.IGNORECASE),
        status="Build error in {0}",
        is_error=True,
        severity="error",
        category="debugging",
    ),
    PatternEntry(
        name="tsc_error",
        regex=re.compile(r"error TS(\d+):\s*(.+)"),
        status="TypeScript error TS{0}: {1}",
        is_error=True,
        severity="error",
        category="debugging",
    ),
    PatternEntry(
        name="gcc_error",
        regex=re.compile(r"error:\s+(.+)"),
        status="Compilation error: {0}",
        is_error=True,
        severity="error",
        category="debugging",
    ),
    PatternEntry(
        name="build_success",
        regex=re.compile(r"build\s+(?:succeeded|successful|complete)", re.IGNORECASE),
        status="Build completed successfully",
        category="coding",
    ),
    # ── Server startup ───────────────────────────────────────────────────
    PatternEntry(
        name="uvicorn_start",
        regex=re.compile(r"Uvicorn running on\s+(\S+)", re.IGNORECASE),
        status="Server running on {0}",
        category="deploying",
    ),
    PatternEntry(
        name="next_dev",
        regex=re.compile(r"ready\s.*?(?:on|started)\s+(?:server\s+)?(?:at\s+)?(\S*localhost\S*)", re.IGNORECASE),
        status="Dev server ready at {0}",
        category="deploying",
    ),
    PatternEntry(
        name="flask_run",
        regex=re.compile(r"Running on\s+(\S+)", re.IGNORECASE),
        status="Flask server running on {0}",
        category="deploying",
    ),
    # ── Python error patterns ────────────────────────────────────────────
    PatternEntry(
        name="traceback",
        regex=re.compile(r"Traceback \(most recent call last\)"),
        status="Python traceback encountered",
        is_error=True,
        severity="error",
        category="debugging",
    ),
    PatternEntry(
        name="syntax_error",
        regex=re.compile(r"SyntaxError:\s*(.+)"),
        status="Syntax error: {0}",
        is_error=True,
        severity="error",
        category="debugging",
    ),
    PatternEntry(
        name="type_error",
        regex=re.compile(r"TypeError:\s*(.+)"),
        status="Type error: {0}",
        is_error=True,
        severity="error",
        category="debugging",
    ),
    PatternEntry(
        name="import_error",
        regex=re.compile(r"(?:ImportError|ModuleNotFoundError):\s*(.+)"),
        status="Import error: {0}",
        is_error=True,
        severity="error",
        category="debugging",
    ),
    PatternEntry(
        name="connection_error",
        regex=re.compile(r"ConnectionError:\s*(.+)"),
        status="Connection error: {0}",
        is_error=True,
        severity="error",
        category="debugging",
    ),
    PatternEntry(
        name="timeout_error",
        regex=re.compile(r"TimeoutError:\s*(.+)"),
        status="Timeout error: {0}",
        is_error=True,
        severity="error",
        category="debugging",
    ),
    PatternEntry(
        name="generic_exception",
        regex=re.compile(r"(\w+Error):\s*(.+)"),
        status="{0}: {1}",
        is_error=True,
        severity="error",
        category="debugging",
    ),
    # ── Linting ──────────────────────────────────────────────────────────
    PatternEntry(
        name="ruff_check",
        regex=re.compile(r"ruff\s+check", re.IGNORECASE),
        status="Running Ruff linter",
        category="coding",
    ),
    PatternEntry(
        name="eslint_run",
        regex=re.compile(r"eslint", re.IGNORECASE),
        status="Running ESLint",
        category="coding",
    ),
    PatternEntry(
        name="prettier_run",
        regex=re.compile(r"prettier", re.IGNORECASE),
        status="Running Prettier formatter",
        category="coding",
    ),
    PatternEntry(
        name="lint_warnings",
        regex=re.compile(r"(\d+)\s+warnings?", re.IGNORECASE),
        status="{0} lint warnings found",
        severity="warning",
        category="coding",
    ),
    # ── File operations ──────────────────────────────────────────────────
    PatternEntry(
        name="file_created",
        regex=re.compile(r"Creat(?:ed|ing)\s+(?:file\s+)?(.+\.\w+)"),
        status="Creating file {0}",
        category="coding",
    ),
    PatternEntry(
        name="file_modified",
        regex=re.compile(r"(?:Modif(?:ied|ying)|Updat(?:ed|ing))\s+(?:file\s+)?(.+\.\w+)"),
        status="Modifying file {0}",
        category="coding",
    ),
    PatternEntry(
        name="file_deleted",
        regex=re.compile(r"(?:Delet(?:ed|ing)|Remov(?:ed|ing))\s+(?:file\s+)?(.+\.\w+)"),
        status="Deleting file {0}",
        severity="warning",
        category="coding",
    ),
    # ── Docker operations ────────────────────────────────────────────────
    PatternEntry(
        name="docker_build",
        regex=re.compile(r"docker build", re.IGNORECASE),
        status="Building Docker image",
        category="deploying",
    ),
    PatternEntry(
        name="docker_pull",
        regex=re.compile(r"docker pull\s+(\S+)", re.IGNORECASE),
        status="Pulling Docker image {0}",
        category="setup",
    ),
    PatternEntry(
        name="docker_run",
        regex=re.compile(r"docker (?:run|compose up)", re.IGNORECASE),
        status="Starting Docker container",
        category="deploying",
    ),
    # ── Database migrations ──────────────────────────────────────────────
    PatternEntry(
        name="alembic_upgrade",
        regex=re.compile(r"alembic\s+upgrade", re.IGNORECASE),
        status="Running Alembic database migration",
        category="setup",
    ),
    PatternEntry(
        name="prisma_migrate",
        regex=re.compile(r"prisma\s+(?:migrate|db push)", re.IGNORECASE),
        status="Running Prisma database migration",
        category="setup",
    ),
    PatternEntry(
        name="django_migrate",
        regex=re.compile(r"python\s+manage\.py\s+migrate", re.IGNORECASE),
        status="Running Django database migration",
        category="setup",
    ),
    # ── Progress indicators ──────────────────────────────────────────────
    PatternEntry(
        name="progress_pct",
        regex=re.compile(r"(\d{1,3})%"),
        status="Progress: {0}%",
        category="coding",
    ),
    PatternEntry(
        name="downloading",
        regex=re.compile(r"[Dd]ownloading\s+(\S+)"),
        status="Downloading {0}",
        category="setup",
    ),
]


# ── Public API ───────────────────────────────────────────────────────────────


def template_translate(raw_content: str, task_id: str = "unknown") -> TranslatedEvent:
    """Translate *raw_content* via regex pattern matching.

    Returns a ``TranslatedEvent`` with appropriate status, severity, and
    category.  Falls back to a generic "Agent is working…" if no pattern
    matches.
    """
    cleaned = strip_ansi(raw_content).strip()

    for entry in PATTERN_MAP:
        match = entry.regex.search(cleaned)
        if match:
            try:
                status_text = entry.status.format(*match.groups())
            except (IndexError, KeyError):
                status_text = entry.status

            words = status_text.split()
            if len(words) > 15:
                status_text = " ".join(words[:15]) + "…"

            return TranslatedEvent(
                task_id=task_id,
                status=status_text,
                is_error=entry.is_error,
                severity=entry.severity,
                category=entry.category,
            )

    return TranslatedEvent(
        task_id=task_id,
        status="Agent is working…",
        is_error=False,
        severity="info",
        category="coding",
    )
