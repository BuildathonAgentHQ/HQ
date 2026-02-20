"""
backend/app/context/knowledge_base.py — PDF ingestion + vector search.

Handles document ingestion (PDF → text chunks → TF-IDF embeddings) and
semantic search over the knowledge base. In-memory version for the sprint.
"""

from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime, timezone

from PyPDF2 import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from backend.app.config import Settings

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """Manages document ingestion and vector similarity search.

    Attributes:
        documents: In-memory registry of ingested documents mapping doc_id -> info.
        chunks: List of all text chunks across all documents.
        chunk_metadata: Metadata mapping for each chunk index.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        # In-memory document storage: doc_id -> {"filename": str, "chunks": list[str], "metadata": dict}
        self.documents: dict[str, dict] = {}
        
        # In-memory vector search state
        self.chunks: list[str] = []
        self.chunk_metadata: list[dict] = [] # {"doc_id": "...", "chunk_index": int}
        
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.vectors = None
        self._is_fitted = False

    def _rebuild_index(self) -> None:
        """Rebuild the TF-IDF matrix from current chunks."""
        self.chunks = []
        self.chunk_metadata = []
        
        for doc_id, doc_info in self.documents.items():
            for i, chunk in enumerate(doc_info["chunks"]):
                self.chunks.append(chunk)
                self.chunk_metadata.append({"doc_id": doc_id, "chunk_index": i})
                
        if self.chunks:
            self.vectors = self.vectorizer.fit_transform(self.chunks)
            self._is_fitted = True
        else:
            self._is_fitted = False
            self.vectors = None

    async def ingest_document(self, filename: str, file_content: bytes) -> str:
        """Ingest a PDF file into the knowledge base.

        Args:
            filename: Original filename.
            file_content: Raw bytes of the PDF.

        Returns:
            The generated doc_id.
        """
        try:
            reader = PdfReader(io.BytesIO(file_content))
            extracted_text = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    extracted_text.append(text)
                    
            full_text = "\n".join(extracted_text)
            
            # Basic chunking: 500 characters with 50 character overlap
            chunk_size = 500
            overlap = 50
            chunks = []
            
            if not full_text.strip():
                logger.warning(f"No text could be extracted from {filename}")
            else:
                start = 0
                text_len = len(full_text)
                while start < text_len:
                    end = start + chunk_size
                    chunks.append(full_text[start:end])
                    start += (chunk_size - overlap)
                    
            doc_id = str(uuid.uuid4())
            
            self.documents[doc_id] = {
                "filename": filename,
                "chunks": chunks,
                "metadata": {
                    "upload_time": datetime.now(timezone.utc).isoformat(),
                    "chunk_count": len(chunks)
                }
            }
            
            self._rebuild_index()
            logger.info(f"Ingested {filename} (ID: {doc_id}) with {len(chunks)} chunks.")
            
            return doc_id
            
        except Exception as e:
            logger.error(f"Failed to ingest document {filename}: {e}")
            raise Exception(f"Failed to ingest document: {e}")

    async def search_knowledge(self, query: str, top_k: int = 5) -> list[str]:
        """Search the knowledge base with a natural-language query.

        Args:
            query: The search text.
            top_k: Number of results to return.

        Returns:
            List of the most relevant text chunks.
        """
        if not self._is_fitted or not self.chunks:
            return []

        try:
            query_vector = self.vectorizer.transform([query])
            similarities = cosine_similarity(query_vector, self.vectors)[0]
            
            # Get indices of top_k most similar chunks
            top_indices = similarities.argsort()[-top_k:][::-1]
            
            results = []
            for idx in top_indices:
                score = similarities[idx]
                # Optional: exclude low similarity chunks
                if score > 0.05:
                    results.append(self.chunks[idx])
                    
            return results
        except Exception as e:
            logger.error(f"Error during knowledge search: {e}")
            return []

    async def list_documents(self) -> list[dict]:
        """List metadata for all stored documents.

        Returns:
            List of dictionaries with document metadata.
        """
        result = []
        for doc_id, doc_info in self.documents.items():
            meta = doc_info["metadata"].copy()
            meta["id"] = doc_id
            meta["filename"] = doc_info["filename"]
            result.append(meta)
        return result

    async def delete_document(self, doc_id: str) -> None:
        """Remove a document and its chunks from storage.

        Args:
            doc_id: The ID of the document to delete.
        """
        if doc_id in self.documents:
            del self.documents[doc_id]
            self._rebuild_index()
            logger.info(f"Deleted document {doc_id}.")
        else:
            logger.warning(f"Attempted to delete non-existent document {doc_id}.")
