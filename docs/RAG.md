# RAG core

Retrieval over the policy corpus: structure-aware chunks with version metadata, hybrid search, a reranker, metadata filters, and citations. Full numbers are in `RAG_ABLATION.md`; this page records the design and what the numbers mean.

## Chosen configuration

**Section chunks, MiniLM embeddings, dense search, cross-encoder rerank over 20 candidates, top 5.** These are the defaults in `src/parley/rag/service.py`.

| Split | doc R@3 | doc MRR | passage R@3 | passage MRR | Stale@5 |
| --- | --- | --- | --- | --- | --- |
| dev (70 questions) | 0.99 | 0.93 | 0.97 | 0.87 | 0.00 |
| test (30 questions) | 0.97 | 0.94 | 0.93 | 0.89 | 0.00 |

Use it:

```
make rag-index   # chunk the policies and store vectors in pgvector
make rag-eval    # rerun the full ablation and rewrite RAG_ABLATION.md
```

```python
hits = search_policies(default_retriever(session), question, as_of=date(2026, 6, 1))
format_context(hits)  # numbered passages, each with its citation and effective date
```

## What was built

- **Chunking** (`chunking.py`): fixed windows (40 words, 10 overlap), one chunk per `##` section with the policy title, version, and effective date prepended, or one chunk per policy.
- **Index** (`store.py`, `tables.py`): chunks and per-model vectors in Postgres; dense search is a pgvector cosine query. `make seed` leaves the index alone.
- **Search** (`retrieval.py`): stemmed BM25, dense, or both fused with reciprocal rank fusion, optionally reranked by a cross-encoder.
- **Filters** (`filters.py`): as-of date (drops superseded, future, and expired versions), region, latest version only.
- **Citations**: every hit carries `POL-REF-001@v2 / Return window`.
- **Freshness** (`freshness.py`): the index stores a hash of the policy corpus; `default_retriever` raises `StaleIndexError` if the policies changed since `make rag-index`.
- **Models**: local ONNX through `fastembed`; no API calls. Weights download once into `.cache/models` and are loaded once per process.

## Findings

1. **The metadata filter matters most.** Without it, 25% of the top five hits are superseded, expired, or not yet in force, and doc MRR drops from 0.94 to 0.84. Version traps (the 14, 30, and 21 day return windows, the expired holiday offer) are solved by the filter, not by the model.
2. **The reranker helps consistently.** Averaged over all configurations it adds about 6 points of doc R@3 and 7 of doc MRR.
3. **Embedding model barely matters.** MiniLM, bge-small, and bge-base are within 0.6 points of each other on doc R@3, which is below the noise floor. The smallest one was chosen.
4. **Hybrid did not beat dense here.** Dense 0.968 against hybrid 0.956 doc R@3; BM25 alone is worst at 0.893. With 38 policies and a reranker over 20 candidates the first stage hardly shows. Hybrid is kept in the code because exact terms such as amounts and ids should matter more on a larger corpus.
5. **Fixed windows lose.** They cut sections in half (passage R@3 0.84 against 0.94 for sections).
6. **Section against whole-policy chunks is a tie within noise** on doc metrics (one dev question apart). Sections were chosen because they cite the exact section and use half the context (118 against 232 words for the top three).

## Method and its limits

- Passage relevance first counted a hit only if the chunk held the gold evidence sentence. That favored whole-policy chunks, so selection uses doc-level relevance, which does not depend on chunk size. Passage metrics are still reported.
- A gap of one question (1.4 points on dev, 3.3 on test) is treated as a tie, and ties go to the cheapest option: fewer stale hits, shorter context, smaller model, simpler mode.
- Questions and policies were written by the same author, and the corpus is small, so absolute numbers are optimistic and many configurations saturate near 1.0. Read the factor tables for direction, not for exact gaps.
- Ticket history is not indexed yet. It is better added when the specialist agents need similar past cases.
