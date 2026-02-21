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
            # Configure persistent async client with auth header for Nia MCP.
            # The Nia API at https://apigcp.trynia.ai/mcp uses Bearer token auth.
            headers: dict[str, str] = {"Content-Type": "application/json"}
            
            # Prefer env var NIA_API_KEY, fall back to mcp.json
            self._api_key = settings.NIA_API_KEY or self._load_api_key()
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            
            self.client = httpx.AsyncClient(
                base_url=self.mcp_url,
                timeout=15.0,
                headers=headers,
            )
        else:
            self.client = None

    @staticmethod
    def _load_api_key() -> str:
        """Try to load the Nia API key from .agent_hq/mcp.json."""
        try:
            mcp_path = os.path.join(".", ".agent_hq", "mcp.json")
            if os.path.exists(mcp_path):
                with open(mcp_path, "r") as f:
                    config = json.load(f)
                servers = config.get("mcpServers", {})
                nia_cfg = servers.get("nia", servers.get("nia-context", {}))
                auth = nia_cfg.get("headers", {}).get("Authorization", "")
                if auth.startswith("Bearer "):
                    return auth[7:]
        except Exception:
            pass
        return ""

    async def _call_mcp_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Invoke an MCP tool via JSON-RPC over HTTP.
        
        Nia MCP tools (per https://docs.trynia.ai/tools-features):
          - search: semantic search across repos/docs
          - index: index repos, docs, research papers, local folders
          - nia_read: read file content from indexed sources
          - nia_grep: regex search in indexed sources
          - nia_explore: browse file structure (tree/ls)
          - nia_research: AI research with quick/deep/oracle modes
          - nia_advisor: analyze code against documentation
          - context: cross-agent context sharing
        """
        if not self.use_nia or not self.client:
            return None
            
        try:
            # MCP uses JSON-RPC 2.0 format
            response = await self.client.post(
                "",  # POST to the base MCP URL itself
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments,
                    },
                    "id": 1,
                },
            )
            response.raise_for_status()
            result = response.json()
            
            # JSON-RPC returns {"result": ...} or {"error": ...}
            if "error" in result:
                logger.warning(f"MCP tool '{tool_name}' returned error: {result['error']}")
                return None
            return result.get("result")
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
        """Call Nia's real MCP tools: search, nia_explore, get_dependencies, get_architecture.
        
        Nia tool reference:
          - search(query, repositories?, search_mode?) -> semantic code search
          - nia_explore(source_type, source_identifier, action?) -> file tree
          - get_dependencies(file_path) -> dependency graph
          - get_architecture() -> high-level module structure
        """
        try:
            # 1. Semantic search using Nia's `search` tool
            search_res = await self._call_mcp_tool("search", {
                "query": task,
                "search_mode": "unified",
                "include_sources": True,
            })
            
            # 2. Explore repo structure using Nia's `nia_explore` tool
            explore_res = await self._call_mcp_tool("nia_explore", {
                "source_type": "repository",
                "source_identifier": repo_path,
                "action": "tree",
            })
            
            # 3. Get dependency graph for the most relevant files
            dep_res = None
            if search_res and isinstance(search_res, list) and len(search_res) > 0:
                # Use the first result's file path for dependency lookup
                top_file = search_res[0].get("file_path", "") if isinstance(search_res[0], dict) else ""
                if top_file:
                    dep_res = await self._call_mcp_tool("get_dependencies", {
                        "file_path": top_file,
                    })
            
            # 4. Get high-level architecture summary
            arch_res = await self._call_mcp_tool("get_architecture", {})
            
            # Start with mock as base and enrich with real data
            base_payload = mock_get_context(task, repo_path)
            
            # Overwrite with actual MCP results if available
            if arch_res:
                arch_summary = json.dumps(arch_res)[:600] if isinstance(arch_res, (dict, list)) else str(arch_res)[:600]
                base_payload.architectural_context = (
                    f"Architecture from Nia:\n{arch_summary}\n\n"
                    + base_payload.architectural_context
                )
            
            if explore_res:
                base_payload.architectural_context = (
                    f"Repository structure from Nia:\n{json.dumps(explore_res)[:800]}\n\n"
                    + base_payload.architectural_context
                )
            
            if search_res:
                # Extract dependency/file info from search results
                search_summary = json.dumps(search_res)[:500] if isinstance(search_res, (dict, list)) else str(search_res)[:500]
                base_payload.architectural_context = (
                    f"Relevant code context:\n{search_summary}\n\n"
                    + base_payload.architectural_context
                )
            
            if dep_res:
                dep_list = dep_res if isinstance(dep_res, list) else [str(dep_res)]
                base_payload.dependencies = list(set(base_payload.dependencies + dep_list))
                
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
            js_import_pattern = re.compile(r"import\s+.*?\s+from\s+['\"](.+?)['\"]", re.IGNORECASE)
            js_require_pattern = re.compile(r"require\(['\"](.+?)['\"]\)", re.IGNORECASE)

            # Walk the repository looking for .py, .ts, .tsx, .js files
            for root, dirs, files in os.walk(repo_path):
                # Ignore common virtual envs and node_modules
                dirs[:] = [d for d in dirs if d not in (".git", ".venv", "venv", "node_modules", "dist", ".next")]
                
                for file in files:
                    if files_scanned > 200:  # Fast guardrail
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
        """Trigger a re-index of the repository in the Nia server.
        
        Uses Nia's `index` tool which auto-detects source type.
        """
        if not self.use_nia or not self.client:
            return
            
        try:
            await self._call_mcp_tool("index", {
                "folder_path": os.path.abspath(repo_path),
                "resource_type": "local_folder",
            })
            logger.info("Successfully requested Nia MCP index refresh.")
        except Exception as e:
            logger.warning(f"Failed to refresh Nia index: {e}")
