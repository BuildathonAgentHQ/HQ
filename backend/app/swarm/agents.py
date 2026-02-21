"""
backend/app/swarm/agents.py — Specialist agent classes for the swarm.

Each agent wraps the ``ClaudeClient`` with a domain-specific system prompt
and file-fetching logic.  All agents:
    • Handle API errors gracefully (single retry, then partial results).
    • Track token usage and include it in the return value.
    • Keep context within Claude's 200K window (truncate / summarize if needed).
    • Ensure generated code matches the repo's conventions.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from backend.app.claude_client.client import ClaudeClient
from backend.app.claude_client.prompts import (
    DOC_WRITER_PROMPT,
    FIX_GENERATOR_PROMPT,
    PR_REVIEWER_PROMPT,
    REFACTOR_PROMPT,
    SECURITY_AUDITOR_PROMPT,
    TEST_WRITER_PROMPT,
)
from backend.app.repo_manager.manager import RepoManager
from shared.schemas import CodeIssue, FixProposal

logger = logging.getLogger(__name__)

# Context limits
_MAX_LINES = 500
_MAX_FILES_PER_CALL = 15


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _truncate(content: str, max_lines: int = _MAX_LINES) -> str:
    """Truncate file content with a marker."""
    lines = content.splitlines(keepends=True)
    if len(lines) <= max_lines:
        return content
    return "".join(lines[:max_lines]) + f"\n... (truncated — {len(lines)} total lines)\n"


def _format_files(files: dict[str, str]) -> str:
    """Format {path: content} into a prompt-friendly string."""
    parts: list[str] = []
    for path, content in files.items():
        parts.append(f"### {path}\n```\n{_truncate(content)}\n```")
    return "\n\n".join(parts)


def _normalise(raw: str, valid: set[str], fallback: str) -> str:
    """Normalise a free-form string to a valid enum value."""
    normalised = raw.lower().replace(" ", "_").replace("-", "_")
    return normalised if normalised in valid else fallback


_VALID_ISSUE_TYPES = {
    "bug", "security", "performance", "error_handling",
    "testing", "style", "breaking", "refactor",
}
_VALID_SEVERITIES = {"critical", "high", "medium", "low"}


def _detect_test_framework(files: dict[str, str]) -> str:
    """Heuristic: detect the project's test framework from file extensions."""
    for path in files:
        lower = path.lower()
        if lower.endswith(".py"):
            return "pytest"
        if lower.endswith((".ts", ".tsx")):
            return "jest"
        if lower.endswith((".js", ".jsx")):
            # Check for jest or mocha indicators in content
            content = files[path]
            if "describe(" in content or "it(" in content:
                return "jest"
            return "jest"
    return "pytest"


def _derive_test_path(file_path: str) -> str:
    """Derive a test file path from a source file path."""
    parts = file_path.rsplit("/", 1)
    directory = parts[0] if len(parts) == 2 else ""
    filename = parts[-1]
    name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "py")

    if ext == "py":
        test_name = f"test_{name}.{ext}"
    else:
        test_name = f"{name}.test.{ext}"

    if directory:
        parent = directory.rsplit("/", 1)[0] if "/" in directory else directory
        return f"{parent}/tests/{test_name}"
    return f"tests/{test_name}"


# ═══════════════════════════════════════════════════════════════════════════════
#  Base Agent
# ═══════════════════════════════════════════════════════════════════════════════


