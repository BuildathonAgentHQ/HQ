"""
backend/app/knowledge/router.py — Knowledge-base upload & listing.

Mounted at ``/api/knowledge`` in ``main.py``.  Provides endpoints for
uploading documents into the context layer and listing indexed docs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, UploadFile, File

router = APIRouter()

# In-memory document registry (mock)
_documents: list[dict[str, Any]] = [
    {
        "doc_id": "doc-001",
        "filename": "architecture_overview.md",
        "size_bytes": 4_200,
        "status": "indexed",
        "uploaded_at": "2026-02-20T10:00:00Z",
        "chunk_count": 12,
    },
    {
        "doc_id": "doc-002",
        "filename": "api_conventions.md",
        "size_bytes": 2_800,
        "status": "indexed",
        "uploaded_at": "2026-02-20T10:05:00Z",
        "chunk_count": 8,
    },
    {
        "doc_id": "doc-003",
        "filename": "security_policy.pdf",
        "size_bytes": 15_600,
        "status": "indexed",
        "uploaded_at": "2026-02-20T10:10:00Z",
        "chunk_count": 24,
    },
]


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)) -> dict[str, str]:
    """Upload a document to be indexed into the knowledge base.

    In mock mode, the file content is read and discarded, but a document
    entry is created and stored so it appears in ``list_documents()``.

    Args:
        file: The uploaded file (any format accepted).

    Returns:
        ``{"doc_id": "...", "status": "indexed"}``
    """
    content = await file.read()
    doc_id = f"doc-{uuid.uuid4().hex[:8]}"
    _documents.append({
        "doc_id": doc_id,
        "filename": file.filename or "unknown",
        "size_bytes": len(content),
        "status": "indexed",
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "chunk_count": max(1, len(content) // 500),  # rough mock
    })
    return {"doc_id": doc_id, "status": "indexed"}


@router.get("/documents")
async def list_documents() -> list[dict[str, Any]]:
    """List all documents currently indexed in the knowledge base.

    Returns:
        List of document metadata dicts.
    """
    return _documents
