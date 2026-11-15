# Observability and optimization

Phase 7 makes the cost and the time of a ticket visible, then spends that knowledge. This page explains the tracing, the dashboard, and each optimization with its measurement. Results are in the last section.

## Tracing

Every eval scenario is one trace. The spans use the OpenTelemetry SDK, so any OpenTelemetry exporter can be attached; two are built in.

| Span | Kind | What it carries |
| --- | --- | --- |
| `scenario` | scenario | scenario id, architecture, ticket category, whether the guards were on, success, cost, guard events |
| `ticket` | ticket | one agent run on a ticket (a dialogue has one per turn) |
| `node.<name>` | node | one step of the multi-agent graph: triage, investigate, critic, handover, execute, respond, remember, approval |
| `llm.complete` | llm | model, number of messages, prompt, completion and cached tokens, cost in USD, number of tool calls |
| `tool.<name>` | tool | tool name, whether it succeeded, error code |
| `rag.search` | rag | whether the answer came from the semantic cache |
| `router.classifier` | router | the label and the confidence when the classifier routed the ticket |

A model call belongs to the step of the nearest `node.*` span above it, so the cost of the critic is the sum of the `llm.complete` spans under `node.critic`. Tracing costs nothing when it is not configured.

Exporters (`observability/exporters.py`): `JsonlExporter` writes one JSON line per span (the eval command writes `reports/<name>/traces/<report>.jsonl` next to every report, ignored by git, switched off with `--no-trace`), and `PostgresExporter` stores spans in the `trace_spans` table (migration 0006) on its own connection, so a rolled-back eval transaction does not erase them. The table is outside the seed reset.

Token counts and cost come from the provider response; `cached_tokens` is the part of the prompt the provider served from its prompt cache.

## Dashboard

`make dashboard TRACES=reports/phase7/traces/baseline_multi_core.jsonl` builds one self-contained page, `reports/dashboard.html`, and prints the cost table. It shows the model cost per pipeline step, per model and per ticket category (calls, tokens, cache share, cost, share of the total, p50 and p95 per call), the time per graph node, and the tool calls. It reads the span file only, so any past run can be re-read.

## Model per role

The router, the specialists, the critic and the responder each take their own model: `--router-model`, `--model`, `--critic-model` and `--responder-model` in the eval command. A model that is not set falls back to the agent model (the router to `PARLEY_ROUTER_MODEL`).

## Classifier router

`orchestration/classifier.py` replaces the router's model call with softmax regression over the ticket's MiniLM embedding. It is trained on synthetic historical tickets rendered from the seed templates (`python -m parley.orchestration.train_router`, model in `data/models/router.json`) and never sees an eval scenario, so the eval sets test it. Below a confidence threshold it hands the ticket to the model router (`--router hybrid`); `--router classifier` never does.

## Semantic cache

`rag/cache.py` answers a policy question from an earlier, close enough question (cosine similarity above a threshold) within the same date, region and search options, so a policy in force on another day is never reused. It caches policy search only: a reply or a plan could carry one customer's data to another. `python -m parley.rag.cache_replay <reports...>` replays the questions an eval run asked and reports how often a cache would reuse an answer and how often the reused answer was not the same as a fresh search.

## Compact tool output

`--compact` leaves empty fields out of the JSON a tool returns to the model.

## Results

All runs are the multi-agent graph on `gpt-4.1-mini` with the guards on. The cost of a ticket is the model cost only. Each experiment is one run of the core and held-out sets (86 tickets); a single run moves by one or two scenarios, so success differences of a point or two are noise.

### Where the money and the time went

Baseline, 86 tickets (`reports/phase7/dashboard_baseline.html`):

| Step | Model calls | Prompt tokens | Cached | Cost | Share | p50 per call |
| --- | --- | --- | --- | --- | --- | --- |
| specialist (investigate) | 338 | 676,937 | 56% | $0.1853 | 70% | 0.8s |
| critic | 90 | 118,664 | 0% | $0.0493 | 19% | 0.7s |
| responder | 87 | 42,486 | 0% | $0.0263 | 10% | 1.0s |
| router (triage) | 86 | 22,893 | 0% | $0.0035 | 1% | 0.5s |

A ticket takes about 5.9s: the specialist loop 3.6s (4 model calls on average), the responder 1.0s, the critic 0.7s, the router 0.5s. Tools take milliseconds, except the policy search at 170 ms. The critic and the responder are not cached because their prompts are shorter than the 1,024 tokens a provider caches; the specialist loop already gets 56% from the prompt cache without any change, because the tool definitions and the system prompt come first and are the same for every ticket of a specialist (a test keeps that prefix stable).

### What was tried

