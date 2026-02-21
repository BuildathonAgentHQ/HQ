import re

with open("backend/app/swarm/router.py", "r") as f:
    code = f.read()

# Fix imports
code = code.replace("from fastapi import APIRouter, HTTPException, Query\n", "from fastapi import APIRouter, HTTPException, Query, Request\n")

# Remove _init function and globals
init_block = """# ── Module-level singletons (lazy-initialised on first request) ──────────────

_orchestrator: Optional[SwarmOrchestrator] = None
_repo_analyzer: Optional[RepoAnalyzer] = None


def _init() -> tuple[SwarmOrchestrator, RepoAnalyzer]:
    \"\"\"Ensure singletons are created (called once, lazily).\"\"\"
    global _orchestrator, _repo_analyzer
    if _orchestrator is None:
        claude = ClaudeClient(settings)
        github = GitHubConnector(settings)
        repo_mgr = RepoManager(settings, github)
        _orchestrator = SwarmOrchestrator(claude, repo_mgr, github, event_router)
        _repo_analyzer = RepoAnalyzer(claude, repo_mgr)
    assert _orchestrator is not None
    assert _repo_analyzer is not None
    return _orchestrator, _repo_analyzer
"""
code = code.replace(init_block, "")

# Replace create_plan
code = code.replace("async def create_plan(body: CreatePlanRequest) -> dict[str, Any]:", "async def create_plan(request: Request, body: CreatePlanRequest) -> dict[str, Any]:")
code = code.replace("    orchestrator, analyzer = _init()", "    orchestrator = request.app.state.swarm_orchestrator\n    analyzer = request.app.state.repo_analyzer")

# Replace list_plans
code = code.replace("async def list_plans() -> list[dict[str, Any]]:", "async def list_plans(request: Request) -> list[dict[str, Any]]:")

# Replace get_plan
code = code.replace("async def get_plan(plan_id: str) -> dict[str, Any]:", "async def get_plan(request: Request, plan_id: str) -> dict[str, Any]:")

# Replace execute_plan
code = code.replace("async def execute_plan(plan_id: str) -> dict[str, Any]:", "async def execute_plan(request: Request, plan_id: str) -> dict[str, Any]:")

# Replace get_fixes
code = code.replace("async def get_fixes(plan_id: str) -> list[dict[str, Any]]:", "async def get_fixes(request: Request, plan_id: str) -> list[dict[str, Any]]:")

# Replace apply_fixes
code = code.replace("async def apply_fixes(plan_id: str, body: ApplyFixesRequest) -> dict[str, Any]:", "async def apply_fixes(request: Request, plan_id: str, body: ApplyFixesRequest) -> dict[str, Any]:")

# Replace apply_all_fixes
code = code.replace("async def apply_all_fixes(plan_id: str) -> dict[str, Any]:", "async def apply_all_fixes(request: Request, plan_id: str) -> dict[str, Any]:")

# Replace get_all_issues
code = code.replace("async def get_all_issues(", "async def get_all_issues(\n    request: Request,")

# Replace update_issue
code = code.replace("async def update_issue(issue_id: str, body: UpdateIssueRequest) -> dict[str, Any]:", "async def update_issue(request: Request, issue_id: str, body: UpdateIssueRequest) -> dict[str, Any]:")

# Replace all forms of _init()
code = code.replace("orchestrator, _ = _init()", "orchestrator = request.app.state.swarm_orchestrator")
code = code.replace("_, analyzer = _init()", "analyzer = request.app.state.repo_analyzer")

with open("backend/app/swarm/router.py", "w") as f:
    f.write(code)

print("Done")
