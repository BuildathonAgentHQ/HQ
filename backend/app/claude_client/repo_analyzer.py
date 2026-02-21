"""
backend/app/claude_client/repo_analyzer.py — On-demand repo & PR analysis via Claude.

Replaces the old Nia context layer.  Instead of pre-indexed embeddings,
Claude directly analyses repo key files and PR diffs on demand, producing
structured JSON results that map onto our Pydantic models.

Context-window strategy (Claude Sonnet — 200K tokens):
    • Typical PR context: 10-30K tokens → plenty of room.
    • Large PRs (>50 files): batched into groups of 10-15 files.
    • Always include FULL file content for changed files (not just diff).
    • Files truncated at 500 lines; for longer files we include the first
      200 lines + the changed section + 50 lines of surrounding context.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from backend.app.claude_client.client import ClaudeClient
from backend.app.claude_client.prompts import (
    PR_REVIEWER_PROMPT,
    REPO_ANALYZER_PROMPT,
    REPO_INDEXER_PROMPT,
    SECURITY_AUDITOR_PROMPT,
)
from backend.app.repo_manager.manager import RepoManager
from backend.app.websocket.events import event_router
from shared.events import EventType, create_ws_event
from shared.schemas import CodeIssue, PRReview, SwarmPlan, SwarmTask

logger = logging.getLogger(__name__)

# Maximum lines to include per file in prompts
_MAX_LINES_PER_FILE = 500
_HEAD_LINES = 200
_CONTEXT_LINES = 50

# Large-PR batching threshold
_LARGE_PR_FILE_THRESHOLD = 50
_BATCH_SIZE = 12


def _truncate_content(content: str, max_lines: int = _MAX_LINES_PER_FILE) -> str:
    """Truncate file content to *max_lines*, appending a marker if cut."""
    lines = content.splitlines(keepends=True)
    if len(lines) <= max_lines:
        return content
    truncated = "".join(lines[:max_lines])
    return truncated + f"\n... (truncated — {len(lines)} total lines)\n"


def _smart_truncate(
    content: str,
    changed_lines: set[int] | None = None,
) -> str:
    """Truncate a long file while preserving changed regions.

    For files exceeding ``_MAX_LINES_PER_FILE``:
        - Always keep the first ``_HEAD_LINES`` lines (imports, class defs).
        - For each changed line, keep ``_CONTEXT_LINES`` lines around it.
        - If no changed lines are known, fall back to simple truncation.
    """
    lines = content.splitlines(keepends=True)
    if len(lines) <= _MAX_LINES_PER_FILE:
        return content

    if not changed_lines:
        return _truncate_content(content)

    # Build a set of line indices to keep
    keep: set[int] = set(range(min(_HEAD_LINES, len(lines))))
    for cl in changed_lines:
        start = max(0, cl - _CONTEXT_LINES)
        end = min(len(lines), cl + _CONTEXT_LINES)
        keep.update(range(start, end))

    # Reconstruct with gap markers
    sorted_keep = sorted(keep)
    parts: list[str] = []
    prev = -1
    for idx in sorted_keep:
        if idx > prev + 1 and prev >= 0:
            parts.append(f"\n... ({idx - prev - 1} lines omitted) ...\n")
        parts.append(lines[idx])
        prev = idx

    if sorted_keep and sorted_keep[-1] < len(lines) - 1:
        parts.append(
            f"\n... ({len(lines) - sorted_keep[-1] - 1} lines omitted to end) ...\n"
        )

    return "".join(parts)


def _extract_changed_lines(patch: str) -> set[int]:
    """Parse a unified diff patch to find the new-side line numbers."""
    changed: set[int] = set()
    current_line = 0
    for line in patch.splitlines():
        hunk = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if hunk:
            current_line = int(hunk.group(1))
            continue
        if line.startswith("+") and not line.startswith("+++"):
            changed.add(current_line)
            current_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            pass  # deleted lines don't advance the new-side counter
        else:
            current_line += 1
    return changed


class RepoAnalyzer:
    """Analyses repositories and PRs using Claude as the intelligence engine.

    Uses :class:`ClaudeClient` for API calls and :class:`RepoManager` for
    GitHub data retrieval.  All analysis results are emitted as WebSocket
    events and returned as structured Pydantic objects.
    """

    def __init__(self, claude: ClaudeClient, repo_manager: RepoManager) -> None:
        self.claude = claude
        self.repo_manager = repo_manager

        # In-memory stores (future: persist to DB)
        self.issues: dict[str, CodeIssue] = {}        # issue_id → CodeIssue
        self.reviews: dict[str, PRReview] = {}         # review_id → PRReview

    # ── Repository index (local caching map) ─────────────────────────────

    async def index_repository(self, repo_id: str) -> str:
        """Create a semantic Markdown index of the repo by summarizing key files.

        This map is saved locally in the repo's clone directory and is used
        by PR Review agents to quickly grasp the architecture without fetching
        irrelevant files over the network.
        """
        repo = await self.repo_manager.get_repo(repo_id)
        logger.info("Building semantic index for repo: %s", repo.full_name)

        structure = await self.repo_manager.get_repo_structure(repo_id)
        key_files = await self.repo_manager.get_key_files(repo_id, max_files=30)

        file_tree_summary = self._format_file_tree(structure)
        files_section = self._format_key_files(key_files)

        user_message = (
            f"## Repository: {repo.full_name}\n\n"
            f"### File Structure\n```\n{file_tree_summary}\n```\n\n"
            f"### Key Files\n{files_section}"
        )

        try:
            # We don't use complete_with_json here because REPO_INDEXER_PROMPT requests pure Markdown
            result = await self.claude.complete(
                system_prompt=REPO_INDEXER_PROMPT,
                user_message=user_message,
                max_tokens=4096,
            )
            markdown_map = result.get("content", "Failed to generate repo map.")
            
            # Save it locally in the clone path
            repo_dir = os.path.join(self.repo_manager.clone_base_path, repo_id)
            map_path = os.path.join(repo_dir, ".agent_hq_repo_map.md")
            if os.path.exists(repo_dir):
                with open(map_path, "w", encoding="utf-8") as f:
                    f.write(markdown_map)
                logger.info("Saved repo map to %s", map_path)
            
            return markdown_map
        except Exception as e:
            logger.error("Failed to build semantic index for %s: %s", repo_id, e)
            return ""

    # ── Repository analysis ──────────────────────────────────────────────

    async def analyze_repo(self, repo_id: str) -> dict[str, Any]:
        """Run a full Claude analysis on a repository's key files.

        Steps:
            1. Fetch the file tree + up to 20 key files.
            2. Build a prompt with structure + file contents.
            3. Call Claude with ``REPO_ANALYZER_PROMPT``.
            4. Update the ``Repository`` object with results.
            5. Store discovered ``CodeIssue`` objects.
            6. Emit ``repo_analyzed`` WebSocket event.

        Returns:
            The full analysis dict from Claude.
        """
        repo = await self.repo_manager.get_repo(repo_id)
        logger.info("Analyzing repo: %s", repo.full_name)

        # 1. Gather context
        structure = await self.repo_manager.get_repo_structure(repo_id)
        key_files = await self.repo_manager.get_key_files(repo_id, max_files=20)

        # 2. Build prompt
        file_tree_summary = self._format_file_tree(structure)
        files_section = self._format_key_files(key_files)

        user_message = (
            f"## Repository: {repo.full_name}\n\n"
            f"### File Structure\n```\n{file_tree_summary}\n```\n\n"
            f"### Key Files\n{files_section}"
        )

        # 3. Call Claude
        result = await self.claude.complete_with_json(
            system_prompt=REPO_ANALYZER_PROMPT,
            user_message=user_message,
            max_tokens=4096,
        )

        # 4. Update Repository
        if "error" not in result:
            repo.analysis_summary = result.get("architecture", "")
            repo.tech_stack = result.get("tech_stack", [])

            # Derive health score from issues
            quality_issues = result.get("code_quality_issues", [])
            security_concerns = result.get("security_concerns", [])
            total_issues = len(quality_issues) + len(security_concerns)
            repo.health_score = max(0, 100 - (total_issues * 8))
            repo.last_analyzed = datetime.now(timezone.utc)

            # 5. Store issues
            all_raw_issues = [
                {**i, "issue_type": "refactor"} for i in quality_issues
            ] + [
                {**i, "issue_type": "security", "file_path": i.get("file", "")}
                for i in security_concerns
            ]
            for raw in all_raw_issues:
                issue = CodeIssue(
                    repo_id=repo_id,
                    file_path=raw.get("file", raw.get("file_path", "")),
                    issue_type=self._normalise_issue_type(
                        raw.get("issue_type", "refactor")
                    ),
                    severity=self._normalise_severity(
                        raw.get("severity", "medium")
                    ),
                    description=raw.get("issue", raw.get("concern", "")),
                    suggestion=raw.get("fix", raw.get("suggestion", "Review this code.")),
                )
                self.issues[issue.id] = issue

        # 6. Emit event
        event = create_ws_event(
            task_id="system",
            event_type=EventType.REPO_ANALYZED,
            payload={
                "repo_id": repo_id,
                "repo": repo.full_name,
                "health_score": repo.health_score,
                "issues_found": len([
                    i for i in self.issues.values() if i.repo_id == repo_id
                ]),
                "analysis": result,
            },
        )
        await event_router.emit(event)

        logger.info(
            "Repo analysis complete: %s — health=%s, issues=%d",
            repo.full_name,
            repo.health_score,
            len([i for i in self.issues.values() if i.repo_id == repo_id]),
        )
        return result

    # ── PR review ────────────────────────────────────────────────────────

    async def analyze_pr(self, repo_id: str, pr_number: int) -> PRReview:
        """Run a deep Claude-powered review on a pull request.

        Steps:
            1. Fetch full PR context (metadata, diff, full file contents).
            2. Build prompt with ``PR_REVIEWER_PROMPT``.
            3. For large PRs, batch into groups of files.
            4. Parse results into ``PRReview`` + ``CodeIssue`` objects.
            5. Emit ``pr_reviewed`` WebSocket event.

        Returns:
            A fully-populated ``PRReview`` object.
        """
        repo = await self.repo_manager.get_repo(repo_id)
        logger.info("Reviewing PR #%d on %s", pr_number, repo.full_name)

        pr_context = await self.repo_manager.get_pr_full_context(
            repo_id, pr_number
        )

        changed_files = pr_context.get("changed_files", [])

        # Decide: single call or batched
        if len(changed_files) > _LARGE_PR_FILE_THRESHOLD:
            result = await self._batched_pr_review(
                repo, pr_context, changed_files
            )
        else:
            result = await self._single_pr_review(repo, pr_context)

        # Build CodeIssue objects
        issues: list[CodeIssue] = []
        for raw_issue in result.get("issues", []):
            issue = CodeIssue(
                repo_id=repo_id,
                pr_number=pr_number,
                file_path=raw_issue.get("file", ""),
                line_number=raw_issue.get("line"),
                issue_type=self._normalise_issue_type(
                    raw_issue.get("type", "bug")
                ),
                severity=self._normalise_severity(
                    raw_issue.get("severity", "medium")
                ),
                description=raw_issue.get("description", ""),
                suggestion=raw_issue.get("suggestion", ""),
            )
            self.issues[issue.id] = issue
            issues.append(issue)

        # Build PRReview
        pr_meta = pr_context.get("pr", {})
        review = PRReview(
            repo_id=repo_id,
            pr_number=pr_number,
            pr_title=pr_meta.get("title", f"PR #{pr_number}"),
            pr_author=pr_meta.get("author", "unknown"),
            summary=result.get("summary", ""),
            risk_level=self._normalise_risk_level(
                result.get("risk_level", "medium")
            ),
            verdict=self._normalise_verdict(
                result.get("verdict", "needs_discussion")
            ),
            issues=issues,
            missing_tests=result.get("missing_tests", []),
            praise=result.get("praise", []),
        )

        self.reviews[review.id] = review

        # Emit event
        event = create_ws_event(
            task_id="system",
            event_type=EventType.PR_REVIEWED,
            payload={
                "repo_id": repo_id,
                "pr_number": pr_number,
                "verdict": review.verdict,
                "risk_level": review.risk_level,
                "issues_found": len(issues),
                "review_id": review.id,
            },
        )
        await event_router.emit(event)

        logger.info(
            "PR #%d review complete: verdict=%s, risk=%s, issues=%d",
            pr_number,
            review.verdict,
            review.risk_level,
            len(issues),
        )
        return review

    # ── Quick single-file review ─────────────────────────────────────────

    async def quick_file_review(
        self, repo_id: str, file_path: str
    ) -> list[CodeIssue]:
        """Review a single file for issues.

        Lighter-weight than a full repo/PR analysis. Suitable for the
        "scan this file" UI action.
        """
        content = await self.repo_manager.get_file_content(repo_id, file_path)
        content = _truncate_content(content)

        system_prompt = (
            "You are an expert code reviewer. Review the following file for "
            "bugs, security issues, performance problems, and code quality. "
            "Respond in JSON with an array of issues:\n"
            '[{"file": "path", "line": null, "type": "bug|security|performance'
            '|error_handling|testing|style|refactor", "severity": "critical|high'
            '|medium|low", "description": "what\'s wrong", "suggestion": '
            '"how to fix it"}]'
        )

        result = await self.claude.complete_with_json(
            system_prompt=system_prompt,
            user_message=f"File: {file_path}\n\n```\n{content}\n```",
            max_tokens=4096,
        )

        issues: list[CodeIssue] = []
        raw_issues = result if isinstance(result, list) else result.get("issues", [])
        if isinstance(result, dict) and "error" not in result and not raw_issues:
            # Claude may have returned issues at top level as a list
            raw_issues = [result] if "description" in result else []

        for raw in raw_issues:
            issue = CodeIssue(
                repo_id=repo_id,
                file_path=file_path,
                line_number=raw.get("line"),
                issue_type=self._normalise_issue_type(
                    raw.get("type", "refactor")
                ),
                severity=self._normalise_severity(
                    raw.get("severity", "medium")
                ),
                description=raw.get("description", ""),
                suggestion=raw.get("suggestion", ""),
            )
            self.issues[issue.id] = issue
            issues.append(issue)

        logger.info(
            "Quick review of %s: %d issues found", file_path, len(issues)
        )
        return issues

    # ── Private helpers ──────────────────────────────────────────────────

    async def _single_pr_review(
        self,
        repo: Any,
        pr_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Run PR review in a single Claude call."""
        user_message = self._build_pr_prompt(pr_context)
        return await self.claude.complete_with_json(
            system_prompt=PR_REVIEWER_PROMPT,
            user_message=user_message,
            max_tokens=4096,
        )

    async def _batched_pr_review(
        self,
        repo: Any,
        pr_context: dict[str, Any],
        changed_files: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Review a large PR by batching files into groups.

        Each batch is reviewed independently, then results are merged.
        """
        pr_meta = pr_context.get("pr", {})
        diff = pr_context.get("diff", "")

        batches = [
            changed_files[i : i + _BATCH_SIZE]
            for i in range(0, len(changed_files), _BATCH_SIZE)
        ]

        logger.info(
            "Large PR (#%d files) — splitting into %d batches",
            len(changed_files),
            len(batches),
        )

        async def _review_batch(batch: list[dict[str, Any]]) -> dict[str, Any]:
            batch_context = {
                "pr": pr_meta,
                "diff": "",  # only send relevant patches
                "changed_files": batch,
                "related_files": [],
            }
            user_message = self._build_pr_prompt(batch_context)
            return await self.claude.complete_with_json(
                system_prompt=PR_REVIEWER_PROMPT,
                user_message=user_message,
                max_tokens=4096,
            )

        batch_results = await asyncio.gather(
            *[_review_batch(b) for b in batches]
        )

        # Merge results
        merged: dict[str, Any] = {
            "summary": "",
            "risk_level": "low",
            "issues": [],
            "missing_tests": [],
            "verdict": "approve",
            "praise": [],
        }

        risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        verdict_order = {"approve": 0, "needs_discussion": 1, "request_changes": 2}
        summaries: list[str] = []

        for br in batch_results:
            if isinstance(br, dict) and "error" not in br:
                summaries.append(br.get("summary", ""))
                merged["issues"].extend(br.get("issues", []))
                merged["missing_tests"].extend(br.get("missing_tests", []))
                merged["praise"].extend(br.get("praise", []))
                # Take the worst risk_level
                br_risk = br.get("risk_level", "low")
                if risk_order.get(br_risk, 0) > risk_order.get(
                    merged["risk_level"], 0
                ):
                    merged["risk_level"] = br_risk
                # Take the most conservative verdict
                br_verdict = br.get("verdict", "approve")
                if verdict_order.get(br_verdict, 0) > verdict_order.get(
                    merged["verdict"], 0
                ):
                    merged["verdict"] = br_verdict

        merged["summary"] = " ".join(s for s in summaries if s)
        return merged

    def _build_pr_prompt(self, pr_context: dict[str, Any]) -> str:
        """Format the PR context into a prompt for Claude."""
        pr = pr_context.get("pr", {})
        parts: list[str] = [
            f"## PR #{pr.get('number', '?')}: {pr.get('title', 'Untitled')}",
            f"**Author:** {pr.get('author', 'unknown')}",
        ]

        body = pr.get("body", "")
        if body:
            parts.append(f"\n**Description:**\n{body}")

        # Inject Repository Semantic Map if available
        repo_id = pr_context.get("repo_id")
        if repo_id:
            map_path = os.path.join(self.repo_manager.clone_base_path, repo_id, ".agent_hq_repo_map.md")
            if os.path.exists(map_path):
                try:
                    with open(map_path, "r", encoding="utf-8") as f:
                        repo_map = f.read()
                    parts.append(f"\n### General Repository Architecture\n{repo_map}")
                except Exception:
                    pass

        # Full diff
        diff = pr_context.get("diff", "")
        if diff:
            parts.append(f"\n### Full Diff\n```diff\n{diff}\n```")

        # Changed files with full content
        changed = pr_context.get("changed_files", [])
        if changed:
            parts.append("\n### Changed Files (full content)")
            for cf in changed:
                path = cf.get("path", "?")
                content = cf.get("full_content", "")
                patch = cf.get("patch", "")

                # Smart truncation using changed-line info
                changed_lines = _extract_changed_lines(patch) if patch else None
                truncated = _smart_truncate(content, changed_lines)

                parts.append(
                    f"\n#### {path} ({cf.get('status', 'modified')})\n"
                    f"```\n{truncated}\n```"
                )

        # Related files
        related = pr_context.get("related_files", [])
        if related:
            parts.append("\n### Related Files (surrounding context)")
            for rf in related:
                content = _truncate_content(rf.get("content", ""), max_lines=200)
                parts.append(
                    f"\n#### {rf.get('path', '?')} ({rf.get('relation', '')})\n"
                    f"```\n{content}\n```"
                )

        return "\n".join(parts)

    @staticmethod
    def _format_file_tree(structure: dict[str, Any]) -> str:
        """Format the file tree into a readable summary."""
        files = structure.get("files", [])
        total = structure.get("total_files", 0)
        langs = structure.get("languages", {})

        # Show up to 100 file paths
        paths = [f["path"] for f in files[:100]]
        tree = "\n".join(paths)
        if len(files) > 100:
            tree += f"\n... and {len(files) - 100} more files"

        lang_summary = ", ".join(
            f"{ext}: {count}" for ext, count in sorted(
                langs.items(), key=lambda x: -x[1]
            )[:10]
        )

        return (
            f"Total files: {total}\n"
            f"Languages: {lang_summary}\n\n"
            f"{tree}"
        )

    @staticmethod
    def _format_key_files(key_files: list[dict[str, Any]]) -> str:
        """Format key files into prompt sections, truncating at 200 lines each."""
        parts: list[str] = []
        for kf in key_files:
            content = _truncate_content(kf.get("content", ""), max_lines=200)
            parts.append(
                f"\n#### [{kf.get('category', '?')}] {kf.get('path', '?')}\n"
                f"```\n{content}\n```"
            )
        return "\n".join(parts)

    # ── Normalisation helpers ────────────────────────────────────────────

    @staticmethod
    def _normalise_issue_type(raw: str) -> str:
        """Map Claude's free-form issue type to our enum."""
        valid = {
            "bug", "security", "performance", "error_handling",
            "testing", "style", "breaking", "refactor",
        }
        normalised = raw.lower().replace(" ", "_").replace("-", "_")
        return normalised if normalised in valid else "refactor"

    @staticmethod
    def _normalise_severity(raw: str) -> str:
        """Map Claude's severity to our enum."""
        valid = {"critical", "high", "medium", "low"}
        return raw.lower() if raw.lower() in valid else "medium"

    @staticmethod
    def _normalise_risk_level(raw: str) -> str:
        valid = {"low", "medium", "high", "critical"}
        return raw.lower() if raw.lower() in valid else "medium"

    @staticmethod
    def _normalise_verdict(raw: str) -> str:
        valid = {"approve", "request_changes", "needs_discussion"}
        return raw.lower() if raw.lower() in valid else "needs_discussion"
