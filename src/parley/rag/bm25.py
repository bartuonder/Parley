import re

from py_rust_stemmers import SnowballStemmer
from rank_bm25 import BM25Okapi

WORD = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "for",
        "from",
        "has",
        "have",
        "i",
        "if",
        "in",
        "is",
        "it",
        "its",
        "my",
        "of",
        "on",
        "or",
        "that",
        "the",
        "their",
        "there",
        "this",
        "to",
        "was",
        "we",
        "what",
        "when",
        "which",
        "will",
        "with",
        "you",
        "your",
    ]
)
_STEMMER = SnowballStemmer("english")


def tokenize(text: str) -> list[str]:
    words = (w for w in WORD.findall(text.lower()) if w not in STOPWORDS)
    return [_STEMMER.stem_word(w) for w in words]


class BM25Index:
    def __init__(self, texts: list[str]) -> None:
        self._bm25 = BM25Okapi([tokenize(t) or ["_"] for t in texts])

    def scores(self, query: str) -> list[float]:
        tokens = tokenize(query)
        if not tokens:
            return [0.0] * len(self._bm25.doc_len)
        return [float(s) for s in self._bm25.get_scores(tokens)]
