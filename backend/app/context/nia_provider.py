"""
backend/app/context/nia_provider.py — Claude-powered context provider.

Replaces the old Nia MCP integration.  Instead of calling external
embedding-based search, Claude directly analyses the repo structure and
key files to produce architectural context for agent prompts.

Backward-compatible: the orchestrator still calls ``get_context()``.

The old ``NiaContextProvider`` name is kept as an alias for imports that
haven't been updated yet.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.app.config import Settings
from shared.mocks.mock_context import mock_get_context
from shared.schemas import ContextPayload

logger = logging.getLogger(__name__)


class ClaudeContextProvider:
    """Provides repository context using Claude instead of Nia MCP.

    Two modes:
        1. **Claude mode** (``USE_CLAUDE_API=True``):
           Fetches repo structure via ``RepoManager``, then asks Claude to
           analyse it for architectural patterns, dependencies, and
           important files relevant to the given task.
        2. **Fallback mode**:
           Returns mock context data.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.use_claude = getattr(settings, "USE_CLAUDE_API", False)

        # Lazy-initialised to avoid circular imports
        self._claude: Any = None
        self._repo_manager: Any = None

    def _ensure_clients(self) -> None:
        """Lazy-load Claude and RepoManager on first use."""
        if self._claude is not None:
            return
        try:
            from backend.app.claude_client.client import ClaudeClient
            from backend.app.control_plane.github_connector import GitHubConnector
            from backend.app.repo_manager.manager import RepoManager

            self._claude = ClaudeClient(self.settings)
            github = GitHubConnector(self.settings)
            self._repo_manager = RepoManager(self.settings, github)
        except Exception as exc:
            logger.warning("Failed to initialise Claude context clients: %s", exc)
            self.use_claude = False

    # ── Public API (backward-compatible) ─────────────────────────────────

    async def get_context(
        self, task: str, repo_path: str = "."
    ) -> ContextPayload:
        """Fetch architectural context for an agent task.

        Args:
            task: Plain-English description of what the agent will do.
            repo_path: Path or identifier for the repository.

        Returns:
            ``ContextPayload`` with architectural context, dependencies,
            relevant skills, and business requirements.
        """
        try:
            if self.use_claude:
                return await self._get_claude_context(task, repo_path)
            else:
                return self._get_fallback_context(task, repo_path)
        except Exception as exc:
            logger.error("Uncaught exception in get_context: %s", exc)
            return ContextPayload(
                architectural_context=(
                    "Context extraction failed. Proceed without "
                    "architectural guidance."
                ),
                dependencies=[],
                relevant_skills=[],
                business_requirements=[],
            )

    async def refresh_index(self, repo_path: str = ".") -> None:
        """No-op for Claude provider (no external index to refresh)."""
        logger.debug("refresh_index called — no action needed for Claude provider")

    # ── Claude context ───────────────────────────────────────────────────

    async def _get_claude_context(
        self, task: str, repo_path: str
    ) -> ContextPayload:
        """Ask Claude to analyse the repo structure for the given task."""
        self._ensure_clients()

        if self._claude is None or self._repo_manager is None:
            return self._get_fallback_context(task, repo_path)

        # Try to find a repo by path or use the first connected repo
        repo_id = await self._resolve_repo_id(repo_path)

        if repo_id is None:
            logger.info("No connected repo found; falling back to mock context")
            return self._get_fallback_context(task, repo_path)

        # Get repo structure
        try:
            structure = await self._repo_manager.get_repo_structure(repo_id)
        except Exception as exc:
            logger.warning("Failed to get repo structure: %s", exc)
            return self._get_fallback_context(task, repo_path)

        # Format file tree for prompt
        file_paths = [
            f["path"] for f in structure.get("files", [])[:150]
        ]
        languages = structure.get("languages", {})
        lang_summary = ", ".join(
            f"{ext}: {count}"
            for ext, count in sorted(languages.items(), key=lambda x: -x[1])[:10]
        )

        user_message = (
            f"# Task\n{task}\n\n"
            f"# Repository Structure\n"
            f"Languages: {lang_summary}\n"
            f"Total files: {structure.get('total_files', 0)}\n\n"
            f"File tree:\n```\n" + "\n".join(file_paths) + "\n```"
        )

        system_prompt = (
            "Given this repository structure, what are the key architectural "
            "patterns, main dependencies, and important files for someone "
            f"about to modify the codebase for: {task}?\n\n"
            "Respond in JSON:\n"
            "{\n"
            '  "architectural_context": "multi-line description of architecture, '
            'patterns, and conventions",\n'
            '  "dependencies": ["list", "of", "key", "dependencies"],\n'
            '  "relevant_files": ["list", "of", "files", "to", "focus", "on"],\n'
            '  "business_requirements": ["list", "of", "constraints"]\n'
            "}"
        )

        try:
            result = await self._claude.complete_with_json(
                system_prompt=system_prompt,
                user_message=user_message,
                max_tokens=2048,
            )
        except Exception as exc:
            logger.warning("Claude context analysis failed: %s", exc)
            return self._get_fallback_context(task, repo_path)

        if isinstance(result, dict) and "error" not in result:
            return ContextPayload(
                architectural_context=result.get(
                    "architectural_context",
                    "No architectural context available.",
                ),
                dependencies=result.get("dependencies", []),
                relevant_skills=[],
                business_requirements=result.get("business_requirements", []),
            )

        return self._get_fallback_context(task, repo_path)

    # ── Fallback ─────────────────────────────────────────────────────────

    @staticmethod
    def _get_fallback_context(task: str, repo_path: str) -> ContextPayload:
        """Return mock context when Claude is unavailable."""
        return mock_get_context(task, repo_path)

    # ── Repo resolution ──────────────────────────────────────────────────

    async def _resolve_repo_id(self, repo_path: str) -> str | None:
        """Try to match ``repo_path`` to a connected repository ID."""
        if self._repo_manager is None:
            return None

        repos = await self._repo_manager.list_repos()

        # Try matching by full name or path
        for repo in repos:
            if (
                repo.full_name == repo_path
                or repo.name == repo_path
                or repo.url == repo_path
            ):
                return repo.id

        # Fall back to the first repo if only one is connected
        if len(repos) == 1:
            return repos[0].id

        return None


# ── Backward-compatible alias ────────────────────────────────────────────────
NiaContextProvider = ClaudeContextProvider
