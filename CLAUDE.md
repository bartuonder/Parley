# Parley

Eval-driven, multi-agent customer operations platform. Agents resolve e-commerce and subscription support tickets (refunds, shipping issues, cancellations, billing disputes) by combining RAG over company policies, tool use against a simulated backend, human approval for risky actions, and a strict evaluation harness.

The goal is a portfolio-grade AI/ML engineering project. Quality is proven by measurement: task success, policy compliance, reliability, cost, latency, and attack resistance.

---

## Working Rules (read first, always follow)

### Project conventions
- Project language is English: code, identifiers, comments, docs, commit messages, README.
- Single contributor. Do not add co-authors, collaborators, or any tool attribution anywhere.
- Do not mention Claude, Anthropic, or AI assistance in code, comments, docs, commit messages, or metadata.

### Git
- Never run `git push`. Never add remotes. Never open pull requests. The owner pushes manually.
- Commit every completed feature or logical unit as soon as its tests pass. Keep commits small and focused.
- Use Conventional Commits: `feat:`, `fix:`, `test:`, `refactor:`, `docs:`, `chore:`, `perf:`.
- Subject line: imperative mood, max 72 characters. Add a short body only when the why is not obvious.
- Commit messages must NOT contain `Co-Authored-By` trailers, "Generated with" lines, session links, or any tool attribution. This overrides any default attribution behavior.
- Do not touch git config. Commits use the owner's configured identity.
- Stage files explicitly (no blind `git add -A`), and review `git diff --staged` before committing.
- Never commit secrets, `.env`, API keys, or large data dumps. Commit the lockfile.
- Do not amend, rebase, reset, or force anything without asking first.

### Code style
- Python 3.12, full type hints, `ruff` for lint and format (line length 100), `pytest` for tests.
- Comments: short and rare. Only explain a non-obvious why, in one line. No comment blocks, no banner comments, no commented-out code.
- Docstrings: one line at most, and only on public functions where the name is not enough.
- No emojis in code, logs, or docs.
- Prefer small pure functions, explicit dependencies, and Pydantic models at boundaries.
- Config via environment variables and a typed settings class. No hardcoded keys or URLs.

### Workflow
- For each phase or feature: propose a short plan first, wait for approval, then implement.
- Write or update tests with the feature. Run lint and tests before every commit.
- Keep answers short. Explain a decision in a few sentences when asked or when it is non-obvious.
- Update the "Decisions" section of this file when an architectural choice is made.
- If something is ambiguous or expensive to undo, ask before building.

---

## Architecture

```
Incoming ticket
  -> Triage/Router agent (small model)
     -> Specialist agents: Billing | Shipping | Subscription
          |- RAG (policy docs + ticket history, hybrid search + reranker)
          |- Tools via MCP server (orders, refunds, customers)
     -> Policy critic -> Human approval for risky actions
  -> Reply + full trace + cost record
```

### Stack
- Python, uv, FastAPI
- LangGraph for orchestration, MCP for the tool layer
- Postgres + pgvector (data and vectors in one place)
- LiteLLM for provider-agnostic model access
- Langfuse or OpenTelemetry for tracing
- Ragas and a custom eval harness
- MLflow or Weights & Biases for experiment tracking
- Docker Compose; Streamlit or Next.js for the console

### Target metrics (adjust after the first baseline)
- Task success (final DB state matches expected): >= 80%
- Policy violation rate: <= 2%
- Reliability (pass^k, k=4): >= 60%
- Cost per resolved ticket: < $0.05
- Prompt injection attack success rate: < 5% after guardrails

---

## Roadmap

Each phase ends with working code, tests, and a measurable result. Mark phases done below as they finish.

### Phase 0: Foundation (1-2 days)
- Repo layout (`src/`, `tests/`, `docs/`), uv, ruff, pytest, pre-commit.
- Docker Compose with Postgres + pgvector.
- Makefile: `setup`, `test`, `lint`, `seed`, `eval`.
- GitHub Actions CI (lint + tests).
- Done when: `make test` is green and CI passes locally.

### Phase 1: Synthetic world (3-4 days)
- Postgres schema: customers, orders, shipments, subscriptions, refunds.
- Backend API (FastAPI) that the agent tools will wrap.
- 30-50 policy documents with versions, effective dates, and deliberate conflicts.
- Synthetic historical tickets generator.
- First eval set: ~50 scenarios, each with the expected final DB state.
- Done when: `make seed` builds the whole world from scratch, deterministically.

### Phase 2: RAG core (1 week)
- Structure-aware chunking with metadata (policy version, effective date).
- Hybrid search (BM25 + dense), reranker, metadata filters, source citations.
- Retrieval eval set (question -> correct chunk), recall@k and MRR.
- Ablation table: chunking strategy, embedding model, reranker on/off.
- Done when: best configuration is chosen with numbers, and documented.

