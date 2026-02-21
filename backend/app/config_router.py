"""
backend/app/config_router.py — Exposes selected configuration to the frontend.

Mounted at ``/api/config`` in ``main.py``.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.config import settings

router = APIRouter()


@router.get("/repo")
async def get_repo_config() -> dict:
    """Return the target repository name and URL.

    The frontend sidebar uses this to display which repo Agent HQ is
    controlling, with a clickable link to GitHub.
    """
    repo = settings.GITHUB_REPO  # e.g. "owner/repo" or just "repo"
    if not repo:
        return {"repo_name": "", "repo_url": "", "repo_owner": ""}

    parts = repo.split("/", 1)
    if len(parts) == 2:
        owner, name = parts
    else:
        owner, name = "", parts[0]

    url = f"https://github.com/{repo}" if "/" in repo else ""

    return {
        "repo_name": name,
        "repo_owner": owner,
        "repo_url": url,
    }
