"""
shared/mocks/mock_github.py — Mock GitHub REST API v3 responses.

Provides functions that return sample PR data, diffs, commit histories,
and coverage reports structured to match the GitHub REST API v3 response
format.  Used by the control-plane module during development.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

_now = datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════════════════
#  Pull Requests — matches GET /repos/{owner}/{repo}/pulls
# ═══════════════════════════════════════════════════════════════════════════════


def get_sample_prs() -> list[dict[str, Any]]:
    """Return a list of mock PR objects matching GitHub API v3 format.

    Each dict mirrors the shape returned by
    ``GET /repos/{owner}/{repo}/pulls``.
    """
    return [
        {
            "number": 101,
            "title": "feat: add OAuth2 provider support",
            "user": {"login": "alice", "avatar_url": "https://avatars.githubusercontent.com/u/1?v=4"},
            "state": "open",
            "html_url": "https://github.com/acme/agent-hq/pull/101",
            "created_at": (_now - timedelta(days=2)).isoformat(),
            "updated_at": (_now - timedelta(hours=3)).isoformat(),
            "labels": [{"name": "feature"}, {"name": "auth"}],
            "requested_reviewers": [{"login": "bob"}, {"login": "charlie"}],
            "draft": False,
        },
        {
            "number": 102,
            "title": "fix: patch SQL injection vulnerability",
            "user": {"login": "bob", "avatar_url": "https://avatars.githubusercontent.com/u/2?v=4"},
            "state": "open",
            "html_url": "https://github.com/acme/agent-hq/pull/102",
            "created_at": (_now - timedelta(hours=6)).isoformat(),
            "updated_at": (_now - timedelta(hours=1)).isoformat(),
            "labels": [{"name": "security"}, {"name": "urgent"}],
            "requested_reviewers": [{"login": "alice"}],
            "draft": False,
        },
        {
            "number": 103,
            "title": "chore: update eslint and prettier configs",
            "user": {"login": "dependabot[bot]", "avatar_url": "https://avatars.githubusercontent.com/in/29110?v=4"},
            "state": "open",
            "html_url": "https://github.com/acme/agent-hq/pull/103",
            "created_at": (_now - timedelta(days=1)).isoformat(),
            "updated_at": (_now - timedelta(days=1)).isoformat(),
            "labels": [{"name": "dependencies"}],
            "requested_reviewers": [],
            "draft": False,
        },
    ]


# ═══════════════════════════════════════════════════════════════════════════════
#  PR Files — matches GET /repos/{owner}/{repo}/pulls/{pr_number}/files
# ═══════════════════════════════════════════════════════════════════════════════


def get_sample_pr_files(pr_number: int) -> list[dict[str, Any]]:
    """Return mock file-change data for a PR.

    Args:
        pr_number: The PR number to generate files for.

    Returns:
        List of dicts matching the GitHub API ``/pulls/{n}/files`` response.
    """
    base_files: dict[int, list[dict[str, Any]]] = {
        101: [
            {"filename": "backend/app/auth/oauth.py", "status": "added", "additions": 120, "deletions": 0, "changes": 120, "patch": "@@ -0,0 +1,120 @@\n+class OAuthProvider:..."},
            {"filename": "backend/app/auth/models.py", "status": "modified", "additions": 35, "deletions": 5, "changes": 40, "patch": "@@ -10,5 +10,35 @@\n+class OAuthToken(BaseModel):..."},
            {"filename": "tests/test_oauth.py", "status": "added", "additions": 85, "deletions": 0, "changes": 85, "patch": "@@ -0,0 +1,85 @@\n+def test_oauth_flow():..."},
        ],
        102: [
            {"filename": "backend/app/api/search.py", "status": "modified", "additions": 10, "deletions": 5, "changes": 15, "patch": "@@ -42,5 +42,10 @@\n-query = f\"SELECT * WHERE name = '{name}'\"...\n+query = \"SELECT * WHERE name = %s\"..."},
            {"filename": "tests/test_search.py", "status": "modified", "additions": 20, "deletions": 3, "changes": 23, "patch": "@@ -15,3 +15,20 @@\n+def test_sql_injection_prevention():..."},
        ],
        103: [
            {"filename": ".eslintrc.js", "status": "modified", "additions": 15, "deletions": 10, "changes": 25, "patch": "@@ -1,10 +1,15 @@..."},
            {"filename": ".prettierrc", "status": "modified", "additions": 3, "deletions": 2, "changes": 5, "patch": "@@ -1,2 +1,3 @@..."},
        ],
    }
    return base_files.get(pr_number, [
        {"filename": "README.md", "status": "modified", "additions": 5, "deletions": 2, "changes": 7, "patch": "@@ -1,2 +1,5 @@..."},
    ])


# ═══════════════════════════════════════════════════════════════════════════════
#  Commits — matches GET /repos/{owner}/{repo}/commits
# ═══════════════════════════════════════════════════════════════════════════════


def get_sample_commits(limit: int = 10) -> list[dict[str, Any]]:
    """Return a list of mock commit objects.

    Args:
        limit: Maximum number of commits to return.
    """
    commits = []
    messages = [
        "feat: add OAuth2 provider support",
        "fix: patch SQL injection in search endpoint",
        "test: add auth integration tests",
        "refactor: extract db connection pool",
        "docs: update API documentation",
        "chore: bump fastapi to 0.129.0",
        "fix: resolve circular import in auth module",
        "feat: add WebSocket heartbeat",
        "test: fix flaky login timeout test",
        "style: run ruff format on backend",
    ]
    for i, msg in enumerate(messages[:limit]):
        commits.append({
            "sha": f"abc{i:04d}" + "0" * 32,
            "commit": {
                "message": msg,
                "author": {
                    "name": ["alice", "bob", "charlie"][i % 3],
                    "date": (_now - timedelta(hours=i * 4)).isoformat(),
                },
            },
            "author": {"login": ["alice", "bob", "charlie"][i % 3]},
        })
    return commits


# ═══════════════════════════════════════════════════════════════════════════════
#  CI Status — matches GET /repos/{owner}/{repo}/commits/{ref}/status
# ═══════════════════════════════════════════════════════════════════════════════


def get_sample_ci_status(ref: str = "main") -> dict[str, Any]:
    """Return a mock combined CI status.

    Args:
        ref: Git ref (branch or SHA).
    """
    return {
        "state": "success",
        "total_count": 4,
        "statuses": [
            {"context": "ci/lint", "state": "success", "description": "Ruff passed"},
            {"context": "ci/test-backend", "state": "success", "description": "42 tests passed"},
            {"context": "ci/test-frontend", "state": "success", "description": "All 28 tests passed"},
            {"context": "ci/build", "state": "success", "description": "Docker image built"},
        ],
        "sha": "abc000" + "0" * 34,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  Coverage — mock coverage.json (e.g., from pytest-cov)
# ═══════════════════════════════════════════════════════════════════════════════


def get_sample_coverage_json() -> dict[str, Any]:
    """Return a mock coverage report in JSON format (pytest-cov style)."""
    return {
        "totals": {"covered_lines": 1490, "num_statements": 2000, "percent_covered": 74.5},
        "files": {
            "backend/app/orchestrator/router.py": {"summary": {"covered_lines": 45, "num_statements": 55, "percent_covered": 81.8}},
            "backend/app/engine/runner.py": {"summary": {"covered_lines": 60, "num_statements": 94, "percent_covered": 63.8}},
            "backend/app/guardrails/janitor.py": {"summary": {"covered_lines": 88, "num_statements": 97, "percent_covered": 90.7}},
            "backend/app/websocket/manager.py": {"summary": {"covered_lines": 70, "num_statements": 80, "percent_covered": 87.5}},
            "shared/schemas.py": {"summary": {"covered_lines": 190, "num_statements": 200, "percent_covered": 95.0}},
        },
    }