class BaseAgent:
    """Shared foundation for all specialist agents.

    Provides file fetching, context-aware truncation, error handling,
    and token tracking.
    """

    def __init__(self, claude: ClaudeClient, repo_manager: RepoManager) -> None:
        self.claude = claude
        self.repo_manager = repo_manager

    async def _fetch_files(
        self, repo_id: str, paths: list[str]
    ) -> dict[str, str]:
        """Fetch multiple files in parallel, returning {path: content}."""
        async def _get(p: str) -> tuple[str, str]:
            try:
                content = await self.repo_manager.get_file_content(repo_id, p)
                return p, content
            except Exception:
                return p, "<file not found>"

        entries = await asyncio.gather(*[_get(p) for p in paths[:_MAX_FILES_PER_CALL]])
        return dict(entries)

    async def _call_claude(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Call Claude with a single retry on failure.

        Returns the parsed JSON dict.  On total failure, returns
        ``{"error": "<message>", "partial": True}``.
        """
        for attempt in range(2):
            try:
                result = await self.claude.complete_with_json(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    max_tokens=max_tokens,
                )
                return result
            except Exception as exc:
                if attempt == 0:
                    logger.warning(
                        "Claude call failed (attempt 1), retrying: %s", exc
                    )
                    await asyncio.sleep(1)
                else:
                    logger.error("Claude call failed after retry: %s", exc)
                    return {"error": str(exc), "partial": True}

        return {"error": "unexpected", "partial": True}

    def _get_token_usage(self) -> dict[str, Any]:
        """Return cumulative token usage from the ClaudeClient."""
        return self.claude.get_usage_stats()


# ═══════════════════════════════════════════════════════════════════════════════
#  Reviewer Agent
# ═══════════════════════════════════════════════════════════════════════════════


class ReviewerAgent(BaseAgent):
    """Reviews files for bugs, security issues, and code quality problems."""

    async def review(
        self,
        repo_id: str,
        target_files: list[str],
        task_description: str,
    ) -> dict[str, Any]:
        """Review target files and return issues found.

        Returns:
            Dict with ``issues`` list and ``token_usage``.
        """
        files = await self._fetch_files(repo_id, target_files)
        files_text = _format_files(files)

        user_message = (
            f"Review these files. Focus on: {task_description}\n\n"
            f"{files_text}"
        )

        result = await self._call_claude(PR_REVIEWER_PROMPT, user_message)

        # Build CodeIssue objects
        issues: list[CodeIssue] = []
        for raw in result.get("issues", []):
            issue = CodeIssue(
                repo_id=repo_id,
                file_path=raw.get("file", ""),
                line_number=raw.get("line"),
                issue_type=_normalise(
                    raw.get("type", "refactor"), _VALID_ISSUE_TYPES, "refactor"
                ),
                severity=_normalise(
                    raw.get("severity", "medium"), _VALID_SEVERITIES, "medium"
                ),
                description=raw.get("description", ""),
                suggestion=raw.get("suggestion", ""),
            )
            issues.append(issue)

        return {
            "issues": [i.model_dump(mode="json") for i in issues],
            "issues_objects": issues,
            "summary": result.get("summary", ""),
            "verdict": result.get("verdict", "needs_discussion"),
            "token_usage": self._get_token_usage(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  Fix Generator Agent
# ═══════════════════════════════════════════════════════════════════════════════


class FixGeneratorAgent(BaseAgent):
    """Generates concrete code fixes for discovered issues.

    CRITICAL: Instructs Claude to copy the original_code segment EXACTLY
    from the source file.  A paraphrased or reformatted original segment
    prevents automated application.
    """

    async def generate_fix(
        self, repo_id: str, issue: CodeIssue
    ) -> FixProposal:
        """Generate a fix for a specific CodeIssue.

        Also fetches related files (imports, tests) to give Claude
        enough context for a semantically correct fix.

        Returns:
            A ``FixProposal`` object ready for approval.
        """
        # Fetch the issue file
        primary = await self._fetch_files(repo_id, [issue.file_path])

        # Attempt to fetch related files (imports from the issue file)
        related_paths = RepoManager._extract_imports(
            primary.get(issue.file_path, ""), issue.file_path
        )
        related = await self._fetch_files(
            repo_id, related_paths[:5]  # limit to 5 related files
        )

        all_files = {**primary, **related}
        files_text = _format_files(all_files)

        # Build a prompt that emphasizes exact code matching
        user_message = (
            f"## Issue\n"
            f"**File:** {issue.file_path}\n"
            f"**Line:** {issue.line_number or 'N/A'}\n"
            f"**Type:** {issue.issue_type} ({issue.severity})\n"
            f"**Description:** {issue.description}\n"
            f"**Suggestion:** {issue.suggestion}\n\n"
            f"## Source Files\n{files_text}\n\n"
            f"CRITICAL: In your response, the 'original_code' field MUST be "
            f"an EXACT copy-paste of the code segment from the file above. "
            f"Do NOT paraphrase, reformat, or summarize the original code. "
            f"Copy it character-for-character so it can be matched for "
            f"automated replacement."
        )

        result = await self._call_claude(FIX_GENERATOR_PROMPT, user_message)

        proposal = FixProposal(
            issue_id=issue.id,
            repo_id=repo_id,
            agent_type="fix_generator",
            file_path=result.get("file_path", issue.file_path),
            original_code=result.get("original_code", ""),
            fixed_code=result.get("fixed_code", ""),
            explanation=result.get("explanation", ""),
            test_code=(
                result.get("test_code")
                if result.get("test_needed")
                else None
            ),
        )

        logger.info(
            "Fix generated for %s: %s",
            issue.file_path,
            proposal.explanation[:80],
        )
        return proposal


# ═══════════════════════════════════════════════════════════════════════════════
#  Test Writer Agent
# ═══════════════════════════════════════════════════════════════════════════════


class TestWriterAgent(BaseAgent):
    """Generates comprehensive test suites for source files."""

    async def write_tests(
        self,
        repo_id: str,
        target_files: list[str],
        task_description: str,
    ) -> dict[str, Any]:
        """Write tests for the given source files.

        Auto-detects the test framework (pytest for Python, jest for
        JS/TS) and generates a complete test file.

        Returns:
            Dict with ``test_file_path``, ``test_code``, ``fix_proposal``,
            and ``token_usage``.
        """
        files = await self._fetch_files(repo_id, target_files)
        files_text = _format_files(files)
        framework = _detect_test_framework(files)

        user_message = (
            f"Test framework: {framework}\n"
            f"Focus: {task_description}\n\n"
            f"Write comprehensive tests for:\n{files_text}\n\n"
            f"Ensure tests follow the project's existing conventions "
            f"(import style, naming, file structure)."
        )

        result = await self._call_claude(TEST_WRITER_PROMPT, user_message)

        test_path = result.get(
            "test_file_path",
            _derive_test_path(target_files[0]) if target_files else "tests/test_new.py",
        )
        test_code = result.get("test_code", "")

        # Create a FixProposal representing the new test file
        proposal = FixProposal(
            issue_id="test_coverage",
            repo_id=repo_id,
            agent_type="test_writer",
            file_path=test_path,
            original_code="",  # new file
            fixed_code=test_code,
            explanation=f"New test file for {', '.join(target_files)}",
        )

        return {
            "test_file_path": test_path,
            "test_code": test_code,
            "test_framework": framework,
            "tests_written": result.get("tests_written", []),
            "coverage_estimate": result.get("coverage_estimate", ""),
            "fix_proposal": proposal,
            "token_usage": self._get_token_usage(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  Refactor Agent
# ═══════════════════════════════════════════════════════════════════════════════


class RefactorAgent(BaseAgent):
    """Refactors code based on a goal description."""

    async def refactor(
        self,
        repo_id: str,
        target_files: list[str],
        task_description: str,
    ) -> list[FixProposal]:
        """Refactor target files according to the given goal.

        Returns:
            List of ``FixProposal`` objects, one per file changed.
        """
        files = await self._fetch_files(repo_id, target_files)
        files_text = _format_files(files)

        user_message = (
            f"Refactoring goal: {task_description}\n\n"
            f"Files:\n{files_text}\n\n"
            f"IMPORTANT: In each change, the 'original_code' must be an "
            f"exact copy from the source file above."
        )

        result = await self._call_claude(REFACTOR_PROMPT, user_message)

        proposals: list[FixProposal] = []
        for change in result.get("changes", []):
            fp = FixProposal(
                issue_id="refactor",
                repo_id=repo_id,
                agent_type="refactor",
                file_path=change.get("file_path", ""),
                original_code=change.get("original_code", ""),
                fixed_code=change.get("refactored_code", ""),
                explanation=change.get("reason", ""),
            )
            proposals.append(fp)

        logger.info(
            "Refactor produced %d change(s) for: %s",
            len(proposals),
            task_description[:60],
        )
        return proposals


# ═══════════════════════════════════════════════════════════════════════════════
#  Security Agent
# ═══════════════════════════════════════════════════════════════════════════════


class SecurityAgent(BaseAgent):
    """Audits code for security vulnerabilities."""

    async def audit(
        self,
        repo_id: str,
        target_files: list[str],
    ) -> dict[str, Any]:
        """Run a security audit on target files.

        Returns:
            Dict with ``vulnerabilities`` (``CodeIssue`` objects),
            ``overall_risk``, ``recommendations``, and ``token_usage``.
        """
        files = await self._fetch_files(repo_id, target_files)
        files_text = _format_files(files)

        result = await self._call_claude(
            SECURITY_AUDITOR_PROMPT,
            f"Audit these files for security vulnerabilities:\n{files_text}",
        )

        issues: list[CodeIssue] = []
        for vuln in result.get("vulnerabilities", []):
            issue = CodeIssue(
                repo_id=repo_id,
                file_path=vuln.get("file", ""),
                line_number=vuln.get("line"),
                issue_type="security",
                severity=_normalise(
                    vuln.get("severity", "medium"), _VALID_SEVERITIES, "medium"
                ),
                description=vuln.get("description", ""),
                suggestion=vuln.get("fix", ""),
            )
            issues.append(issue)

        return {
            "vulnerabilities": [i.model_dump(mode="json") for i in issues],
            "vulnerabilities_objects": issues,
            "overall_risk": result.get("overall_risk", "medium"),
            "recommendations": result.get("recommendations", []),
            "token_usage": self._get_token_usage(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  Documentation Writer Agent
# ═══════════════════════════════════════════════════════════════════════════════


class DocWriterAgent(BaseAgent):
    """Generates technical documentation for source files."""

    async def write_docs(
        self,
        repo_id: str,
        target_files: list[str],
        doc_type: str = "readme",
    ) -> FixProposal:
        """Generate documentation for target files.

        Args:
            repo_id: Repository ID.
            target_files: Files to document.
            doc_type: One of ``readme``, ``api_docs``, ``inline_comments``,
                      ``architecture``.

        Returns:
            ``FixProposal`` containing the generated documentation.
        """
        files = await self._fetch_files(repo_id, target_files)
        files_text = _format_files(files)

        user_message = (
            f"Documentation type requested: {doc_type}\n\n"
            f"Generate documentation for:\n{files_text}\n\n"
            f"Follow the project's existing documentation style and "
            f"conventions.  Use proper headings, code examples, and "
            f"maintain consistency with any existing docs."
        )

        result = await self._call_claude(DOC_WRITER_PROMPT, user_message)

        content = result.get("content", "")
        actual_doc_type = result.get("doc_type", doc_type)

        doc_path = {
            "readme": "README.md",
            "api_docs": "docs/API.md",
            "inline_comments": target_files[0] if target_files else "docs/comments.md",
            "architecture": "docs/ARCHITECTURE.md",
        }.get(actual_doc_type, f"docs/{actual_doc_type}.md")

        proposal = FixProposal(
            issue_id="documentation",
            repo_id=repo_id,
            agent_type="doc_writer",
            file_path=doc_path,
            original_code="",  # new or replacement file
            fixed_code=content,
            explanation=f"Generated {actual_doc_type} documentation",
        )

        logger.info(
            "Documentation generated: %s (%d chars)",
            doc_path,
            len(content),
        )
        return proposal
