"""
backend/scripts/test_swarm_demo.py — Manual demonstration of the Swarm logic.

Connects to a small public repo, finds a PR, reviews it with Claude,
generates fixes, and prints everything without pushing any changes.

Usage:
    export GITHUB_TOKEN="..."
    export ANTHROPIC_API_KEY="..."
    python -m backend.scripts.test_swarm_demo
"""

import asyncio
import logging
from pprint import pprint

from backend.app.config import settings
from backend.app.claude_client.client import ClaudeClient
from backend.app.control_plane.github_connector import GitHubConnector
from backend.app.repo_manager.manager import RepoManager
from backend.app.claude_client.repo_analyzer import RepoAnalyzer
from backend.app.swarm.orchestrator import SwarmOrchestrator
from backend.app.websocket.events import event_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def run_demo():
    print("🚀 Starting Agent HQ Swarm Demo (Dry Run) 🚀\n")

    # 1. Initialize services
    claude = ClaudeClient(settings)
    github = GitHubConnector(settings)
    repo_manager = RepoManager(settings, github)
    analyzer = RepoAnalyzer(claude, repo_manager)
    orchestrator = SwarmOrchestrator(claude, repo_manager, github, event_router)

    # Use a well-known public repository that usually has open PRs
    demo_owner = "fastapi"
    demo_repo = "fastapi"
    repo_full_name = f"{demo_owner}/{demo_repo}"

    print(f"📦 Connecting to repository: {repo_full_name}...")
    try:
        repo = await repo_manager.add_repo(demo_owner, demo_repo)
        print(f"✅ Connected to: {repo.full_name}")
    except Exception as e:
        print(f"❌ Failed to connect to repo: {e}")
        return

    # 2. Find an open PR
    print("\n🔍 Fetching open PRs...")
    prs = await github.get_open_prs()  # Wait, this uses settings.GITHUB_REPO
    # Let's override github.owner_repo for the demo just to fetch PRs
    # Or just use repo_manager.get_open_prs
    try:
        prs_list = await repo_manager.get_open_prs(repo.id)
        if not prs_list:
            print("❌ No open PRs found. Try another repo.")
            return
    except Exception as e:
        print(f"❌ Failed to fetch PRs: {e}")
        return

    target_pr = prs_list[0]
    pr_number = target_pr["number"]
    print(f"🎯 Selected PR #{pr_number}: {target_pr['title']} by @{target_pr['user']['login']}")

    # 3. Analyze PR
    print(f"\n🧠 Claude analyzing PR #{pr_number}. This might take a minute...")
    try:
        review = await analyzer.analyze_pr(repo.id, pr_number)
        print(f"\n✅ Review Complete:")
        print(f"   Verdict: {review.verdict}")
        print(f"   Risk Level: {review.risk_level}")
        print(f"   Summary: {review.summary}")
        print(f"   Issues Found: {len(review.issues)}")
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return

    if not review.issues:
        print("\n✨ Claude found no issues! Perfect PR.")
        return

    # 4. Swarm Planning
    print("\n🛠️  Planning Fixes...")
    try:
        plan = await orchestrator.plan_fix(repo.id, review.issues, pr_number=pr_number)
        print(f"✅ Plan created with {len(plan.tasks)} tasks.")
        print(f"   Plan ID: {plan.id}")
        for t in plan.tasks:
            print(f"   - Task [{t.agent_type}] depending on {t.dependencies}")
    except Exception as e:
        print(f"❌ Planning failed: {e}")
        return

    # 5. Swarm Execution
    print("\n⚡ Executing Swarm Plan...")
    try:
        # We manually await the plan execution instead of using run_in_background
        await orchestrator.execute_plan(plan.id)
        
        # Note: execute_plan updates the plan object in-place and stores fixes
        print(f"\n✅ Plan Status: {plan.status}")
        
        fixes = [f for f in orchestrator.fix_proposals.values() if f.repo_id == repo.id]
        print(f"💡 Fixes Proposed: {len(fixes)}")
        
        for f in fixes:
            print(f"\n   📄 File: {f.file_path}")
            print(f"   🤖 Agent: {f.agent_type}")
            print(f"   💬 Explanation: {f.explanation}")
            print("   --- [SNIPPET] ---")
            # print the first 5 lines of the diff/fix
            print("\n".join(f.fixed_code.splitlines()[:5]) + "\n   ...")

    except Exception as e:
        print(f"❌ Execution failed: {e}")
        return

    print("\n🎉 Demo completed successfully! Printout of token usage:")
    usage = claude.get_usage_stats()
    pprint(usage)


if __name__ == "__main__":
    asyncio.run(run_demo())