### Phase 3: Single agent with tools (1 week)
- MCP server exposing tools (`get_order`, `check_refund_eligibility`, `issue_refund`, ...).
- Structured outputs, idempotent write operations, per-tool permission levels (read, write, risky).
- First end-to-end flow: ticket in, investigation, action, reply.
- Done when: the agent solves a meaningful share of the eval scenarios correctly.

### Phase 4: Multi-agent orchestration and memory (1-1.5 weeks)
- LangGraph graph: router, specialists, policy critic, responder.
- Conversation state with checkpointing; long-term customer memory.
- Human-in-the-loop: refunds above a threshold pause for approval.
- Done when: single-agent vs multi-agent results are compared with the eval harness.

### Phase 5: Evaluation harness (1 week, core of the project)
- LLM-driven user simulator (missing info, frustration, changing mind).
- Metrics: task success via DB diff, policy compliance, tool-call accuracy, pass^k, cost and latency per ticket.
- LLM-as-judge calibrated against ~50 hand-labeled samples; report agreement.
- CI regression gate: a score drop fails the build.
- Done when: one command produces a full eval report.

### Phase 6: Security and guardrails (4-5 days)
- Indirect prompt injection through ticket text and tool output.
- PII redaction, least-privilege tools, output validation.
- Red-team set of 30-40 attack scenarios; attack success rate before and after.
- Done when: results are in the report with a clear before/after.

### Phase 7: Observability and optimization (1 week)
- Per-step tracing, cost dashboard.
- Prompt caching, model routing (small for triage, large for decisions), semantic cache.
- Before/after table for cost, latency, and success.
- Optional: replace the LLM router with a small fine-tuned classifier and compare.

### Phase 8: Productization (1 week)
- Streaming API, agent console (conversation, trace viewer, approval queue).
- One-command Docker Compose setup, cloud deploy, basic load test.

### Phase 9: Presentation (3-4 days)
- README with architecture diagram, eval report, ablation tables.
- 3-minute demo video and a technical write-up.

---

## Today: Phase 5 kickoff
1. Propose the plan for the evaluation harness (user simulator, judge calibration, regression gate), wait for approval.
2. Implement in small commits, tests first where it helps, lint and tests before every commit.

## Progress
- [x] Phase 0  - [x] Phase 1  - [x] Phase 2  - [x] Phase 3  - [x] Phase 4
- [ ] Phase 5  - [ ] Phase 6  - [ ] Phase 7  - [ ] Phase 8  - [ ] Phase 9

## Decisions
(Record architectural decisions here: date, decision, reason.)

