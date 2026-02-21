"""
backend/app/swarm/orchestrator.py — Swarm execution engine.

Coordinates specialist agents to fix issues discovered by Claude analysis.
Manages execution plans with dependency ordering, parallel task dispatch,
fix proposal collection, and GitHub PR creation for approved fixes.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from backend.app.claude_client.client import ClaudeClient
from backend.app.claude_client.prompts import (
    DOC_WRITER_PROMPT,
    FIX_GENERATOR_PROMPT,
    REFACTOR_PROMPT,
    SECURITY_AUDITOR_PROMPT,
    SWARM_COORDINATOR_PROMPT,
    TEST_WRITER_PROMPT,
)
from backend.app.control_plane.github_connector import GitHubConnector
from backend.app.repo_manager.manager import RepoManager
from backend.app.websocket.events import EventRouter
from shared.events import EventType, create_ws_event
from shared.schemas import CodeIssue, FixProposal, SwarmPlan, SwarmTask

logger = logging.getLogger(__name__)


class SwarmOrchestrator:
    """Brain of the agent swarm.

    Takes a set of issues, asks Claude to build an execution plan, dispatches
    specialist agents in dependency order, collects results, and optionally
    applies fixes via GitHub PRs.
    """

    def __init__(
        self,
        claude: ClaudeClient,
        repo_manager: RepoManager,
        github: GitHubConnector,
        event_router: EventRouter,
    ) -> None:
        self.claude = claude
        self.repo_manager = repo_manager
        self.github = github
        self.event_router = event_router

        # Active plans keyed by plan.id
        self.active_plans: dict[str, SwarmPlan] = {}

        # Collected fix proposals keyed by fix.id
        self.fix_proposals: dict[str, FixProposal] = {}

    # ═════════════════════════════════════════════════════════════════════
    #  1. Planning
    # ═════════════════════════════════════════════════════════════════════

    async def plan_fix(
        self,
        repo_id: str,
        issues: list[CodeIssue],
        pr_number: Optional[int] = None,
    ) -> SwarmPlan:
        """Create an execution plan for fixing the given issues.

        Returns a ``SwarmPlan`` in ``planning`` status — NOT yet executed.
        The user can review and approve before calling ``execute_plan``.
        """
        repo = await self.repo_manager.get_repo(repo_id)

        # Format issues for the coordinator prompt
        issues_text = "\n".join(
            f"- [{i.severity.upper()}] ({i.issue_type}) {i.file_path}"
            f"{f':L{i.line_number}' if i.line_number else ''}: "
            f"{i.description}"
            for i in issues
        )

        user_message = (
            f"## Repository: {repo.full_name}\n\n"
            f"### Issues to fix ({len(issues)} total)\n{issues_text}\n\n"
            "Create an execution plan to fix these issues. "
            "Determine the right specialist agents and execution order."
        )

        result = await self.claude.complete_with_json(
            system_prompt=SWARM_COORDINATOR_PROMPT,
            user_message=user_message,
            max_tokens=4096,
        )

        # Build SwarmTask objects from Claude's plan
        tasks: list[SwarmTask] = []
        step_id_map: dict[int, str] = {}  # step_number → task.id

        for step in result.get("steps", []):
            task = SwarmTask(
                repo_id=repo_id,
                pr_number=pr_number,
                agent_type=self._normalise_agent_type(
                    step.get("agent_type", "fix_generator")
                ),
                task_description=step.get("task_description", ""),
                target_files=step.get("target_files", []),
            )
            step_num = step.get("step_number", 0)
            step_id_map[step_num] = task.id
            tasks.append(task)

        # Resolve depends_on from step numbers to task IDs
        for idx, step in enumerate(result.get("steps", [])):
            raw_deps = step.get("depends_on", [])
            if raw_deps and idx < len(tasks):
                tasks[idx].depends_on = [
                    step_id_map[d]
                    for d in raw_deps
                    if d in step_id_map
                ]

        plan = SwarmPlan(
            repo_id=repo_id,
            pr_number=pr_number,
            trigger="pr_review" if pr_number else "fix_issues",
            plan_summary=result.get("plan_summary", "Fix identified issues"),
            tasks=tasks,
            total_issues_found=len(issues),
        )

        self.active_plans[plan.id] = plan
        logger.info(
            "Swarm plan created: %s — %d tasks for %d issues",
            plan.id,
            len(tasks),
            len(issues),
        )
        return plan

    # ═════════════════════════════════════════════════════════════════════
    #  2. Execution
    # ═════════════════════════════════════════════════════════════════════

    async def execute_plan(self, plan_id: str) -> SwarmPlan:
        """Execute a plan by running tasks in dependency order.

        Tasks at the same dependency level run in parallel.
        """
        plan = self.active_plans.get(plan_id)
        if plan is None:
            raise KeyError(f"Plan not found: {plan_id}")

        plan.status = "executing"

        # Emit swarm_started
        await self.event_router.emit(
            create_ws_event(
                task_id="system",
                event_type=EventType.SWARM_STARTED,
                payload={
                    "plan_id": plan.id,
                    "repo_id": plan.repo_id,
                    "total_tasks": len(plan.tasks),
                    "plan_summary": plan.plan_summary,
                },
            )
        )

        logger.info("Executing plan %s: %d tasks", plan.id, len(plan.tasks))

        # Build a lookup of task status by ID
        task_map: dict[str, SwarmTask] = {t.id: t for t in plan.tasks}
        completed: set[str] = set()

        try:
            # Execute in waves until all tasks are done
            while len(completed) < len(plan.tasks):
                # Find tasks whose dependencies are all completed
                ready = [
                    t
                    for t in plan.tasks
                    if t.id not in completed
                    and t.status == "pending"
                    and all(d in completed for d in t.depends_on)
                ]

                if not ready:
                    # Check if any tasks are still running
                    running = [
                        t for t in plan.tasks
                        if t.status == "running"
                    ]
                    if not running:
                        # Deadlock — remaining tasks have unmet dependencies
                        logger.warning(
                            "Plan %s: no ready/running tasks but %d remain",
                            plan.id,
                            len(plan.tasks) - len(completed),
                        )
                        break
                    # Wait for running tasks (shouldn't normally happen with
                    # asyncio.gather, but safeguard against edge cases)
                    await asyncio.sleep(0.1)
                    continue

                # Run ready tasks in parallel
                results = await asyncio.gather(
                    *[
                        self._execute_task(t, plan.repo_id)
                        for t in ready
                    ],
                    return_exceptions=True,
                )

                for task, result in zip(ready, results):
                    if isinstance(result, Exception):
                        task.status = "failed"
                        task.result = {"error": str(result)}
                        logger.error(
                            "Task %s failed: %s", task.id, result
                        )
                    completed.add(task.id)

            # Count fix proposals
            plan.total_fixes_proposed = len(
                [
                    fp
                    for fp in self.fix_proposals.values()
                    if fp.repo_id == plan.repo_id
                ]
            )

            plan.status = "completed"

        except Exception:
            plan.status = "failed"
            logger.exception("Plan %s execution failed", plan.id)

        # Emit swarm_completed
        await self.event_router.emit(
            create_ws_event(
                task_id="system",
                event_type=EventType.SWARM_COMPLETED,
                payload={
                    "plan_id": plan.id,
                    "repo_id": plan.repo_id,
                    "status": plan.status,
                    "tasks_completed": len(completed),
                    "tasks_total": len(plan.tasks),
                    "fixes_proposed": plan.total_fixes_proposed,
                },
            )
        )

        logger.info(
            "Plan %s %s: %d/%d tasks, %d fixes proposed",
            plan.id,
            plan.status,
            len(completed),
            len(plan.tasks),
            plan.total_fixes_proposed,
        )
        return plan

    # ═════════════════════════════════════════════════════════════════════
    #  3. Task execution (dispatches to specialist agents)
    # ═════════════════════════════════════════════════════════════════════

    async def _execute_task(
        self, task: SwarmTask, repo_id: str
    ) -> dict[str, Any]:
        """Execute a single swarm task by dispatching to the right agent."""
        task.status = "running"
        task.started_at = datetime.now(timezone.utc)

        # Emit agent started
        await self.event_router.emit(
            create_ws_event(
                task_id="system",
                event_type=EventType.SWARM_AGENT_STARTED,
                payload={
                    "task_id": task.id,
                    "agent_type": task.agent_type,
                    "task_description": task.task_description,
                    "target_files": task.target_files,
                },
            )
        )

        logger.info(
            "Agent %s starting: %s",
            task.agent_type,
            task.task_description[:80],
        )

        try:
            # Fetch file contents for the agent
            file_contents = await self._fetch_target_files(
                repo_id, task.target_files
            )

            # Dispatch to the correct agent
            agent_dispatch = {
                "reviewer": self._run_reviewer,
                "test_writer": self._run_test_writer,
                "refactor": self._run_refactor,
                "security_auditor": self._run_security_auditor,
                "doc_writer": self._run_doc_writer,
                "fix_generator": self._run_fix_generator,
            }

            handler = agent_dispatch.get(task.agent_type, self._run_fix_generator)
            result = await handler(task, repo_id, file_contents)

            task.result = result
            task.status = "success"

        except Exception as exc:
            task.result = {"error": str(exc)}
            task.status = "failed"
            logger.exception("Agent %s failed", task.agent_type)
            result = task.result

        task.completed_at = datetime.now(timezone.utc)

        # Track tokens from the last Claude call
        usage = self.claude.get_usage_stats()
        task.tokens_used = usage.get("total_tokens", 0)
        task.cost = usage.get("estimated_cost_usd", 0.0)

        # Emit agent completed
        await self.event_router.emit(
            create_ws_event(
                task_id="system",
                event_type=EventType.SWARM_AGENT_COMPLETED,
                payload={
                    "task_id": task.id,
                    "agent_type": task.agent_type,
                    "status": task.status,
                    "tokens_used": task.tokens_used,
                    "cost": task.cost,
                },
            )
        )

        return result

    # ═════════════════════════════════════════════════════════════════════
    #  4. Specialist agent runners
    # ═════════════════════════════════════════════════════════════════════

    async def _run_reviewer(
        self, task: SwarmTask, repo_id: str, files: dict[str, str]
    ) -> dict[str, Any]:
        """Review files for issues (uses PR_REVIEWER_PROMPT logic)."""
        from backend.app.claude_client.prompts import PR_REVIEWER_PROMPT

        files_text = self._format_files(files)
        result = await self.claude.complete_with_json(
            system_prompt=PR_REVIEWER_PROMPT,
            user_message=f"Review these files:\n{files_text}",
            max_tokens=4096,
        )
        # Store discovered issues
        for raw in result.get("issues", []):
            self._store_issue(repo_id, task.pr_number, raw)
        return result

    async def _run_test_writer(
        self, task: SwarmTask, repo_id: str, files: dict[str, str]
    ) -> dict[str, Any]:
        """Generate tests for target files."""
        files_text = self._format_files(files)
        result = await self.claude.complete_with_json(
            system_prompt=TEST_WRITER_PROMPT,
            user_message=(
                f"Write tests for:\n{files_text}\n\n"
                f"Focus on: {task.task_description}"
            ),
            max_tokens=4096,
        )
        # If test code is produced, create a FixProposal for it
        test_code = result.get("test_code")
        test_path = result.get("test_file_path")
        if test_code and test_path:
            fp = FixProposal(
                issue_id="test_coverage",
                repo_id=repo_id,
                agent_type="test_writer",
                file_path=test_path,
                original_code="",
                fixed_code=test_code,
                explanation=f"New test file: {test_path}",
                test_code=None,
            )
            self.fix_proposals[fp.id] = fp
        return result

    async def _run_refactor(
        self, task: SwarmTask, repo_id: str, files: dict[str, str]
    ) -> dict[str, Any]:
        """Refactor target files."""
        files_text = self._format_files(files)
        result = await self.claude.complete_with_json(
            system_prompt=REFACTOR_PROMPT,
            user_message=(
                f"Refactor goal: {task.task_description}\n\n"
                f"Files:\n{files_text}"
            ),
            max_tokens=4096,
        )
        # Convert each change to a FixProposal
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
            self.fix_proposals[fp.id] = fp
        return result

    async def _run_security_auditor(
        self, task: SwarmTask, repo_id: str, files: dict[str, str]
    ) -> dict[str, Any]:
        """Security audit of target files."""
        files_text = self._format_files(files)
        result = await self.claude.complete_with_json(
            system_prompt=SECURITY_AUDITOR_PROMPT,
            user_message=f"Audit these files for security vulnerabilities:\n{files_text}",
            max_tokens=4096,
        )
        for vuln in result.get("vulnerabilities", []):
            self._store_issue(
                repo_id,
                task.pr_number,
                {
                    "file": vuln.get("file", ""),
                    "line": vuln.get("line"),
                    "type": "security",
                    "severity": vuln.get("severity", "medium"),
                    "description": vuln.get("description", ""),
                    "suggestion": vuln.get("fix", ""),
                },
            )
        return result

    async def _run_doc_writer(
        self, task: SwarmTask, repo_id: str, files: dict[str, str]
    ) -> dict[str, Any]:
        """Generate documentation for target files."""
        files_text = self._format_files(files)
        result = await self.claude.complete_with_json(
            system_prompt=DOC_WRITER_PROMPT,
            user_message=(
                f"Write documentation for:\n{files_text}\n\n"
                f"Focus: {task.task_description}"
            ),
            max_tokens=4096,
        )
        # Store doc content as a fix proposal (new file)
        content = result.get("content")
        doc_type = result.get("doc_type", "readme")
        if content:
            doc_path = {
                "readme": "README.md",
                "api_docs": "docs/API.md",
                "architecture": "docs/ARCHITECTURE.md",
            }.get(doc_type, f"docs/{doc_type}.md")
            fp = FixProposal(
                issue_id="documentation",
                repo_id=repo_id,
                agent_type="doc_writer",
                file_path=doc_path,
                original_code="",
                fixed_code=content,
                explanation=f"Generated {doc_type} documentation",
            )
            self.fix_proposals[fp.id] = fp
        return result

    async def _run_fix_generator(
        self, task: SwarmTask, repo_id: str, files: dict[str, str]
    ) -> dict[str, Any]:
        """Generate a concrete code fix for an issue."""
        files_text = self._format_files(files)
        result = await self.claude.complete_with_json(
            system_prompt=FIX_GENERATOR_PROMPT,
            user_message=(
                f"Issue: {task.task_description}\n\n"
                f"Files:\n{files_text}"
            ),
            max_tokens=4096,
        )

        fp = FixProposal(
            issue_id=task.id,  # link back to the originating task
            repo_id=repo_id,
            agent_type="fix_generator",
            file_path=result.get("file_path", task.target_files[0] if task.target_files else ""),
            original_code=result.get("original_code", ""),
            fixed_code=result.get("fixed_code", ""),
            explanation=result.get("explanation", ""),
            test_code=result.get("test_code") if result.get("test_needed") else None,
        )
        self.fix_proposals[fp.id] = fp

        # Emit fix_proposed
        await self.event_router.emit(
            create_ws_event(
                task_id="system",
                event_type=EventType.FIX_PROPOSED,
                payload={
                    "fix_id": fp.id,
                    "file_path": fp.file_path,
                    "explanation": fp.explanation[:200],
                    "agent_type": fp.agent_type,
                },
            )
        )
        return result

    # ═════════════════════════════════════════════════════════════════════
    #  5. Apply fixes via GitHub
    # ═════════════════════════════════════════════════════════════════════

    async def apply_fixes(
        self, plan_id: str, fix_ids: list[str]
    ) -> dict[str, Any]:
        """Apply approved fixes by creating a branch and PR on GitHub.

        Steps:
            1. Create branch ``fix/{plan_id_short}``
            2. For each fix, commit the changed file
            3. If a fix includes test code, also commit the test
            4. Open a single PR containing all fixes
            5. Emit ``fix_applied`` event

        Returns:
            Dict with ``pr_url``, ``branch``, ``fixes_applied`` count.
        """
        plan = self.active_plans.get(plan_id)
        if plan is None:
            raise KeyError(f"Plan not found: {plan_id}")

        repo = await self.repo_manager.get_repo(plan.repo_id)
        branch_name = f"fix/{plan_id[:8]}"

        # 1. Create branch
        await self.github.create_branch(
            repo.full_name, branch_name, repo.default_branch
        )

        # 2. Apply each fix
        applied_count = 0
        fix_summaries: list[str] = []

        for fix_id in fix_ids:
            fp = self.fix_proposals.get(fix_id)
            if fp is None:
                logger.warning("Fix %s not found; skipping", fix_id)
                continue

            try:
                # Commit the fix
                await self.github.create_or_update_file(
                    repo=repo.full_name,
                    path=fp.file_path,
                    content=fp.fixed_code,
                    message=f"fix: {fp.explanation[:72]}",
                    branch=branch_name,
                )

                # Commit test if present
                if fp.test_code:
                    test_path = self._derive_test_path(fp.file_path)
                    await self.github.create_or_update_file(
                        repo=repo.full_name,
                        path=test_path,
                        content=fp.test_code,
                        message=f"test: add tests for {fp.file_path}",
                        branch=branch_name,
                    )

                fp.status = "applied"
                applied_count += 1
                fix_summaries.append(
                    f"- **{fp.file_path}** ({fp.agent_type}): {fp.explanation}"
                )
            except Exception:
                logger.exception("Failed to apply fix %s", fix_id)
                fp.status = "rejected"

        # 3. Create PR
        pr_title = f"Agent HQ: Fix {applied_count} issues"
        if plan.pr_number:
            pr_title += f" from PR #{plan.pr_number}"
        else:
            pr_title += f" from repo audit"

        pr_body = (
            "## 🤖 Agent HQ Automated Fixes\n\n"
            f"**Plan ID:** `{plan_id}`\n"
            f"**Fixes applied:** {applied_count}\n\n"
            "### Changes\n" + "\n".join(fix_summaries)
        )

        pr_result = await self.github.create_pull_request(
            repo=repo.full_name,
            title=pr_title,
            body=pr_body,
            head=branch_name,
            base=repo.default_branch,
        )

        pr_url = pr_result.get("html_url", "")
        plan.total_fixes_applied = applied_count

        # 4. Emit event
        await self.event_router.emit(
            create_ws_event(
                task_id="system",
                event_type=EventType.FIX_APPLIED,
                payload={
                    "plan_id": plan_id,
                    "pr_url": pr_url,
                    "branch": branch_name,
                    "fixes_applied": applied_count,
                },
            )
        )

        logger.info(
            "Applied %d fixes on branch %s → PR: %s",
            applied_count,
            branch_name,
            pr_url,
        )
        return {
            "pr_url": pr_url,
            "branch": branch_name,
            "fixes_applied": applied_count,
        }

    async def apply_all_fixes(self, plan_id: str) -> dict[str, Any]:
        """Approve and apply ALL proposed fixes from a plan.

        Convenience method for the "Fix All" button in the UI.
        """
        plan = self.active_plans.get(plan_id)
        if plan is None:
            raise KeyError(f"Plan not found: {plan_id}")

        # Collect all fix IDs that belong to this plan's repo
        all_fix_ids = [
            fp.id
            for fp in self.fix_proposals.values()
            if fp.repo_id == plan.repo_id and fp.status == "proposed"
        ]

        if not all_fix_ids:
            return {"pr_url": "", "branch": "", "fixes_applied": 0}

        return await self.apply_fixes(plan_id, all_fix_ids)

    # ═════════════════════════════════════════════════════════════════════
    #  Helpers
    # ═════════════════════════════════════════════════════════════════════

    async def _fetch_target_files(
        self, repo_id: str, paths: list[str]
    ) -> dict[str, str]:
        """Fetch content for a list of files, returning {path: content}."""
        result: dict[str, str] = {}

        async def _get(p: str) -> tuple[str, str]:
            try:
                content = await self.repo_manager.get_file_content(repo_id, p)
                return p, content
            except Exception:
                return p, "<file not found>"

        entries = await asyncio.gather(*[_get(p) for p in paths])
        for path, content in entries:
            result[path] = content
        return result

    @staticmethod
    def _format_files(files: dict[str, str]) -> str:
        """Format file contents into a prompt-friendly string."""
        parts: list[str] = []
        for path, content in files.items():
            # Truncate very long files
            lines = content.splitlines()
            if len(lines) > 500:
                content = "\n".join(lines[:500]) + f"\n... ({len(lines)} total lines)"
            parts.append(f"### {path}\n```\n{content}\n```")
        return "\n\n".join(parts)

    def _store_issue(
        self,
        repo_id: str,
        pr_number: Optional[int],
        raw: dict[str, Any],
    ) -> CodeIssue:
        """Create and store a CodeIssue from a raw Claude result dict."""
        valid_types = {
            "bug", "security", "performance", "error_handling",
            "testing", "style", "breaking", "refactor",
        }
        valid_severities = {"critical", "high", "medium", "low"}

        issue_type = raw.get("type", "refactor").lower().replace(" ", "_")
        if issue_type not in valid_types:
            issue_type = "refactor"

        severity = raw.get("severity", "medium").lower()
        if severity not in valid_severities:
            severity = "medium"

        issue = CodeIssue(
            repo_id=repo_id,
            pr_number=pr_number,
            file_path=raw.get("file", ""),
            line_number=raw.get("line"),
            issue_type=issue_type,
            severity=severity,
            description=raw.get("description", ""),
            suggestion=raw.get("suggestion", raw.get("fix", "")),
        )
        # Also store in the repo_analyzer issues if available
        return issue

    @staticmethod
    def _normalise_agent_type(raw: str) -> str:
        """Map raw agent_type to a valid SwarmTask.agent_type literal."""
        valid = {
            "coordinator", "reviewer", "test_writer", "refactor",
            "security_auditor", "doc_writer", "fix_generator",
        }
        normalised = raw.lower().replace(" ", "_").replace("-", "_")
        return normalised if normalised in valid else "fix_generator"

    @staticmethod
    def _derive_test_path(file_path: str) -> str:
        """Derive a test file path from a source file path."""
        parts = file_path.rsplit("/", 1)
        if len(parts) == 2:
            directory, filename = parts
        else:
            directory, filename = "", parts[0]

        name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "py")

        # Python: test_foo.py  JS/TS: foo.test.ts
        if ext == "py":
            test_name = f"test_{name}.{ext}"
        else:
            test_name = f"{name}.test.{ext}"

        if directory:
            # Place in tests/ sibling directory if possible
            parent = directory.rsplit("/", 1)[0] if "/" in directory else directory
            return f"{parent}/tests/{test_name}"
        return f"tests/{test_name}"
