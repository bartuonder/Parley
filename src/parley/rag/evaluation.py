import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from parley.policies.models import Region
from parley.rag.filters import SearchFilter, apply_filters
from parley.rag.models import Chunk
from parley.rag.retrieval import Hit, Mode, Retriever
from parley.seed.config import REFERENCE_NOW

DEFAULT_QUESTIONS = Path(__file__).resolve().parents[3] / "data" / "eval" / "retrieval"
REFERENCE_DATE = REFERENCE_NOW.date()
SEARCH_DEPTH = 10
STALE_DEPTH = 5
TEST_REMAINDERS = frozenset({2, 5, 8})


class Gold(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc: str
    evidence: str


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^Q\d{3}$")
    question: str
    as_of: date = REFERENCE_DATE
    region: Region | None = None
    gold: list[Gold] = Field(min_length=1)

    @property
    def split(self) -> str:
        return "test" if int(self.id[1:]) % 10 in TEST_REMAINDERS else "dev"


def load_questions(directory: Path = DEFAULT_QUESTIONS) -> list[Question]:
    questions: list[Question] = []
    for path in sorted(directory.glob("*.yaml")):
        questions += [Question(**item) for item in yaml.safe_load(path.read_text()) or []]
    return questions


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def is_relevant(chunk: Chunk, gold: Gold) -> bool:
    """A chunk answers a gold item when it is from that policy version and holds the evidence."""
    return chunk.doc_key == gold.doc and normalize(gold.evidence) in normalize(chunk.text)


def is_doc_relevant(chunk: Chunk, gold: Gold) -> bool:
    """Granularity-neutral relevance: the chunk comes from the gold policy version."""
    return chunk.doc_key == gold.doc


@dataclass(frozen=True)
class QuestionScore:
    recall_at: dict[int, float]
    reciprocal_rank: float
    stale_rate: float
    doc_recall_at_3: float
    doc_reciprocal_rank: float
    context_words: int


def _reciprocal_rank(hits: list[Hit], question: Question, relevant: Callable[..., bool]) -> float:
    for hit in hits[:SEARCH_DEPTH]:
        if any(relevant(hit.chunk, g) for g in question.gold):
            return 1.0 / hit.rank
    return 0.0


def _recall(hits: list[Hit], question: Question, k: int, relevant: Callable[..., bool]) -> float:
    top = [h.chunk for h in hits[:k]]
    found = sum(any(relevant(c, g) for c in top) for g in question.gold)
    return found / len(question.gold)


def score_question(question: Question, hits: list[Hit], in_force: set[str]) -> QuestionScore:
    top = hits[:STALE_DEPTH]
    stale = sum(h.chunk.doc_key not in in_force for h in top) / len(top) if top else 0.0
    return QuestionScore(
        recall_at={k: _recall(hits, question, k, is_relevant) for k in (1, 3, 5)},
        reciprocal_rank=_reciprocal_rank(hits, question, is_relevant),
        stale_rate=stale,
        doc_recall_at_3=_recall(hits, question, 3, is_doc_relevant),
        doc_reciprocal_rank=_reciprocal_rank(hits, question, is_doc_relevant),
        context_words=sum(len(h.chunk.text.split()) for h in hits[:3]),
    )


class Metrics(BaseModel):
    n: int
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    mrr: float
    stale_rate: float
    doc_recall_at_3: float = 0.0
    doc_mrr: float = 0.0
    context_words: float = 0.0


def aggregate(scores: list[QuestionScore]) -> Metrics:
    n = len(scores)

    def mean(values: list[float]) -> float:
        return sum(values) / n if n else 0.0

    return Metrics(
        n=n,
        recall_at_1=mean([s.recall_at[1] for s in scores]),
        recall_at_3=mean([s.recall_at[3] for s in scores]),
        recall_at_5=mean([s.recall_at[5] for s in scores]),
        mrr=mean([s.reciprocal_rank for s in scores]),
        stale_rate=mean([s.stale_rate for s in scores]),
        doc_recall_at_3=mean([s.doc_recall_at_3 for s in scores]),
        doc_mrr=mean([s.doc_reciprocal_rank for s in scores]),
        context_words=mean([float(s.context_words) for s in scores]),
    )


def evaluate(
    retriever: Retriever,
    questions: list[Question],
    *,
    mode: Mode,
    rerank: bool,
    use_filter: bool = True,
    candidates: int = 20,
) -> Metrics:
    scores = []
    for q in questions:
        filt = SearchFilter(as_of=q.as_of, region=q.region) if use_filter else SearchFilter()
        hits = retriever.search(
            q.question, mode=mode, filt=filt, k=SEARCH_DEPTH, candidates=candidates, rerank=rerank
        )
        in_force = {c.doc_key for c in apply_filters(retriever.chunks, SearchFilter(as_of=q.as_of))}
        scores.append(score_question(q, hits, in_force))
    return aggregate(scores)
