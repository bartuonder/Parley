from enum import StrEnum

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from parley.rag.bm25 import BM25Index
from parley.rag.chunking import ChunkStrategy
from parley.rag.embedders import Embedder
from parley.rag.filters import SearchFilter, apply_filters
from parley.rag.models import Chunk
from parley.rag.rerankers import Reranker
from parley.rag.store import load_chunks
from parley.rag.tables import ChunkEmbeddingRow, ChunkRow

RRF_K = 60


class Mode(StrEnum):
    BM25 = "bm25"
    DENSE = "dense"
    HYBRID = "hybrid"


class Hit(BaseModel):
    chunk: Chunk
    score: float
    rank: int

    @property
    def citation(self) -> str:
        return self.chunk.citation


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    fused: dict[str, float] = {}
    for ranking in rankings:
        for position, item in enumerate(ranking, start=1):
            fused[item] = fused.get(item, 0.0) + 1.0 / (k + position)
    return fused


class Retriever:
    def __init__(
        self,
        session: Session,
        strategy: ChunkStrategy,
        embedder: Embedder,
        reranker: Reranker | None = None,
    ) -> None:
        self.session = session
        self.strategy = strategy
        self.embedder = embedder
        self.reranker = reranker
        self.chunks = load_chunks(session, strategy)
        self._by_id = {c.chunk_id: c for c in self.chunks}
        self._bm25 = BM25Index([c.text for c in self.chunks])
        self._query_vectors: dict[str, list[float]] = {}

    def search(
        self,
        query: str,
        *,
        mode: Mode = Mode.HYBRID,
        filt: SearchFilter | None = None,
        k: int = 5,
        candidates: int = 20,
        rerank: bool = False,
    ) -> list[Hit]:
        if rerank and self.reranker is None:
            raise ValueError("rerank=True needs a reranker")
        allowed = {c.chunk_id for c in apply_filters(self.chunks, filt or SearchFilter())}
        if not allowed:
            return []

        ranked = self._first_stage(query, mode, allowed, candidates)
        if rerank and self.reranker is not None:
            texts = [self._by_id[cid].text for cid, _ in ranked]
            scores = self.reranker.score(query, texts)
            ranked = sorted(
                ((cid, s) for (cid, _), s in zip(ranked, scores, strict=True)),
                key=lambda pair: pair[1],
                reverse=True,
            )
        return [
            Hit(chunk=self._by_id[cid], score=score, rank=rank)
            for rank, (cid, score) in enumerate(ranked[:k], start=1)
        ]

    def _first_stage(
        self, query: str, mode: Mode, allowed: set[str], limit: int
    ) -> list[tuple[str, float]]:
        if mode == Mode.BM25:
            return self._bm25_ranking(query, allowed)[:limit]
        if mode == Mode.DENSE:
            return self._dense_ranking(query, allowed, limit)
        bm25 = self._bm25_ranking(query, allowed)[:limit]
        dense = self._dense_ranking(query, allowed, limit)
        fused = reciprocal_rank_fusion([[c for c, _ in bm25], [c for c, _ in dense]])
        return sorted(fused.items(), key=lambda pair: pair[1], reverse=True)[:limit]

    def _bm25_ranking(self, query: str, allowed: set[str]) -> list[tuple[str, float]]:
        scores = self._bm25.scores(query)
        pairs = [(c.chunk_id, s) for c, s in zip(self.chunks, scores, strict=True) if s > 0]
        return sorted((p for p in pairs if p[0] in allowed), key=lambda p: p[1], reverse=True)

    def _dense_ranking(self, query: str, allowed: set[str], limit: int) -> list[tuple[str, float]]:
        distance = ChunkEmbeddingRow.embedding.cosine_distance(self._query_vector(query))
        stmt = (
            select(ChunkRow.chunk_id, distance)
            .join(ChunkEmbeddingRow, ChunkEmbeddingRow.chunk_pk == ChunkRow.id)
            .where(
                ChunkRow.strategy == self.strategy.value,
                ChunkEmbeddingRow.model == self.embedder.name,
                ChunkRow.chunk_id.in_(allowed),
            )
            .order_by(distance, ChunkRow.id)
            .limit(limit)
        )
        rows = [(cid, 1.0 - float(d)) for cid, d in self.session.execute(stmt)]
        if not rows:
            raise LookupError(f"no embeddings stored for model {self.embedder.name!r}")
        return rows

    def _query_vector(self, query: str) -> list[float]:
        if query not in self._query_vectors:
            self._query_vectors[query] = self.embedder.embed_query(query)
        return self._query_vectors[query]
