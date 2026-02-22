"""
backend/app/knowledge/router.py — Knowledge-base upload & listing.

Mounted at ``/api/knowledge`` in ``main.py``. Provides endpoints for
uploading documents into the context layer, listing, searching, and
deleting indexed docs.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from backend.app.config import settings
from backend.app.context.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)

router = APIRouter()

# Instantiate the KnowledgeBase singleton for the router
knowledge_base = KnowledgeBase(settings)


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)) -> dict[str, str]:
    """Upload a document to be indexed into the knowledge base.

    Args:
        file: The uploaded PDF file.

    Returns:
        ``{"doc_id": "...", "status": "indexed"}``
    """
    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are currently supported")

    content = await file.read()
    
    try:
        doc_id = await knowledge_base.ingest_document(file.filename, content)
        return {"doc_id": doc_id, "status": "indexed"}
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents")
async def list_documents() -> list[dict[str, Any]]:
    """List all documents currently indexed in the knowledge base.

    Returns:
        List of document metadata dicts.
    """
    try:
        return await knowledge_base.list_documents()
    except Exception as e:
        logger.error(f"List documents failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str) -> dict[str, str]:
    """Delete a document from the knowledge base."""
    await knowledge_base.delete_document(doc_id)
    return {"status": "deleted", "doc_id": doc_id}


class SearchQuery(BaseModel):
    """Request body for knowledge base search."""

    query: str = Field(..., description="Natural-language search query.")
    top_k: int = Field(5, ge=1, le=50, description="Number of results to return.")


@router.post("/search")
async def search_knowledge(body: SearchQuery) -> dict[str, Any]:
    """Search the knowledge base with a natural-language query.

    Returns:
        ``{"results": [...], "count": N}``
    """
    try:
        results = await knowledge_base.search_knowledge(body.query, body.top_k)
        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Knowledge search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ChatMessage(BaseModel):
    """Request body for knowledge base chat."""

    message: str = Field(..., description="User's question about the uploaded PDFs.")
    top_k: int = Field(8, ge=1, le=20, description="Number of relevant chunks to use as context.")
    repo_id: str | None = Field(None, description="Optional repo ID to include PR context. Uses first connected repo if omitted.")


def _format_pr_summary(pr: dict) -> str:
    """Format a PR into a concise text block for context."""
    num = pr.get("number", "?")
    title = pr.get("title", "")
    state = pr.get("state", "unknown")
    author = (pr.get("user") or {}).get("login", "unknown")
    body = (pr.get("body") or "")[:800]
    created = pr.get("created_at", "")
    merged = pr.get("merged_at")
    return (
        f"PR #{num}: {title}\n"
        f"  State: {state} | Author: {author} | Created: {created}"
        + (f" | Merged: {merged}" if merged else "")
        + f"\n  Description: {body}\n"
    )


@router.post("/chat")
async def chat_with_documents(request: Request, body: ChatMessage) -> dict[str, Any]:
    """Chat with the knowledge base. Answers questions using uploaded PDF content
    and context from open/closed PRs of the linked repository.
    """
    try:
        context_parts: list[str] = []

        # 1. Search for relevant context from uploaded PDFs
        chunks = await knowledge_base.search_knowledge(body.message, top_k=body.top_k)
        if chunks:
            context_parts.append(
                "## Context from uploaded documents\n\n"
                + "\n\n---\n\n".join(chunks[: body.top_k])
            )

        # 2. Add PR context from linked repo
        repo_manager = request.app.state.repo_manager
        repos = await repo_manager.list_repos()
        repo_id = body.repo_id
        if not repo_id and repos:
            repo_id = repos[0].id
        if repo_id and repos:
            try:
                all_prs = await repo_manager.get_all_prs(repo_id)
                if all_prs:
                    pr_summaries = [_format_pr_summary(pr) for pr in all_prs[:50]]
                    context_parts.append(
                        "## Pull requests (open and closed) from linked repository\n\n"
                        + "\n".join(pr_summaries)
                    )
            except Exception as e:
                logger.warning("Could not fetch PRs for chat context: %s", e)

        if not context_parts:
            return {
                "response": (
                    "No context available. Please upload PDFs and/or connect a repository "
                    "on the Repositories page to enable questions about your documents and PRs."
                ),
                "sources_used": 0,
            }

        full_context = "\n\n".join(context_parts)
        system_prompt = (
            "You are a helpful assistant that answers questions based on the provided context. "
            "The context may include: (1) excerpts from uploaded PDF documents, and (2) summaries "
            "of pull requests (open and closed) from the linked GitHub repository. "
            "Use the context below to answer the user's question. "
            "If the context does not contain enough information, say so clearly. "
            "Do not make up information. Keep answers concise and accurate.\n\n"
            f"{full_context}"
        )
        user_message = body.message

        claude = request.app.state.claude_client
        result = await claude.complete(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=2048,
            temperature=0.2,
        )
        return {
            "response": result.get("text", ""),
            "sources_used": len(chunks) if chunks else 0,
        }
    except Exception as e:
        logger.error(f"Knowledge chat failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

