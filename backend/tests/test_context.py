"""Tests for the context layer: NIA provider, knowledge base, skill synthesis."""
from __future__ import annotations

import pytest

from app.config import Settings
from app.context.knowledge_base import KnowledgeBase
from app.context.nia_provider import NiaContextProvider
from app.context.skill_synthesis import SkillSynthesizer
from shared.schemas import ContextPayload


@pytest.fixture
def settings():
    return Settings(USE_NIA_MCP=False, USE_DATABRICKS=False)


class TestNiaContextProvider:
    @pytest.mark.asyncio
    async def test_get_context_returns_payload(self, settings):
        nia = NiaContextProvider(settings)
        ctx = await nia.get_context("Build a REST API", ".")
        assert isinstance(ctx, ContextPayload)
        assert len(ctx.architectural_context) > 0

    @pytest.mark.asyncio
    async def test_fallback_never_crashes(self, settings):
        """Even with a bogus repo path, get_context returns a minimal payload."""
        nia = NiaContextProvider(settings)
        ctx = await nia.get_context("Do something", "/nonexistent/path")
        assert isinstance(ctx, ContextPayload)
        # Should still have architectural context from mock
        assert len(ctx.architectural_context) > 0

    @pytest.mark.asyncio
    async def test_error_returns_minimal_payload(self, settings):
        """Simulates an exception path — provider should never raise."""
        nia = NiaContextProvider(settings)
        # Force an error by overriding internal method
        async def _boom(*a, **kw):
            raise RuntimeError("boom")
        nia._get_fallback_context = _boom
        nia._get_mcp_context = _boom
        ctx = await nia.get_context("fail me", ".")
        assert isinstance(ctx, ContextPayload)
        assert "failed" in ctx.architectural_context.lower()


class TestKnowledgeBase:
    @pytest.mark.asyncio
    async def test_ingest_and_list(self, settings):
        kb = KnowledgeBase(settings)
        doc_id = await kb.ingest_document("test.txt", b"This is test content about APIs.")
        assert doc_id is not None
        docs = await kb.list_documents()
        assert len(docs) >= 1

    @pytest.mark.asyncio
    async def test_ingest_invalid_pdf_graceful(self, settings):
        kb = KnowledgeBase(settings)
        doc_id = await kb.ingest_document("bad.pdf", b"%PDF-broken content")
        assert doc_id is not None

    @pytest.mark.asyncio
    async def test_search_knowledge(self, settings):
        """Ingest a document and verify search returns relevant chunks."""
        kb = KnowledgeBase(settings)
        await kb.ingest_document(
            "api_guide.txt",
            b"FastAPI is a modern web framework for building APIs with Python. "
            b"It provides automatic documentation and data validation.",
        )
        results = await kb.search_knowledge("FastAPI web framework")
        assert isinstance(results, list)
        assert len(results) >= 1
        assert "FastAPI" in results[0]

    @pytest.mark.asyncio
    async def test_search_empty_kb(self, settings):
        """Search on empty knowledge base returns empty list."""
        kb = KnowledgeBase(settings)
        results = await kb.search_knowledge("anything")
        assert results == []

    @pytest.mark.asyncio
    async def test_delete_document(self, settings):
        """Delete a document and verify it's gone."""
        kb = KnowledgeBase(settings)
        doc_id = await kb.ingest_document("to_delete.txt", b"Delete me later")
        docs_before = await kb.list_documents()
        assert len(docs_before) == 1

        await kb.delete_document(doc_id)
        docs_after = await kb.list_documents()
        assert len(docs_after) == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, settings):
        """Deleting a non-existent doc should not raise."""
        kb = KnowledgeBase(settings)
        await kb.delete_document("nonexistent-id")  # should not raise


class TestSkillSynthesizer:
    @pytest.mark.asyncio
    async def test_store_and_find_skill(self, settings):
        ss = SkillSynthesizer(settings)
        await ss.store_skill("Install deps", ["pip install -r requirements.txt"], True)
        skills = await ss.find_similar_skills("Install npm packages")
        assert isinstance(skills, list)
        assert len(skills) >= 1

    @pytest.mark.asyncio
    async def test_skip_failed_skill(self, settings):
        """Failed tasks should not be stored."""
        ss = SkillSynthesizer(settings)
        await ss.store_skill("Bad task", ["step1"], False)
        assert len(ss._memory_store) == 0

    @pytest.mark.asyncio
    async def test_find_similar_empty_store(self, settings):
        """Empty store returns empty list."""
        ss = SkillSynthesizer(settings)
        skills = await ss.find_similar_skills("anything")
        assert skills == []

    @pytest.mark.asyncio
    async def test_update_skill_success_rate(self, settings):
        """Update success rate and verify the exponential moving average."""
        ss = SkillSynthesizer(settings)
        await ss.store_skill("Build API", ["create endpoint"], True)
        skill_name = ss._memory_store[0][1].name

        # Successive failures should decrease the rate
        await ss.update_skill_success_rate(skill_name, False)
        updated_rate = ss._memory_store[0][1].success_rate
        assert updated_rate < 1.0

        # Success should increase it back
        await ss.update_skill_success_rate(skill_name, True)
        final_rate = ss._memory_store[0][1].success_rate
        assert final_rate > updated_rate

    @pytest.mark.asyncio
    async def test_update_nonexistent_skill(self, settings):
        """Updating a non-existent skill should not raise."""
        ss = SkillSynthesizer(settings)
        await ss.update_skill_success_rate("ghost-skill", True)  # should not raise
