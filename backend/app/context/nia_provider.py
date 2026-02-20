"""
backend/app/context/nia_provider.py — MCP Context Integration.

Provides the NiaContextProvider which connects to the Nia MCP server
to fetch robust repository context, falling back to a lightweight local AST parser
and mock data when the MCP server is disabled.
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
from typing import Any

import httpx

from backend.app.config import Settings
from shared.mocks.mock_context import mock_get_context
from shared.schemas import ContextPayload

logger = logging.getLogger(__name__)


class NiaContextProvider:
    """Provides repository context utilizing the Nia MCP server or fallback."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.use_nia = settings.USE_NIA_MCP
        self.mcp_url = settings.NIA_MCP_URL
        
        if self.use_nia:
            # We configure a persistent async client for MCP requests
            self.client = httpx.AsyncClient(base_url=self.mcp_url, timeout=10.0)
        else:
            self.client = None

    async def _call_mcp_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Helper to invoke an MCP tool via the HTTP wrapper."""
        if not self.use_nia or not self.client:
            return None
            
        try:
            # Assuming standard JSON-RPC or REST wrapper for MCP tools
            response = await self.client.post(
                "/tools/execute", # standard route for tool invocation
                json={"name": tool_name, "arguments": arguments}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"Failed to call MCP tool '{tool_name}': {e}")
            return None

    async def get_context(self, task: str, repo_path: str = ".") -> ContextPayload:
        """Fetch context from Nia MCP or fallback to local parsing."""
        try:
            if self.use_nia:
                return await self._get_mcp_context(task, repo_path)
            else:
                return await self._get_fallback_context(task, repo_path)
        except Exception as e:
            logger.error(f"Uncaught exception in get_context: {e}")
            # Ensure we NEVER crash the task due to context failure
            return ContextPayload(
                architectural_context="Context extraction failed. Proceed without architectural guidance.",
                dependencies=[],
                relevant_skills=[],
                business_requirements=[],
            )

    async def _get_mcp_context(self, task: str, repo_path: str) -> ContextPayload:
        """Call the MCP server's search_codebase, get_dependencies, and get_architecture."""
        try:
            # 1. search_codebase
            search_res = await self._call_mcp_tool("search_codebase", {"query": task, "path": repo_path})
            # 2. get_dependencies
            deps_res = await self._call_mcp_tool("get_dependencies", {"path": repo_path})
            # 3. get_architecture
            arch_res = await self._call_mcp_tool("get_architecture", {"path": repo_path})
            
            # Extract basic mock payload or empty items to merge into
            base_payload = mock_get_context(task, repo_path)
            
            # Overwrite with actual MCP results if available
            if arch_res and "architecture" in arch_res:
                base_payload.architectural_context = str(arch_res["architecture"])
            elif search_res:
                base_payload.architectural_context = f"MCP search results: {json.dumps(search_res)[:500]}"
                
            if deps_res and "dependencies" in deps_res:
                base_payload.dependencies = deps_res["dependencies"]
                
            return base_payload
            
        except Exception as e:
            logger.error(f"Error communicating with Nia MCP: {e}")
            return await self._get_fallback_context(task, repo_path)

    async def _get_fallback_context(self, task: str, repo_path: str) -> ContextPayload:
        """Walk the repo directory and parse imports to build a simplified map."""
        base_payload = mock_get_context(task, repo_path)
        
        try:
            logger.info("Nia MCP disabled or failed. Using fallback AST dependency parsing.")
            
            python_imports: set[str] = set()
            js_imports: set[str] = set()
            files_scanned = 0
            
            # Simple regex for TS/JS imports
            js_import_pattern = re.compile(r"import\s+.*?\s+from\s+['\"](.*?)['\"]", re.IGNORECASE)
            js_require_pattern = re.compile(r"require\(['\"](.*?)['\"]\)", re.IGNORECASE)

            # Walk the repository looking for .py, .ts, .tsx, .js files
            for root, dirs, files in os.walk(repo_path):
                # Ignore common virtual envs and node_modules
                dirs[:] = [d for d in dirs if d not in (".git", ".venv", "venv", "node_modules", "dist", ".next")]
                
                for file in files:
                    if files_scanned > 200: # Fast guardrail
                        break
                        
                    path = os.path.join(root, file)
                    
                    if file.endswith(".py"):
                        try:
                            with open(path, "r", encoding="utf-8") as f:
                                tree = ast.parse(f.read())
                            for node in ast.walk(tree):
                                if isinstance(node, ast.Import):
                                    for alias in node.names:
                                        python_imports.add(alias.name.split(".")[0])
                                elif isinstance(node, ast.ImportFrom) and node.module:
                                    python_imports.add(node.module.split(".")[0])
                            files_scanned += 1
                        except Exception:
                            pass
                            
                    elif file.endswith((".js", ".jsx", ".ts", ".tsx")):
                        try:
                            with open(path, "r", encoding="utf-8") as f:
                                content = f.read()
                            
                            for match in js_import_pattern.finditer(content):
                                # naive module name extraction
                                module = match.group(1)
                                if not module.startswith("."):
                                    js_imports.add(module.split("/")[0])
                                    
                            for match in js_require_pattern.finditer(content):
                                module = match.group(1)
                                if not module.startswith("."):
                                    js_imports.add(module.split("/")[0])
                                    
                            files_scanned += 1
                        except Exception:
                            pass
                            
                if files_scanned > 200:
                    break
                    
            extracted_deps = sorted(list(python_imports | js_imports))
            
            if extracted_deps:
                base_payload.dependencies = list(set(base_payload.dependencies + extracted_deps))
                blurb = f"Fallback context extracted {len(extracted_deps)} core dependencies via AST parsing. Files scanned: {files_scanned}."
                base_payload.architectural_context = blurb + "\n\n" + base_payload.architectural_context

            return base_payload

        except Exception as e:
            logger.error(f"Fallback AST parsing failed: {e}")
            return base_payload

    async def refresh_index(self, repo_path: str = ".") -> None:
        """Trigger a re-index of the repository in the Nia server."""
        if not self.use_nia or not self.client:
            return
            
        try:
            await self.client.post("/tools/execute", json={
                "name": "refresh_index",
                "arguments": {"path": repo_path}
            })
            logger.info("Successfully requested Nia MCP index refresh.")
        except Exception as e:
            logger.warning(f"Failed to refresh Nia index: {e}")
