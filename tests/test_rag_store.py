import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from parley.policies.loader import load_policies
from parley.rag.chunking import ChunkStrategy, chunk_corpus
from parley.rag.models import Chunk
from parley.rag.store import index_chunks, load_chunks, load_embeddings, save_embeddings
from parley.rag.tables import ChunkEmbeddingRow, ChunkRow
from parley.seed.config import SeedConfig
from parley.seed.runner import seed_database

SECTION = ChunkStrategy.SECTION


@pytest.fixture
def chunks() -> list[Chunk]:
    return chunk_corpus(load_policies(), SECTION)[:6]


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_index_and_load_round_trip_in_order(session: Session, chunks: list[Chunk]) -> None:
    index_chunks(session, SECTION, chunks)
    assert load_chunks(session, SECTION) == chunks


def test_reindexing_replaces_chunks_and_drops_their_embeddings(
    session: Session, chunks: list[Chunk]
) -> None:
    index_chunks(session, SECTION, chunks)
    save_embeddings(session, SECTION, "m", {c.chunk_id: [1.0, 0.0] for c in chunks})
    index_chunks(session, SECTION, chunks[:2])
    assert len(load_chunks(session, SECTION)) == 2
    assert count(session, ChunkEmbeddingRow) == 0


def test_strategies_are_stored_independently(session: Session, chunks: list[Chunk]) -> None:
    index_chunks(session, SECTION, chunks)
    whole = chunk_corpus(load_policies(), ChunkStrategy.DOCUMENT)[:3]
    index_chunks(session, ChunkStrategy.DOCUMENT, whole)
    index_chunks(session, SECTION, chunks[:1])
    assert len(load_chunks(session, ChunkStrategy.DOCUMENT)) == 3
    assert len(load_chunks(session, SECTION)) == 1


def test_embeddings_are_kept_per_model_with_different_dimensions(
    session: Session, chunks: list[Chunk]
) -> None:
    index_chunks(session, SECTION, chunks)
    save_embeddings(session, SECTION, "small", {c.chunk_id: [1.0, 2.0] for c in chunks})
    save_embeddings(session, SECTION, "large", {c.chunk_id: [1.0, 2.0, 3.0] for c in chunks})
    assert len(load_embeddings(session, SECTION, "small")[chunks[0].chunk_id]) == 2
    assert len(load_embeddings(session, SECTION, "large")[chunks[0].chunk_id]) == 3


def test_saving_embeddings_again_replaces_the_previous_ones(
    session: Session, chunks: list[Chunk]
) -> None:
    index_chunks(session, SECTION, chunks)
    save_embeddings(session, SECTION, "m", {c.chunk_id: [1.0, 0.0] for c in chunks})
    save_embeddings(session, SECTION, "m", {c.chunk_id: [0.0, 1.0] for c in chunks})
    loaded = load_embeddings(session, SECTION, "m")
    assert len(loaded) == len(chunks)
    assert loaded[chunks[0].chunk_id] == [0.0, 1.0]


def test_embeddings_for_unknown_chunks_are_rejected(session: Session, chunks: list[Chunk]) -> None:
    index_chunks(session, SECTION, chunks)
    with pytest.raises(KeyError):
        save_embeddings(session, SECTION, "m", {"nope#0": [1.0]})


def test_seeding_the_world_leaves_the_index_alone(session: Session, chunks: list[Chunk]) -> None:
    index_chunks(session, SECTION, chunks)
    seed_database(session, SeedConfig(n_customers=5))
    assert count(session, ChunkRow) == len(chunks)
