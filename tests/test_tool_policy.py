from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from parley.backend.services import Backend
from parley.rag.embedders import HashEmbedder
from parley.rag.rerankers import OverlapReranker
from parley.rag.service import build_default_index, default_retriever
from parley.tools.context import ToolContext
from parley.tools.policy import POLICY_TOOLS
from parley.tools.registry import ToolRegistry
from tests.factories import NOW, make_customer

REGISTRY = ToolRegistry(POLICY_TOOLS)
EMBEDDER = HashEmbedder(256)


@pytest.fixture
def ctx(session: Session) -> ToolContext:
    sender = make_customer(session, "ada@example.com")
    build_default_index(session, embedder=EMBEDDER)
    retriever = default_retriever(session, EMBEDDER, OverlapReranker())
    backend = Backend(session, lambda: NOW + timedelta(days=200))
    return ToolContext(backend, sender.id, "T-1", retriever=retriever)


def test_search_returns_cited_passages_in_force(ctx: ToolContext) -> None:
    result = REGISTRY.call(ctx, "search_policies", {"query": "how many days to return an item"})
    assert result.ok and result.data is not None
    passages = result.data["passages"]
    assert 0 < len(passages) <= 5
    assert all("@v" in p["citation"] and p["text"] for p in passages)


def test_search_without_a_retriever_is_unavailable(ctx: ToolContext) -> None:
    ctx.retriever = None
    result = REGISTRY.call(ctx, "search_policies", {"query": "return window"})
    assert result.error_code == "unavailable"


def test_search_rejects_a_trivial_query(ctx: ToolContext) -> None:
    assert REGISTRY.call(ctx, "search_policies", {"query": "a"}).error_code == "invalid_arguments"
