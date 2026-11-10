from parley.rag.bm25 import BM25Index, tokenize

TEXTS = [
    "Physical items can be returned within 30 days of delivery.",
    "Customs duties are the customer's responsibility for international parcels.",
    "Annual plans can be refunded within 14 days of the charge date.",
]


def test_tokenize_lowercases_drops_stopwords_and_stems() -> None:
    assert tokenize("The Returns were REFUNDED") == ["return", "were", "refund"]


def test_tokenize_empty_and_stopword_only_text() -> None:
    assert tokenize("") == []
    assert tokenize("the of and") == []


def test_best_match_is_the_chunk_sharing_the_rare_terms() -> None:
    scores = BM25Index(TEXTS).scores("customs duty on international parcel")
    assert scores.index(max(scores)) == 1


def test_stemming_matches_inflected_forms() -> None:
    scores = BM25Index(TEXTS).scores("can I return an item")
    assert scores.index(max(scores)) == 0


def test_query_without_content_words_scores_zero() -> None:
    assert BM25Index(TEXTS).scores("the of") == [0.0, 0.0, 0.0]


def test_empty_chunk_text_does_not_break_the_index() -> None:
    assert len(BM25Index(["", "refund window"]).scores("refund")) == 2
