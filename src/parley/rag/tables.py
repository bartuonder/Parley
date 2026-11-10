from datetime import date

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from parley.db.base import Base
from parley.db.models import enum_col
from parley.policies.models import PolicyCategory

INDEX_TABLES = frozenset({"chunks", "chunk_embeddings"})


class ChunkRow(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy: Mapped[str] = mapped_column(String(16))
    chunk_id: Mapped[str] = mapped_column(String(120))
    doc_id: Mapped[str] = mapped_column(String(20))
    version: Mapped[int]
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[PolicyCategory] = mapped_column(enum_col(PolicyCategory))
    regions: Mapped[list[str]] = mapped_column(JSONB)
    effective_date: Mapped[date] = mapped_column(Date)
    expires_date: Mapped[date | None] = mapped_column(Date)
    section: Mapped[str | None] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    corpus_hash: Mapped[str] = mapped_column(String(64))

    __table_args__ = (UniqueConstraint("strategy", "chunk_id", name="uq_chunks_strategy_chunk"),)


class ChunkEmbeddingRow(Base):
    __tablename__ = "chunk_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True)
    chunk_pk: Mapped[int] = mapped_column(ForeignKey("chunks.id", ondelete="CASCADE"), index=True)
    model: Mapped[str] = mapped_column(String(100))
    embedding: Mapped[list[float]] = mapped_column(Vector())

    __table_args__ = (
        UniqueConstraint("chunk_pk", "model", name="uq_chunk_embeddings_chunk_model"),
    )
