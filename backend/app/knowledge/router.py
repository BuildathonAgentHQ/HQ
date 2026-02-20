"""
backend/app/knowledge/router.py — Knowledge-base upload & listing.

Mounted at ``/api/knowledge`` in ``main.py``. Provides endpoints for
uploading documents into the context layer and listing indexed docs.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

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