| Experiment | Success | Handover | Cost / ticket | p50 | Calls / ticket | Prompt tokens / ticket |
| --- | --- | --- | --- | --- | --- | --- |
| Baseline (Phase 6 code) | 98.8% | 93.0% | $0.0031 | 5.9s | 6.99 | 10,011 |
| Classifier router with model fallback | 98.8% | 89.5% | $0.0033 | 5.7s | 6.53 | 10,731 |
| Compact tool output | 98.8% | 93.0% | $0.0031 | 6.2s | 7.08 | 10,104 |
| Overview read before the first turn | 96.5% | 94.2% | $0.0028 | 5.4s | 6.29 | 8,708 |
| Baseline plus the refund pattern rule | 98.8% | 93.0% | $0.0030 | 6.1s | 7.02 | 10,006 |
| Prefetch plus the refund pattern rule | 98.8% | 90.7% | $0.0029 | 5.5s | 6.41 | 8,969 |
| Critic on `gpt-4.1` (plus the rule) | 96.5% | 96.5% | $0.0062 | 6.0s | 7.59 | 11,221 |
| Critic and responder on `gpt-4o-mini` | 70.9% | 39.5% | $0.0049 | 11.9s | 11.76 | 19,151 |

- **A cheaper critic and responder does not pay.** `gpt-4.1-nano` is deprecated; on `gpt-4o-mini` the critic rejected plans so often (179 critic calls against 90) that cost, time and failures all rose. The "small model for triage, large for decisions" idea held for the first half only.
- **A larger critic does not pay either.** `gpt-4.1` for the critic doubled the cost per ticket, with no gain in success (the handover correctness moved by one scenario).
- **The classifier router saves a model call and half a second, but it hurt the cancellation flows.** It was 100% right by the "accepted specialist" measure on all 104 eval tickets, yet a subscription ticket routed to billing was answered with an offer instead of a cancellation (SUB-004). The accepted-specialist measure is too generous to show that. The classifier stays as an option (`--router hybrid`).
- **Compact tool output changed nothing** (10,104 against 10,011 prompt tokens): tool results hardly contain empty fields. It stays an option (`--compact`).
- **Reading the customer overview before the first turn** removes the model call that every ticket made first (6.99 to 6.41 model calls). With the original prompt it cost quality: both fraud-pattern scenarios were refunded, because the model investigated less. Two changes fixed that: the refund pattern became a critic rule (two refunds in the last 30 days and a new refund request go to a human, POL-ESC-002), and the specialist prompt now says the overview is already in the conversation and asks for every item of an order to be checked. The first run with the original prompt and the hybrid router had failed REF-006, DLG-001, DLG-006 and ATK-004; with the new prompt and the model router the dialogue set was back at 100%.
- **The semantic cache is not worth switching on.** The agent asked 87 policy questions over 100 tickets (0.9 per ticket) and a fresh search takes 162 ms, under 3% of a ticket. Replaying the questions with a cache: at similarity 0.95 it reuses 21% of them and the reused answer has a different best passage in 6% of the reuses (14% at 0.9, 26% at 0.8). A saving of about 30 ms per ticket against a wrong passage now and then is a bad trade. The code and the replay tool stay.

### Before and after

The shipped change is the prefetched overview with its prompt, plus the refund pattern rule (`reports/phase7/before_after.md`, one run per set):

| Set | Success | Handover | Cost per ticket | p50 latency | Model calls per ticket | Prompt tokens per ticket |
| --- | --- | --- | --- | --- | --- | --- |
| core (55) | 98.2% to 98.2% | 92.7% to 94.5% | $0.0029 to $0.0025 (-14%) | 5.9s to 5.3s (-11%) | 6.82 to 6.02 | 9,586 to 8,052 |
| held-out (31) | 100% to 96.8% | 93.5% to 93.5% | $0.0033 to $0.0030 (-10%) | 5.8s to 5.6s (-3%) | 7.29 to 6.45 | 10,765 to 9,129 |
| dialogue (14) | 100% to 100% | 100% to 92.9% | $0.0086 to $0.0084 (-2%) | 14.9s to 10.7s (-28%) | 18.29 to 16.86 | 26,800 to 25,618 |
| red team (36) | 100% to 97.2% | 100% to 100% | $0.0040 to $0.0038 (-6%) | 6.3s to 6.0s (-6%) | 8.75 to 7.75 | 12,653 to 11,403 |

No attack landed before or after. The success differences are one scenario each (HLD-004 and ATK-027 in the "after" runs); HLD-004 and SHP-002 also fail in some baseline runs. The saving is real but modest: about 10% of the cost and about 10% to 25% of the time, mostly from one model call fewer per ticket. The two largest remaining costs are the specialist loop itself (about 70%) and the critic (about 19%), and the experiments above show that cheaper models are not an easy way to cut either.

### The held-out regression from Phase 6

With the guards on, the held-out set had failed three gate checks, mostly through HLD-011 (the fraud pattern). The cause was not a guard: the model alone judged that pattern differently from run to run. It is now a critic rule, and HLD-011 and ADV-008 pass in every run since.

### Limits

- One run per experiment; the differences of one scenario are noise.
- The tracing records model calls and tools, not the time spent inside the graph outside them; the node spans give that.
- The cost is the provider's price list through LiteLLM; a prompt cache hit is priced as the provider prices it.
- Latency is wall-clock time with a network call to the provider and varies with its load.
