from datetime import date

from sqlalchemy.orm import Session

from parley.policies.loader import load_policies
from parley.policies.models import PolicyDoc, Region
from parley.rag.chunking import ChunkStrategy
from parley.rag.embedders import Embedder, get_embedder
from parley.rag.filters import SearchFilter
from parley.rag.indexing import build_index
from parley.rag.rerankers import CrossEncoderReranker, Reranker
from parley.rag.retrieval import Hit, Mode, Retriever

DEFAULT_STRATEGY = ChunkStrategy.SECTION
DEFAULT_EMBEDDING = "minilm"
DEFAULT_MODE = Mode.DENSE
DEFAULT_TOP_K = 5
DEFAULT_CANDIDATES = 20


def build_default_index(
    session: Session, docs: list[PolicyDoc] | None = None, embedder: Embedder | None = None
) -> int:
    """Index the policy corpus with the configuration chosen in docs/RAG_ABLATION.md."""
    return build_index(
        session,
        docs if docs is not None else load_policies(),
        DEFAULT_STRATEGY,
        [embedder or get_embedder(DEFAULT_EMBEDDING)],
    )


def default_retriever(
    session: Session, embedder: Embedder | None = None, reranker: Reranker | None = None
) -> Retriever:
    return Retriever(
        session,
        DEFAULT_STRATEGY,
        embedder or get_embedder(DEFAULT_EMBEDDING),
        reranker or CrossEncoderReranker(),
    )


def search_policies(
    retriever: Retriever, query: str, as_of: date, region: Region | None = None
) -> list[Hit]:
    """Policies in force on a date, ranked for a question, with citations on every hit."""
    return retriever.search(
        query,
        mode=DEFAULT_MODE,
        filt=SearchFilter(as_of=as_of, region=region),
        k=DEFAULT_TOP_K,
        candidates=DEFAULT_CANDIDATES,
        rerank=True,
    )
