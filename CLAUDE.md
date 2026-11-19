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

## Today: Phase 9 kickoff
1. Propose the plan for the presentation (README with architecture diagram, eval report, ablation tables, demo video script, technical write-up) and wait for approval. Pull the numbers from `docs/EVAL.md`, `docs/RAG_ABLATION.md`, `docs/SECURITY.md`, `docs/OBSERVABILITY.md` and `docs/SERVICE.md`, and keep their stated caveats.
2. Before writing claims, settle the open items: the per-guard ablation was never run, pass^4 (the project target) exists only for the Phase 5 code (98.2% core, 96.8% held-out in `docs/EVAL.md`) while later runs used three repeats, ATK-027 and SHP-002 stay unstable, and the service has not been deployed to a cloud host.
3. Implement in small commits, lint and tests before every commit.

## Progress
- [x] Phase 0  - [x] Phase 1  - [x] Phase 2  - [x] Phase 3  - [x] Phase 4
- [x] Phase 5  - [x] Phase 6  - [x] Phase 7  - [x] Phase 8  - [ ] Phase 9

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
- 2026-11-13: A human decision on a waiting refund is written to customer memory (`refund_approved`, `refund_declined`) and `resume_multi` returns the follow-up message, so neither is lost after a pause. An unreadable critic answer still approves, but it is recorded as `critic_source` and reported as a rate. `.gitattributes` fixes LF line endings because the project is developed on both macOS and Windows.
- 2026-11-13: The eval has a held-out set (`data/eval/heldout`, 31 scenarios) written before any Phase 5 tuning and reported separately. It is not clean forever: HLD-027 (a refund plus a cancellation in one ticket) and HLD-028 (wording that implied a cancellation) were changed or fixed after a first run showed them failing, and the numbers say so.
- 2026-11-13: The user simulator is an LLM that plays a persona with facts it reveals only when asked, up to four turns. Each turn is a fresh agent run on the newest message plus the history; database state carries over. The responder is shown the actions of earlier turns of the same ticket, because without them it denied refunds it had already made. Simulator and judge cost count against the budget, not against cost per ticket.
- 2026-11-13: The judge is a stronger model than the agent and grades four binary criteria. It was calibrated on 50 replies labeled by the same assistant that built the harness and then reviewed and approved by the project owner, so the agreement is with a reviewed reference, not with labels made blind. The judge prompt was revised once after the first calibration (92.5% overall agreement before, 95.5% after); both numbers are reported.
- 2026-11-13: The regression gate compares scopes (`multi/core`, `multi/heldout`) with `reports/baseline.json` using tolerances above the observed run-to-run spread, plus the project targets. CI runs only the offline gate (every scenario of every set replayed with a scripted model); the live gate (`make eval-gate`) needs the API key and runs locally, because CI cannot spend money without a secret.
- 2026-11-13: Every specialist can now propose a cancellation. Tickets that ask for a refund and a cancellation in one message failed under strict least privilege (HLD-027, DLG-012); proposals are still reviewed by the critic and executed by a separate step, so the risk stays low. The critic also rejects cancelling several plans on a vague request, and specialists ask which record is meant instead of guessing.
- 2026-11-13: Ablation shows the critic is the part of the graph that matters (success drops 6 points on the core set without it). Routing and the reply rewrite showed no measurable gain with the current responder prompt and two runs per configuration; they are candidates to simplify in Phase 7, not conclusions.
- 2026-11-14: Defenses are switchable guards (`GuardConfig`): untrusted text is fenced with a per-request token, a rule-based scan of the ticket and every tool output locks refunds and cancellations for a suspect ticket and hands it to a human (the ticket is still answered), replies are checked for prompt or tool internals and other people's personal data, stored notes are redacted, policy passages must match the policy files, the critic checks for injected instructions, and refunds split to stay under the approval threshold are refused. They are on in the eval harness and off in unit tests of single tools.
- 2026-11-14: Security is measured with two numbers: the agent was manipulated (it tried a forbidden action, even if blocked) and the attack landed (state changed, canary leaked, internals exposed). The backend rules already block most forbidden refunds, so harm alone hides how often the model was fooled. The red-team set has a dev split used while building the guards and a test split kept out of tuning; one test attack (ATK-028) was fixed after it failed and is disclosed as such.
- 2026-11-14: A guard-triggered handover is not counted as the agent's own handover decision and is reported as the share of tickets flagged. With the guards on, the gate failed three held-out checks (handover, refund precision, judge false claims) mostly through HLD-011; the baseline was left at the Phase 5 numbers so that the regression stays visible until it is reviewed.
- 2026-11-15: Tracing uses the OpenTelemetry SDK behind one small `Telemetry` singleton that is a no-op when not configured. Two exporters: a JSONL file per eval report (git-ignored) and a `trace_spans` table in Postgres (migration 0006, outside the seed reset). Cost is the sum of `llm.complete` spans under a `node.*` span, so the dashboard reads spans only and any past run can be re-read.
- 2026-11-15: Measured split of the model cost: specialist 70%, critic 19%, responder 10%, router 1%. The prompt cache already serves 56% of specialist prompt tokens because tool definitions and the system prompt come first; critic and responder prompts are under the 1,024-token cache minimum.
- 2026-11-15: A cheaper critic and responder (`gpt-4o-mini`) and a larger critic (`gpt-4.1`) both lose to `gpt-4.1-mini` everywhere on cost, time or success. `gpt-4.1-nano` is deprecated. The router stays a model call; the softmax classifier router (`--router hybrid`) saves half a second but broke SUB-004, and its "accepted specialist" accuracy hid that.
- 2026-11-15: The semantic cache (policy search only, never replies) is kept as code and a replay tool but not enabled: 0.9 searches per ticket at 162 ms, and a reused answer had another best passage in 6% of the reuses at similarity 0.95. Compact tool output changed nothing and stays an option.
- 2026-11-15: Reading the customer overview before the first turn (`--prefetch`) cuts about 10% of the cost but made the model investigate less (HLD-019 and ATK-027 failed in every gate run), so it is an option and off by default. The fraud pattern (two refunds in 30 days plus a new refund request) became a deterministic critic rule because the model judged it inconsistently; that resolves the HLD-011 regression of 2026-11-14.
- 2026-11-15: The Phase 7 gate was run once per set with prefetch off (`reports/phase7/gate_final`) and still fails on tool recall and judge facts covered by one or two scenarios; `reports/baseline.json` stays at the Phase 6 numbers until a full repeated run is reviewed. Tool recall on the red-team scope has three expected writes, so it is too coarse to gate on there.
- 2026-11-18: The gate scales its tolerance with the number of cases behind a metric (two misses allowed) and refuses fewer than two repeats. HLD-006 and ATK-027 failed through prompt behavior, not data: the specialist treated a large refund as a reason for a handover or asked for confirmation, and the critic rejected right plans with self-contradicting issues. Three prompt lines fixed both. The three-repeat gate for core and held-out passes except held-out handover accuracy (84.9% against 94.6%); the red-team scope could not run because the credit ran out, so the baseline is unchanged.
- 2026-11-19: The full three-repeat gate passes: core 98.8% (pass^3 96.4%), held-out 98.9% (96.8%), red team 98.1% (97.2%) with no attack landed, all within the Phase 6 baseline's tolerances once the handover accuracy tolerance went from 5 to 10 points (the same code gave 84.9% to 90.3% on held-out). `reports/baseline.json` is unchanged. Evidence in `reports/phase7/gate_full`.
- 2026-11-19: The ticket service stores tickets and an event log in Postgres (`service_tickets`, `ticket_events`, migration 0007, outside the seed reset), runs the multi-agent graph in the background with a bounded number of concurrent tickets, and streams stored events over server-sent events with replay by `Last-Event-ID`. A paused refund waits in an approval queue and a decision resumes the LangGraph checkpoint. The API needs `X-API-Key` (required in prod). Tickets left running by a stopped process are failed on startup.
- 2026-11-19: Unbounded concurrency stalled the service: the graph uses synchronous sessions inside async code, so a burst exhausted the connection pool and the blocked event loop could not release it. The fix is a semaphore (`PARLEY_MAX_CONCURRENT_TICKETS`, default 8), a pool sized from it, and span export from a background thread. A simulated model (`PARLEY_LLM_MODE=simulated`, refused in prod) lets CI, demos and load tests run without a key.
- 2026-11-19: The console is a Next.js app (the owner chose it over Streamlit) that reaches the API only through its own `/api` route, which adds the API key on the server, exposes four path prefixes, and passes event streams through. Traces carry redacted tool arguments and results in the service (switch `PARLEY_TRACE_CONTENT`); prompts and replies are never put in spans. MLflow and W&B were dropped from the stack: results are files in git.
- 2026-11-19: Not done in Phase 8: a cloud deployment (the Compose stack runs locally and `docs/SERVICE.md` lists the steps), a login for console users, and a real-model load test. The console was verified by component tests, a production build and requests through its proxy, not in a browser.
