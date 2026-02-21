"""
backend/app/repo_manager/manager.py — Repository lifecycle and GitHub integration.

Handles connecting GitHub repos, fetching file trees and content, identifying
key files for Claude analysis, and assembling full PR context for code review.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from backend.app.config import Settings
from backend.app.control_plane.github_connector import GitHubConnector
from backend.app.websocket.events import event_router
from shared.events import EventType, create_ws_event
from shared.schemas import Repository

logger = logging.getLogger(__name__)


# ── Patterns for identifying key files ──────────────────────────────────────

_ENTRY_POINT_PATTERNS = re.compile(
    r"(^|/)("
    r"main\.\w+|index\.\w+|app\.\w+|manage\.py|server\.\w+"
    r")$"
)

_CONFIG_PATTERNS = re.compile(
    r"(^|/)("
    r"package\.json|requirements\.txt|Cargo\.toml|pyproject\.toml|go\.mod"
    r"|Gemfile|Dockerfile|docker-compose[^/]*\.ya?ml|\.env\.example"
    r"|tsconfig\.json|webpack\.config\.\w+|vite\.config\.\w+"
    r")$"
)

_SCHEMA_PATTERNS = re.compile(
    r"(^|/)("
    r"models\.\w+|schema\w*\.\w+|types\.\w+"
    r")$"
)

_ROUTE_PATTERNS = re.compile(
    r"(^|/)("
    r"routes?\.\w+|api\.\w+|views?\.\w+|controllers?\.\w+|router\.\w+"
    r")$"
)

_TEST_PATTERNS = re.compile(
    r"(^|/)("
    r"test_[^/]+|[^/]+_test\.\w+|[^/]+\.test\.\w+|[^/]+\.spec\.\w+"
    r")$"
)

# Directories to skip when building the file tree
_SKIP_DIRS = {
    "node_modules", "__pycache__", ".git", "dist", "build",
    ".next", ".nuxt", ".cache", "vendor", ".tox", ".mypy_cache",
    ".pytest_cache", "coverage", ".eggs", "egg-info",
}


class RepoManager:
    """Manages connected GitHub repositories for analysis by Claude.

    Responsibilities:
        - Adding / removing repos
        - Fetching file trees and individual file content via GitHub API
        - Identifying "key files" for Claude analysis
        - Assembling full PR context for deep code review
    """

    def __init__(self, settings: Settings, github: GitHubConnector) -> None:
        self.settings = settings
        self.github = github
        self.repos: dict[str, Repository] = {}
        self.clone_base_path = "/tmp/agent_hq_repos"

        # Content cache: (repo_id, path) → {"content": str, "expires_at": datetime}
        self._content_cache: dict[tuple[str, str], dict[str, Any]] = {}
        self._cache_ttl = timedelta(minutes=5)

    # ── CRUD ─────────────────────────────────────────────────────────────

    async def add_repo(self, owner: str, name: str) -> Repository:
        """Connect a GitHub repository and trigger initial analysis.

        Args:
            owner: GitHub user or org.
            name: Repository name.

        Returns:
            The newly created ``Repository`` object.

        Raises:
            ValueError: If the repo doesn't exist or is inaccessible.
        """
        full_name = f"{owner}/{name}"

        # Verify the repo exists via GitHub API
        try:
            repo_data = await self.github._request(
                "GET", f"/repos/{full_name}"
            )
        except Exception as exc:
            raise ValueError(
                f"Cannot access GitHub repo '{full_name}': {exc}"
            ) from exc

        repo = Repository(
            owner=owner,
            name=name,
            full_name=full_name,
            url=repo_data.get("html_url", f"https://github.com/{full_name}"),
            default_branch=repo_data.get("default_branch", "main"),
        )

        self.repos[repo.id] = repo

        # ── Local Clone (v2 optimization) ──
        repo_dir = os.path.join(self.clone_base_path, repo.id)
        if not os.path.exists(repo_dir):
            os.makedirs(self.clone_base_path, exist_ok=True)
            logger.info("Cloning %s locally to %s", repo.full_name, repo_dir)
            # Use git clone --depth=1 for speed. If auth needed, use GITHUB_TOKEN
            token = self.settings.GITHUB_TOKEN
            auth_url = repo.url.replace("https://", f"https://{token}@") if token else repo.url
            
            proc = await asyncio.create_subprocess_shell(
                f"git clone --depth 1 {auth_url} {repo_dir}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error("Git clone failed: %s", stderr.decode())
                # Fall back gracefully, but warn
            else:
                logger.info("Successfully cloned %s", repo.full_name)

        # Emit event
        event = create_ws_event(
            task_id="system",
            event_type=EventType.REPO_ADDED,
            payload=repo.model_dump(mode="json"),
        )
        await event_router.emit(event)

        logger.info("Repo added: %s (id=%s)", full_name, repo.id)
        return repo

    async def get_repo(self, repo_id: str) -> Repository:
        """Retrieve a connected repo by ID.

        Raises:
            KeyError: If repo_id is not found.
        """
        if repo_id not in self.repos:
            raise KeyError(f"Repository not found: {repo_id}")
        return self.repos[repo_id]

    async def list_repos(self) -> list[Repository]:
        """Return all connected repositories."""
        return list(self.repos.values())

    async def remove_repo(self, repo_id: str) -> None:
        """Disconnect a repository.

        Raises:
            KeyError: If repo_id is not found.
        """
        if repo_id not in self.repos:
            raise KeyError(f"Repository not found: {repo_id}")
        removed = self.repos.pop(repo_id)
        logger.info("Repo removed: %s (id=%s)", removed.full_name, repo_id)

    # ── File tree ────────────────────────────────────────────────────────

    async def get_repo_structure(self, repo_id: str) -> dict[str, Any]:
        """Fetch the full file tree from GitHub and return a structured dict.

        Returns::

            {
                "files": [{"path": str, "type": "file"|"dir", "size": int}],
                "total_files": int,
                "languages": {"py": 12, "ts": 8, ...}
            }
        """
        repo = await self.get_repo(repo_id)
        path = f"/repos/{repo.full_name}/git/trees/{repo.default_branch}?recursive=1"
        tree_data = await self.github._request("GET", path)

        files: list[dict[str, Any]] = []
        languages: dict[str, int] = {}

        for item in tree_data.get("tree", []):
            item_path: str = item.get("path", "")

            # Skip ignored directories
            parts = item_path.split("/")
            if any(p in _SKIP_DIRS for p in parts):
                continue

            entry_type = "file" if item.get("type") == "blob" else "dir"
            size = item.get("size", 0)
            files.append({"path": item_path, "type": entry_type, "size": size})

            # Count languages by extension
            if entry_type == "file" and "." in item_path:
                ext = item_path.rsplit(".", 1)[-1].lower()
                languages[ext] = languages.get(ext, 0) + 1

        return {
            "files": files,
            "total_files": sum(1 for f in files if f["type"] == "file"),
            "languages": languages,
        }

    # ── File content ─────────────────────────────────────────────────────

    async def get_file_content(self, repo_id: str, file_path: str) -> str:
        """Fetch a single file's content directly from the local cloned disk.

        Raises:
            ValueError: If the file cannot be fetched or read.
        """
        repo_dir = os.path.join(self.clone_base_path, repo_id)
        full_path = os.path.join(repo_dir, file_path)

        # Ensure we don't accidentally read outside the repo dir (LFI protection logic)
        real_repo_dir = os.path.realpath(repo_dir)
        real_full_path = os.path.realpath(full_path)
        if not real_full_path.startswith(real_repo_dir):
            raise ValueError(f"Path traversal detected: {file_path}")

        if not os.path.exists(real_full_path):
            # Fallback to API if we don't have it locally (e.g. repo not cloned correctly)
            repo = await self.get_repo(repo_id)
            api_path = f"/repos/{repo.full_name}/contents/{file_path}"
            try:
                data = await self.github._request("GET", api_path, params={"ref": repo.default_branch})
                content_b64 = data.get("content", "")
                return base64.b64decode(content_b64).decode("utf-8", errors="replace")
            except Exception as exc:
                raise ValueError(f"Cannot fetch '{file_path}' from {repo.full_name}: {exc}") from exc

        try:
            with open(real_full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return content
        except Exception as exc:
            raise ValueError(f"Cannot read local file '{file_path}': {exc}") from exc

    # ── Key files ────────────────────────────────────────────────────────

    async def get_key_files(
        self, repo_id: str, max_files: int = 20
    ) -> list[dict[str, Any]]:
        """Identify and return the most important files for Claude analysis.

        Prioritisation order:
            1. Entry points  (main.*, index.*, app.*, manage.py, server.*)
            2. Config files   (package.json, requirements.txt, etc.)
            3. Schemas/Models (models.*, schema.*, types.*)
            4. Routes/API     (routes.*, api.*, views.*, controllers.*)
            5. Tests          (test_*, *.test.*, *.spec.*)

        Returns:
            Up to ``max_files`` dicts with ``path``, ``category``,
            and ``content`` keys.
        """
        structure = await self.get_repo_structure(repo_id)

        # Classify each file
        categorised: dict[str, list[str]] = {
            "entry_point": [],
            "config": [],
            "schema": [],
            "route": [],
            "test": [],
        }

        for entry in structure["files"]:
            if entry["type"] != "file":
                continue
            p = entry["path"]
            if _ENTRY_POINT_PATTERNS.search(p):
                categorised["entry_point"].append(p)
            elif _CONFIG_PATTERNS.search(p):
                categorised["config"].append(p)
            elif _SCHEMA_PATTERNS.search(p):
                categorised["schema"].append(p)
            elif _ROUTE_PATTERNS.search(p):
                categorised["route"].append(p)
            elif _TEST_PATTERNS.search(p):
                categorised["test"].append(p)

        # Flatten into a priority-ordered list
        priority_order = ["entry_point", "config", "schema", "route", "test"]
        selected: list[dict[str, str]] = []
        for category in priority_order:
            for path in categorised[category]:
                if len(selected) >= max_files:
                    break
                selected.append({"path": path, "category": category})
            if len(selected) >= max_files:
                break

        # Fetch contents in parallel
        async def _fetch(item: dict[str, str]) -> dict[str, Any]:
            try:
                content = await self.get_file_content(repo_id, item["path"])
            except Exception:
                content = "<error fetching file>"
            return {
                "path": item["path"],
                "category": item["category"],
                "content": content,
            }

        results = await asyncio.gather(*[_fetch(item) for item in selected])
        return list(results)

    # ── PR context ───────────────────────────────────────────────────────

    async def get_pr_full_context(
        self, repo_id: str, pr_number: int
    ) -> dict[str, Any]:
        """Assemble everything Claude needs for a deep PR review.

        Returns::

            {
                "pr": {"number": int, "title": str, "author": str, "body": str},
                "diff": str,
                "changed_files": [
                    {"path": str, "status": str, "patch": str, "full_content": str}
                ],
                "related_files": [
                    {"path": str, "relation": str, "content": str}
                ]
            }
        """
        repo = await self.get_repo(repo_id)

        # 1. PR metadata
        pr_path = f"/repos/{repo.full_name}/pulls/{pr_number}"
        pr_data = await self.github._request("GET", pr_path)
        pr_meta = {
            "number": pr_data.get("number", pr_number),
            "title": pr_data.get("title", ""),
            "author": (pr_data.get("user") or {}).get("login", "unknown"),
            "body": pr_data.get("body", "") or "",
        }

        # 2. Full diff
        diff = await self.github.get_pr_diff(pr_number)

        # 3. Changed files with full content
        pr_files = await self.github.get_pr_files(pr_number)
        changed_files: list[dict[str, Any]] = []

        async def _fetch_changed(f: dict[str, Any]) -> dict[str, Any]:
            fpath = f.get("filename", "")
            try:
                full_content = await self.get_file_content(repo_id, fpath)
            except Exception:
                full_content = "<unavailable>"
            return {
                "path": fpath,
                "status": f.get("status", "modified"),
                "patch": f.get("patch", ""),
                "full_content": full_content,
            }

        changed_files = list(
            await asyncio.gather(*[_fetch_changed(f) for f in pr_files])
        )

        # 4. Related files — find imports for each changed file
        related_files: list[dict[str, Any]] = []
        changed_paths = {cf["path"] for cf in changed_files}

        for cf in changed_files:
            imports = self._extract_imports(cf["full_content"], cf["path"])
            for imp in imports:
                if imp in changed_paths:
                    continue  # already in changed files
                if imp in {rf["path"] for rf in related_files}:
                    continue  # already fetched
                try:
                    content = await self.get_file_content(repo_id, imp)
                    related_files.append({
                        "path": imp,
                        "relation": f"imported by {cf['path']}",
                        "content": content,
                    })
                except Exception:
                    pass  # skip files we can't fetch

        return {
            "pr": pr_meta,
            "diff": diff,
            "changed_files": changed_files,
            "related_files": related_files,
        }

    # ── PR listing ───────────────────────────────────────────────────────

    async def get_open_prs(self, repo_id: str) -> list[dict[str, Any]]:
        """List open PRs for a specific repository."""
        repo = await self.get_repo(repo_id)
        path = f"/repos/{repo.full_name}/pulls?state=open"
        try:
            prs = await self.github._request("GET", path)
            return [
                {
                    "number": pr.get("number"),
                    "title": pr.get("title", ""),
                    "author": (pr.get("user") or {}).get("login", "unknown"),
                    "created_at": pr.get("created_at"),
                    "updated_at": pr.get("updated_at"),
                    "url": pr.get("html_url", ""),
                }
                for pr in prs
            ]
        except Exception:
            logger.warning("Failed to fetch PRs for %s", repo.full_name, exc_info=True)
            return []

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _extract_imports(content: str, file_path: str) -> list[str]:
        """Best-effort extraction of import paths from source code.

        Returns a list of plausible relative file paths.  Not perfect, but
        good enough to pull in surrounding context for Claude.
        """
        imports: list[str] = []
        ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
        dir_prefix = "/".join(file_path.split("/")[:-1])

        if ext == "py":
            # from foo.bar import baz  →  foo/bar.py
            for match in re.finditer(
                r"^\s*from\s+([\w.]+)\s+import", content, re.MULTILINE
            ):
                mod_path = match.group(1).replace(".", "/") + ".py"
                imports.append(mod_path)
            # import foo.bar  →  foo/bar.py
            for match in re.finditer(
                r"^\s*import\s+([\w.]+)", content, re.MULTILINE
            ):
                mod_path = match.group(1).replace(".", "/") + ".py"
                imports.append(mod_path)

        elif ext in ("ts", "tsx", "js", "jsx"):
            # import ... from './foo'  or  require('./foo')
            for match in re.finditer(
                r"""(?:from|require\()\s*['"]([^'"]+)['"]""", content
            ):
                imp = match.group(1)
                if imp.startswith("."):
                    # Resolve relative path
                    resolved = f"{dir_prefix}/{imp}".replace("//", "/")
                    # Try common extensions
                    for try_ext in ("", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.js"):
                        imports.append(resolved + try_ext)

        return imports
