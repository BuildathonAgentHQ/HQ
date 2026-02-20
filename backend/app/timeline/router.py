"""
backend/app/timeline/router.py — Git timeline & checkout endpoints.

Mounted at ``/api/timeline`` in ``main.py``.  Provides endpoints for
viewing commit history and checking out specific commits.  Uses mock
data from ``shared/mocks/mock_github.py`` until the real git integration
is wired.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared.mocks.mock_github import get_sample_commits

router = APIRouter()


class CheckoutRequest(BaseModel):
    """Request body for the checkout endpoint."""
    commit_hash: str


@router.get("/")
async def get_timeline() -> list[dict[str, Any]]:
    """Return a list of recent git commits with timestamps.

    Each entry includes the commit SHA, message, author, and date.
    Returns the 20 most recent commits.
    """
    raw_commits = get_sample_commits(limit=10)
    # Reshape into a cleaner timeline format
    timeline: list[dict[str, Any]] = []
    for c in raw_commits:
        timeline.append({
            "sha": c["sha"][:12],
            "message": c["commit"]["message"],
            "author": c["commit"]["author"]["name"],
            "date": c["commit"]["author"]["date"],
        })
    return timeline


@router.post("/checkout")
async def checkout_commit(body: CheckoutRequest) -> dict[str, str]:
    """Check out a specific commit by hash.

    In mock mode, this always succeeds and returns a confirmation.

    Args:
        body: CheckoutRequest with the target commit hash.

    Returns:
        ``{"status": "checked_out", "commit_hash": "..."}``
    """
    if not body.commit_hash or len(body.commit_hash) < 7:
        raise HTTPException(status_code=400, detail="Invalid commit hash")
    return {"status": "checked_out", "commit_hash": body.commit_hash}
