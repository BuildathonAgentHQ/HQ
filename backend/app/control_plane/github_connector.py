"""
GitHub Connector for Agent HQ Control Plane.

Handles retrieving PR data, diffs, commits, and check runs from the GitHub REST API.
Includes a 5-minute in-memory cache and conditional requests (ETag) to minimize rate limits.
Falls back to mock data gracefully when USE_GITHUB is False.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from backend.app.config import Settings
from shared.mocks import mock_github

logger = logging.getLogger(__name__)


class GitHubConnector:
    """Connects to GitHub REST API with caching and fallback."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.use_github = settings.USE_GITHUB
        self.base_url = "https://api.github.com"
        
        # Simple in-memory cache: URL -> {"data": Any, "etag": str, "expires_at": datetime}
        self.cache: dict[str, dict[str, Any]] = {}
        self.cache_ttl = timedelta(minutes=5)
        
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Agent-HQ-Control-Plane",
        }
        if self.use_github and self.settings.GITHUB_TOKEN:
            self.headers["Authorization"] = f"Bearer {self.settings.GITHUB_TOKEN}"
            
        self.owner_repo = self.settings.GITHUB_REPO or "BuiltathonAgentHQ/HQ"

    def _get_cache(self, url: str) -> Optional[dict[str, Any]]:
        if url in self.cache:
            entry = self.cache[url]
            if datetime.now(timezone.utc) < entry["expires_at"]:
                return entry
            # Expired, but keep for ETag in request
            return entry
        return None

    def _set_cache(self, url: str, data: Any, etag: Optional[str] = None):
        self.cache[url] = {
            "data": data,
            "etag": etag,
            "expires_at": datetime.now(timezone.utc) + self.cache_ttl
        }

    async  def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.base_url}{path}"
        
        # Check cache
        if method.upper() == "GET":
            cached = self._get_cache(url)
            # If not expired, serve immediately
            if cached and datetime.now(timezone.utc) < cached["expires_at"]:
                logger.debug(f"Cache hit (fresh) for {url}")
                return cached["data"]
            
            # If expired but has ETag, use If-None-Match
            if cached and cached.get("etag"):
                headers = kwargs.pop("headers", {})
                headers["If-None-Match"] = cached["etag"]
                kwargs["headers"] = headers

        headers = kwargs.pop("headers", {})
        merged_headers = {**self.headers, **headers}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(method, url, headers=merged_headers, **kwargs)
                
                # Check rate limit
                remaining = response.headers.get("X-RateLimit-Remaining")
                if remaining is not None and int(remaining) < 10:
                    logger.warning(f"GitHub API rate limit critical: {remaining} requests left.")
                
                if response.status_code == 304 and method.upper() == "GET":
                    logger.debug(f"Cache hit (304 Not Modified) for {url}")
                    # Update expiration
                    self.cache[url]["expires_at"] = datetime.now(timezone.utc) + self.cache_ttl
                    return self.cache[url]["data"]
                    
                response.raise_for_status()
                
                # We expect JSON for most endpoints, unless specified otherwise
                is_json = "application/json" in response.headers.get("Content-Type", "")
                data = response.json() if is_json else response.text
                
                # Update cache on success
                if method.upper() == "GET":
                    etag = response.headers.get("ETag")
                    self._set_cache(url, data, etag)
                    
                return data
                
            except httpx.HTTPStatusError as e:
                logger.error(f"GitHub API error {e.response.status_code}: {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Request failed: {e}")
                raise

    def invalidate_pr_cache(self) -> None:
        """Clear cached PR list so the next fetch returns fresh data from GitHub."""
        url = f"{self.base_url}/repos/{self.owner_repo}/pulls?state=open"
        if url in self.cache:
            del self.cache[url]
            logger.debug("Invalidated PR list cache")

    async def get_open_prs(self, *, bypass_cache: bool = False) -> list[dict[str, Any]]:
        if not self.use_github:
            return mock_github.get_sample_prs()
        if bypass_cache:
            self.invalidate_pr_cache()
        try:
            path = f"/repos/{self.owner_repo}/pulls?state=open"
            return await self._request("GET", path)
        except Exception:
            logger.warning("get_open_prs: GitHub API failed; falling back to mock", exc_info=True)
            return mock_github.get_sample_prs()

    async def get_all_prs(self, per_page: int = 100) -> list[dict[str, Any]]:
        """Fetch all PRs (open + closed + merged), paginated."""
        if not self.use_github:
            return mock_github.get_sample_prs()
        try:
            all_prs: list[dict[str, Any]] = []
            page = 1
            while True:
                path = f"/repos/{self.owner_repo}/pulls?state=all&per_page={per_page}&page={page}"
                batch = await self._request("GET", path)
                if not batch:
                    break
                all_prs.extend(batch)
                if len(batch) < per_page:
                    break
                page += 1
            return all_prs
        except Exception:
            logger.warning("get_all_prs: GitHub API failed; falling back to mock", exc_info=True)
            return mock_github.get_sample_prs()

    async def get_pr_diff(self, pr_number: int) -> str:
        if not self.use_github:
            files = mock_github.get_sample_pr_files(pr_number)
            return "\n\n".join(f"diff --git a/{f['filename']} b/{f['filename']}\n{f.get('patch', '')}" for f in files)
        try:
            path = f"/repos/{self.owner_repo}/pulls/{pr_number}"
            return await self._request("GET", path, headers={"Accept": "application/vnd.github.v3.diff"})
        except Exception:
            logger.warning("get_pr_diff: GitHub API failed; falling back to mock", exc_info=True)
            files = mock_github.get_sample_pr_files(pr_number)
            return "\n\n".join(f"diff --git a/{f['filename']} b/{f['filename']}\n{f.get('patch', '')}" for f in files)

    async def get_pr_files(self, pr_number: int) -> list[dict[str, Any]]:
        if not self.use_github:
            return mock_github.get_sample_pr_files(pr_number)
        try:
            path = f"/repos/{self.owner_repo}/pulls/{pr_number}/files"
            return await self._request("GET", path)
        except Exception:
            logger.warning("get_pr_files: GitHub API failed; falling back to mock", exc_info=True)
            return mock_github.get_sample_pr_files(pr_number)

    async def get_commit_history(self, count: int = 50) -> list[dict[str, Any]]:
        if not self.use_github:
            return mock_github.get_sample_commits(count)
        try:
            path = f"/repos/{self.owner_repo}/commits?per_page={count}"
            return await self._request("GET", path)
        except Exception:
            logger.warning("get_commit_history: GitHub API failed; falling back to mock", exc_info=True)
            return mock_github.get_sample_commits(count)

    async def get_check_runs(self, ref: str) -> list[dict[str, Any]]:
        if not self.use_github:
            status = mock_github.get_sample_ci_status(ref)
            return status.get("statuses", [])
        try:
            path = f"/repos/{self.owner_repo}/commits/{ref}/check-runs"
            response = await self._request("GET", path)
            return response.get("check_runs", [])
        except Exception:
            logger.warning("get_check_runs: GitHub API failed; falling back to mock", exc_info=True)
            status = mock_github.get_sample_ci_status(ref)
            return status.get("statuses", [])

    async def create_pr(self, title: str, body: str, head: str, base: str = "main") -> dict[str, Any]:
        if not self.use_github:
            return {
                "number": 999, "title": title, "body": body,
                "html_url": f"https://github.com/{self.owner_repo}/pull/999", "state": "open"
            }
        try:
            path = f"/repos/{self.owner_repo}/pulls"
            payload = {"title": title, "body": body, "head": head, "base": base}
            return await self._request("POST", path, json=payload)
        except Exception:
            logger.warning("create_pr: GitHub API failed; returning mock", exc_info=True)
            return {
                "number": 999, "title": title, "body": body,
                "html_url": f"https://github.com/{self.owner_repo}/pull/999", "state": "open"
            }

    # ── New methods for swarm agents ─────────────────────────────────────

    async def create_branch(
        self, repo: str, branch_name: str, from_branch: str = "main"
    ) -> dict[str, Any]:
        """Create a new branch from an existing branch.

        Steps:
            1. Get the SHA of the source branch.
            2. Create a new ref pointing to the same SHA.
        """
        if not self.use_github:
            return {"ref": f"refs/heads/{branch_name}", "sha": "mock_sha"}
        try:
            # Get source branch SHA
            ref_data = await self._request(
                "GET", f"/repos/{repo}/git/ref/heads/{from_branch}"
            )
            sha = ref_data["object"]["sha"]

            # Create new branch
            return await self._request(
                "POST",
                f"/repos/{repo}/git/refs",
                json={"ref": f"refs/heads/{branch_name}", "sha": sha},
            )
        except Exception:
            logger.warning("create_branch failed", exc_info=True)
            return {"ref": f"refs/heads/{branch_name}", "sha": "error"}

    async def create_or_update_file(
        self,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str,
    ) -> dict[str, Any]:
        """Create or update a file on a branch via GitHub Contents API.

        Automatically handles existing files by fetching their current SHA.
        The content is base64-encoded before sending.
        """
        import base64

        if not self.use_github:
            return {"content": {"path": path, "sha": "mock_sha"}, "commit": {"sha": "mock_commit"}}
        try:
            # Check if file exists (need its sha for update)
            sha: Optional[str] = None
            try:
                existing = await self._request(
                    "GET",
                    f"/repos/{repo}/contents/{path}",
                    params={"ref": branch},
                )
                sha = existing.get("sha")
            except Exception:
                pass  # file doesn't exist yet

            payload: dict[str, Any] = {
                "message": message,
                "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                "branch": branch,
            }
            if sha:
                payload["sha"] = sha

            return await self._request(
                "PUT", f"/repos/{repo}/contents/{path}", json=payload
            )
        except Exception:
            logger.warning("create_or_update_file failed", exc_info=True)
            return {"content": {"path": path}, "commit": {"sha": "error"}}

    async def create_pull_request(
        self,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> dict[str, Any]:
        """Create a pull request on a specific repository.

        Unlike ``create_pr`` (which uses ``self.owner_repo``), this method
        accepts an explicit ``repo`` parameter for use by swarm agents
        operating on dynamically-connected repositories.
        """
        if not self.use_github:
            return {
                "number": 999,
                "title": title,
                "body": body,
                "html_url": f"https://github.com/{repo}/pull/999",
                "state": "open",
            }
        try:
            return await self._request(
                "POST",
                f"/repos/{repo}/pulls",
                json={"title": title, "body": body, "head": head, "base": base},
            )
        except Exception:
            logger.warning("create_pull_request failed", exc_info=True)
            return {
                "number": 999,
                "title": title,
                "html_url": f"https://github.com/{repo}/pull/999",
                "state": "open",
            }

    async def add_pr_comment(
        self, repo: str, pr_number: int, body: str
    ) -> dict[str, Any]:
        """Add a comment to a pull request."""
        if not self.use_github:
            return {"id": 1, "body": body}
        try:
            return await self._request(
                "POST",
                f"/repos/{repo}/issues/{pr_number}/comments",
                json={"body": body},
            )
        except Exception:
            logger.warning("add_pr_comment failed", exc_info=True)
            return {"id": 0, "body": body}

