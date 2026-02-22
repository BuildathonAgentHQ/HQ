"""
backend/app/auth/router.py — GitHub OAuth authentication.

Provides login, callback, logout, and user/repo endpoints.
"""

from __future__ import annotations

import logging
import secrets
from typing import Any

import httpx
from fastapi import APIRouter, Cookie, Depends, Request, Response
from fastapi.responses import RedirectResponse

from backend.app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


def get_github_token(
    github_token: str | None = Cookie(default=None),
) -> str | None:
    """Extract GitHub token from cookie (cookie name: github_token)."""
    return github_token

# In-memory state for OAuth (in production use Redis or DB)
# state -> code_verifier for PKCE (optional)
_oauth_state_store: dict[str, str] = {}

# Cookie config
AUTH_COOKIE_NAME = "github_token"
AUTH_COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def _github_login_url(state: str) -> str:
    scopes = (settings.GITHUB_OAUTH_SCOPES or "repo,read:user").strip()
    redirect_uri = settings.GITHUB_OAUTH_REDIRECT_URI or f"http://localhost:{settings.WS_PORT}/api/auth/github/callback"
    return (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scopes}"
        f"&state={state}"
    )


@router.get("/github/login")
async def github_login() -> RedirectResponse:
    """Redirect user to GitHub OAuth authorization page."""
    if not settings.GITHUB_CLIENT_ID:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/repos?error=github_oauth_not_configured",
            status_code=302,
        )
    state = secrets.token_urlsafe(32)
    _oauth_state_store[state] = ""
    url = _github_login_url(state)
    return RedirectResponse(url=url, status_code=302)


async def _do_github_callback(
    code: str | None,
    state: str | None,
    error: str | None,
    redirect_uri: str,
) -> Response:
    """Shared OAuth callback logic. Uses the actual callback URL for token exchange."""
    frontend_url = settings.FRONTEND_URL
    if error:
        logger.warning("GitHub OAuth error: %s", error)
        return RedirectResponse(
            url=f"{frontend_url}/repos?error={error}",
            status_code=302,
        )
    if not code or not state:
        return RedirectResponse(
            url=f"{frontend_url}/repos?error=missing_params",
            status_code=302,
        )
    if state not in _oauth_state_store:
        return RedirectResponse(
            url=f"{frontend_url}/repos?error=invalid_state",
            status_code=302,
        )
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
    data = resp.json()
    token = data.get("access_token")
    if not token:
        logger.error("No access token in GitHub response: %s", data)
        return RedirectResponse(
            url=f"{frontend_url}/repos?error=token_exchange_failed",
            status_code=302,
        )

    del _oauth_state_store[state]

    response = RedirectResponse(url=f"{frontend_url}/repos", status_code=302)
    response.set_cookie(
        key="github_token",
        value=token,
        max_age=AUTH_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/github/callback")
async def github_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> Response:
    """Handle GitHub OAuth callback at /api/auth/github/callback."""
    redirect_uri = str(request.url).split("?")[0]
    return await _do_github_callback(code, state, error, redirect_uri)


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    """Clear auth cookie. Frontend should redirect after calling this."""
    response.delete_cookie(key="github_token", path="/")
    return {"status": "ok"}


@router.get("/me")
async def get_me(token: str | None = Depends(get_github_token)) -> dict[str, Any]:
    """Return current user info if authenticated."""
    if not token:
        return {"authenticated": False, "user": None}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
        if resp.status_code != 200:
            return {"authenticated": False, "user": None}
        user = resp.json()
        return {
            "authenticated": True,
            "user": {
                "login": user.get("login"),
                "name": user.get("name"),
                "avatar_url": user.get("avatar_url"),
            },
        }
    except Exception as e:
        logger.warning("Failed to fetch GitHub user: %s", e)
        return {"authenticated": False, "user": None}


@router.get("/github/repos")
async def list_github_repos(
    token: str | None = Depends(get_github_token),
) -> dict[str, Any]:
    """List repositories the authenticated user has access to."""
    if not token:
        return {"repos": [], "error": "Not authenticated"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.github.com/user/repos?per_page=100&sort=updated",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
        if resp.status_code != 200:
            return {"repos": [], "error": f"GitHub API error: {resp.status_code}"}
        data = resp.json()
        repos = [
            {
                "id": r.get("id"),
                "full_name": r.get("full_name"),
                "owner": (r.get("owner") or {}).get("login", ""),
                "name": r.get("name"),
                "private": r.get("private", False),
                "html_url": r.get("html_url"),
            }
            for r in data
        ]
        return {"repos": repos}
    except Exception as e:
        logger.warning("Failed to fetch GitHub repos: %s", e)
        return {"repos": [], "error": str(e)}