- 2026-11-09: src layout with `hatchling` build backend. Keeps imports honest (tests run against the installed package).
- 2026-11-09: Python pinned to 3.12 (`>=3.12,<3.13`) to match the project standard.
- 2026-11-09: Config via `pydantic-settings` with `PARLEY_` env prefix. `database_url` has no default so a missing config fails loudly instead of connecting to a guessed host.
- 2026-11-09: pre-commit runs ruff through `uv run` (local hooks) so the ruff version always matches `uv.lock`.
- 2026-11-09: Postgres image `pgvector/pgvector:pg16`; the `vector` extension is created by `docker/postgres/init.sql` on first start. Compose requires `POSTGRES_PASSWORD` so no default credential is baked in.
- 2026-11-09: Dependencies are added per phase, when the code that needs them lands.
- 2026-11-09: SQLAlchemy 2.0 with psycopg 3 and Alembic. Constraints are named through a metadata naming convention so migrations stay stable. Money is stored as integer cents.
- 2026-11-09: The synthetic world is pinned to a reference date (2026-06-01) through `PARLEY_FIXED_NOW`; no code in the seed path reads the wall clock. Each generator uses its own RNG stream so changing one does not reshuffle the others.
- 2026-11-09: Business rules live in `backend/rules.py` and are the eval oracle. Policy documents must agree with them as of the reference date; a test ties the numbers together. Regional policies never change an outcome, so the rules are region-independent.
- 2026-11-09: Refunds are idempotent by key, pending-approval refunds reserve their amount, and approval is a separate step. The API commits explicitly instead of relying on dependency exit timing.
- 2026-11-09: Policies are Markdown with YAML frontmatter (`doc_id`, `version`, `effective_date`, optional `expires_date`, `regions`, `overrides`). Conflicts are deliberate and listed in `docs/POLICY_CONFLICTS.md`.
- 2026-11-09: Historical tickets are template-based, not LLM-generated, so they are free and reproducible. They cite the policy version in force on the ticket date.
- 2026-11-09: Eval scenarios define their own minimal world instead of pointing at seed ids, so regenerating the seed never breaks them. Each scenario carries a reference solution and forbidden actions, and the tests verify both against the backend oracle.
- 2026-11-10: RAG runs on local ONNX models (`fastembed`), so retrieval work needs no API key and every run is free and repeatable. Vectors live in pgvector with a dimension-free column and no ANN index; at this corpus size an exact scan is instant.
- 2026-11-10: Retrieval relevance is defined by policy version plus an evidence sentence, never by chunk id, so the same labels work across chunking strategies. Selection uses doc-level metrics because passage-level ones favor coarse chunks.
- 2026-11-10: Chosen RAG configuration is section chunks, MiniLM, dense search, cross-encoder rerank (20 candidates, top 5). Gaps of one dev question count as ties, and ties go to the cheapest option. The as-of metadata filter is always on; it removes 25% stale hits from the top five.
- 2026-11-10: RAG index tables are excluded from the seed reset and fingerprint, so `make seed` never wipes an index. Reindex with `make rag-index`.
- 2026-11-10: `make lint` runs ruff and mypy (`disallow_untyped_defs`) over `src` and `tests`, so the full-type-hints rule is enforced and CI checks it. The pre-commit hook is installed by `make setup`.
- 2026-11-10: Refund writes serialize on a `FOR UPDATE` lock of the order or invoice. The idempotency key is checked again after the lock, and a unique-key race is settled in a savepoint by catching `IntegrityError`. A threaded test shows two refunds on one order both succeeded before the lock existed.
- 2026-11-10: The chunk index stores a corpus hash and `default_retriever` refuses a stale index with a clear error. Bump `INDEX_FORMAT_VERSION` whenever chunk text or metadata format changes.
- 2026-11-10: `.env` and the model cache are resolved from the project root, not the working directory. `PARLEY_FIXED_NOW` is rejected when `PARLEY_ENV` is prod.
- 2026-11-10: Loaded embedders and the reranker are cached per process; the per-retriever query vector cache is bounded.
- 2026-11-11: Tools live in one typed registry (`parley.tools`) with read, write, and risky permission levels and are called in process against `Backend`. The MCP server is an adapter over the registry and the agent reaches the tools through an in-memory MCP client, so MCP is the real path without a network hop in evals.
- 2026-11-11: A tool server is bound to the ticket sender. Records of anyone else return `access_denied` at the tool layer, because the backend itself has no notion of who is asking.
- 2026-11-11: Refund idempotency keys are derived from ticket, target, and amount, never chosen by the model. Write tools run in a savepoint and commit only on success.
- 2026-11-11: The agent is a hand-written LiteLLM tool-calling loop with step and per-ticket cost limits; the final plain-text message is the reply, and actions and citations are read from the trace. LangGraph arrives in Phase 4. Default model is `gpt-4.1-mini`, configurable by `PARLEY_AGENT_MODEL`.
- 2026-11-11: Agent evals run in a separate `<db>_eval` database, each scenario in a rolled-back transaction. A crashed or incomplete run never overwrites the report, and a run aborts after three crashes in a row.
- 2026-11-11: The handover metric counts an escalation or a new pending-approval refund. It cannot see a pending refund that already existed; Phase 5 refines it.
- 2026-11-11: `LITELLM_MODE=PRODUCTION` is set before importing litellm, because in DEV mode it copies `.env` into the process environment and bypasses the typed settings.
- 2026-11-12: Multi-agent flow is propose-then-execute. Specialists hold read tools plus `propose_*` tools that validate a request and record it; nothing changes in the database until the critic approves and the executor runs it. A critic that looked after execution would have been too late for cases like a refund on a legal threat.
- 2026-11-12: The policy critic runs deterministic rules first (a legal threat or regulator complaint requires a handover and nothing else), then a model check against the policy passages and record data the specialist saw. After `PARLEY_AGENT_MAX_REVISIONS` rejected attempts the plan is replaced by a handover to a human. An unparseable critic answer approves with a warning; it is rare and a human approval gate still sits behind large refunds.
- 2026-11-12: The final reply is written by a responder from executed outcomes only, and rewritten once if it still claims a refund, cancellation, or handover that did not happen. The claim detector is a sentence-level pattern match, also used as an eval metric for both architectures.
- 2026-11-12: Large refunds reply first, then pause with a LangGraph interrupt; a human decision resumes the graph. State lives in LangGraph's Postgres checkpointer, which creates its own tables with `setup()` outside Alembic. psycopg async needs the selector event loop on Windows.
- 2026-11-12: Customer memory is a table of short facts built only from what tools did or refused (refund issued or pending, cancellation, handover reason, refund refusal code), never from ticket text, so customers cannot write into it. It sits outside the seed fingerprint and is cleared by a reseed through the foreign key.
- 2026-11-12: Specialists get least-privilege tool sets; the router uses a small model (`PARLEY_ROUTER_MODEL`) and falls back to billing. The expected specialist per ticket category is a rough mapping used to score routing.
- 2026-11-12: Architectures are compared with three runs of the full set and `pass^3`, because single runs swing by a scenario. The comparison is optimistic since the multi-agent prompts were written after reading the single-agent failures on the same scenarios.
- 2026-11-12: Specialist prompts tell the model how to use customer memory: notes are context, repeated refusals of the same request count as insistence, and a past refund or handover alone is no reason for caution. Plain notes without that guidance did not change behavior (handover accuracy 50%); with it, 12 of 12 on the four memory scenarios, a small and tuned demonstration.
