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

    async def get_open_prs(self) -> list[dict[str, Any]]:
        if not self.use_github:
            return mock_github.get_sample_prs()
            
        path = f"/repos/{self.owner_repo}/pulls?state=open"
        return await self._request("GET", path)

    async def get_pr_diff(self, pr_number: int) -> str:
        if not self.use_github:
            # Reconstruct dummy diff from mock files
            files = mock_github.get_sample_pr_files(pr_number)
            return "\n\n".join(f"diff --git a/{f['filename']} b/{f['filename']}\n{f.get('patch', '')}" for f in files)
            
        path = f"/repos/{self.owner_repo}/pulls/{pr_number}"
        return await self._request("GET", path, headers={"Accept": "application/vnd.github.v3.diff"})

    async def get_pr_files(self, pr_number: int) -> list[dict[str, Any]]:
        if not self.use_github:
            return mock_github.get_sample_pr_files(pr_number)
            
        path = f"/repos/{self.owner_repo}/pulls/{pr_number}/files"
        return await self._request("GET", path)

    async def get_commit_history(self, count: int = 50) -> list[dict[str, Any]]:
        if not self.use_github:
            return mock_github.get_sample_commits(count)
            
        path = f"/repos/{self.owner_repo}/commits?per_page={count}"
        return await self._request("GET", path)

    async def get_check_runs(self, ref: str) -> list[dict[str, Any]]:
        if not self.use_github:
            # Mock returns combined status, we wrap it in a pseudo check-runs list
            status = mock_github.get_sample_ci_status(ref)
            return status.get("statuses", [])
            
        path = f"/repos/{self.owner_repo}/commits/{ref}/check-runs"
        response = await self._request("GET", path)
        return response.get("check_runs", [])

    async def create_pr(self, title: str, body: str, head: str, base: str = "main") -> dict[str, Any]:
        if not self.use_github:
            return {
                "number": 999,
                "title": title,
                "body": body,
                "html_url": f"https://github.com/{self.owner_repo}/pull/999",
                "state": "open"
            }
            
        path = f"/repos/{self.owner_repo}/pulls"
        payload = {
            "title": title,
            "body": body,
            "head": head,
            "base": base
        }
        return await self._request("POST", path, json=payload)
