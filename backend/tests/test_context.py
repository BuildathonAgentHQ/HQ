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


class TestSkillSynthesizer:
    @pytest.mark.asyncio
    async def test_store_and_find_skill(self, settings):
        ss = SkillSynthesizer(settings)
        await ss.store_skill("Install deps", ["pip install -r requirements.txt"], True)
        skills = await ss.find_similar_skills("Install npm packages")
        assert isinstance(skills, list)
        assert len(skills) >= 1
