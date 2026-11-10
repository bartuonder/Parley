import hashlib

from sqlalchemy.orm import Session

from parley.policies.models import PolicyDoc
from parley.rag.chunking import ChunkStrategy
from parley.rag.store import stored_corpus_hashes

INDEX_FORMAT_VERSION = 1


class StaleIndexError(RuntimeError):
    pass


def corpus_hash(docs: list[PolicyDoc]) -> str:
    """Fingerprint of the policy corpus and the index format; changes whenever either does."""
    digest = hashlib.sha256(f"format:{INDEX_FORMAT_VERSION}".encode())
    for doc in sorted(docs, key=lambda d: d.key):
        digest.update(doc.model_dump_json().encode())
    return digest.hexdigest()


def assert_index_fresh(session: Session, strategy: ChunkStrategy, docs: list[PolicyDoc]) -> None:
    stored = stored_corpus_hashes(session, strategy)
    if not stored:
        raise StaleIndexError(f"no {strategy.value} index found; run `make rag-index`")
    if stored != {corpus_hash(docs)}:
        raise StaleIndexError(
            f"the {strategy.value} index was built from a different policy corpus; "
            "run `make rag-index`"
        )
