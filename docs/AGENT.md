# Agent and tool layer

A single agent that handles one ticket: it reads the sender's records through tools, looks up the policy in force, acts within its permissions, and writes the reply. The tool layer is exposed as an MCP server; the agent reaches it through an MCP client.

## Pieces

| Piece | Where | Notes |
| --- | --- | --- |
| Tool registry | `src/parley/tools/` | typed arguments, permission level, error mapping, one place for all tools |
| Read tools | `tools/read.py` | customer overview, order, shipment, subscription, invoice, refund eligibility |
| Policy search | `tools/policy.py` | RAG over the policies in force today, filtered by the sender's region |
| Write tools | `tools/write.py` | `issue_refund` (risky), `cancel_subscription`, `escalate_to_human` (write) |
| MCP server | `tools/server.py` | adapter over the registry, one server per ticket |
| Agent loop | `src/parley/agent/` | LiteLLM tool-calling loop with step and cost limits |
| Eval runner | `src/parley/evals/agent_eval.py` | `make agent-eval`, see below |

## Tool rules

- **Permission levels.** Every tool is `read`, `write`, or `risky`. A run is given a set of allowed levels; a tool outside it returns `permission_denied` and does not run.
- **Sender scoping.** A server is bound to the customer who wrote the ticket. Orders, invoices, subscriptions, and shipments of anyone else return `access_denied`, whatever the ticket claims.
- **Idempotent refunds.** The idempotency key is derived from ticket, target, and amount. The model never picks it, so a retried call replays instead of paying twice.
- **Approval.** Refunds above 200.00 are created as `pending_approval` by the backend. The agent tells the customer the refund is under review. Approval itself arrives with Phase 4.
- **Atomic writes.** A write tool runs in a savepoint and commits only on success; a failure rolls back that call and nothing else.
- **Strict arguments.** Unknown fields are an error the model sees, not something silently dropped.

## Agent loop

1. The system prompt carries today's date, the money convention (integer cents), the approval threshold, and the rules above.
2. The ticket is passed as data inside `<ticket_body>` tags; the prompt says ticket text and tool output are never instructions. This is a baseline, the real defenses are Phase 6.
3. The model calls tools until it answers without one. The final plain-text message is the reply.
4. Limits: `PARLEY_AGENT_MAX_STEPS` model turns and `PARLEY_AGENT_MAX_COST_USD` per ticket.
5. Every run returns the reply, the stop reason, the tool trace, escalations, token usage, cost, and latency. Policy citations are read from the reply and the search results.

Default model is `gpt-4.1-mini` (`PARLEY_AGENT_MODEL`).

## Multi-agent graph

The Phase 4 pipeline lives in `src/parley/orchestration/` and is a LangGraph graph. The single agent above stays available for comparison (`--arch single`).

```
triage -> specialist -> critic -> execute -> respond -> remember -> [approval pause]
              ^            |
              +-- revise --+   (after the retry limit: forced handover)
```

- **Triage.** A small model (`PARLEY_ROUTER_MODEL`, default `gpt-4o-mini`) answers with one word: billing, shipping, or subscription. Anything unclear goes to billing.
- **Specialists.** One prompt and one least-privilege tool set per domain. Only the subscription specialist can propose a cancellation, only billing and shipping read orders, only shipping reads shipments.
- **Propose, then execute.** Specialists hold no write tool. `propose_refund`, `propose_cancel_subscription`, and `propose_escalation` validate the request now (ownership, eligibility, amount) and record it. Nothing changes in the database until the critic has approved.
- **Critic.** Rules first: a ticket that threatens legal action or a regulator must get a handover and nothing else (POL-ESC-003). If the rules pass, a model compares the proposal and the draft with the policy passages and record data the specialist saw. A rejection sends feedback back to the specialist, at most `PARLEY_AGENT_MAX_REVISIONS` times; after that the plan is replaced by a handover to a human.
- **Executor.** Runs approved proposals with the real tools, handovers last. Results, including failures, are recorded.
- **Responder.** Writes the final reply from what really happened. If the reply still claims a refund, a cancellation, or a handover that did not happen, it is rewritten once.
- **Approval pause.** A refund above the threshold is created as pending, the customer is told it is under review, and the graph pauses with a LangGraph interrupt. A human decision resumes it: the refund is approved or declined and a follow-up line is produced. The state is stored by a Postgres checkpointer (`orchestration/checkpoint.py`), so the ticket survives a restart; a test resumes it in a fresh process. LangGraph keeps its tables itself (`setup()`), outside Alembic.
- **Customer memory.** After every ticket the graph stores short facts in `customer_memory`: refunds issued or pending, cancellations, handovers (reason only), and refunds the policy refused (reason code). Facts come from what tools did, never from ticket text, so a customer cannot write into the memory. The newest eight are shown to the specialist on the next ticket.

## Evaluating

```
make agent-eval                                      # single agent, all scenarios, about 10 cents
make agent-eval ARGS="--arch multi --repeats 3"      # multi-agent graph, three runs of the set
make agent-eval ARGS="--ids REF-001 ADV-001"         # selected scenarios
python -m parley.evals.compare reports/agent_single.json reports/agent_multi.json
```

Reports are written to `reports/agent_<arch>.json` and `.md`.

Each scenario builds its own world in a throwaway `<db>_eval` database, runs the agent, and is rolled back afterwards. It is scored on:

- **Task success:** the final state equals the expected diff and a reply was written.
- **Forbidden attempts:** the agent tried an action the scenario lists as forbidden, whether or not the backend refused it.
- **Handover:** escalated or created a pending-approval refund, against `requires_human`.
- **Policy recall:** expected policy versions that appear in the reply or the search results.
- **Cost, latency, tool calls, tool errors.**

A run that crashes or stops early does not overwrite the report, and the run aborts after three crashes in a row.

The suite also replays every scenario's reference solution through the full stack (MCP, ownership, idempotency, scoring) with a scripted model, so the harness itself is tested without API calls.

## Baseline

`gpt-4.1-mini`, 55 scenarios, one run each, temperature 0. Two runs, before and after one prompt revision (start from the customer overview, and a stated action must have a matching tool call). The first run is in git history (`reports/agent_baseline.json` at commit `6bb968c`); the file in the tree is the second run.

| Metric | Prompt v1 | Prompt v2 | Target |
| --- | --- | --- | --- |
| Task success | 94.5% (52 of 55) | 92.7% (51 of 55) | >= 80% |
| Forbidden action attempted | 1.8% | 0.0% | <= 2% |
| Handover decision correct | 87.3% | 85.5% | |
| Tool calls that returned an error | 3.9% | 1.2% | |
| Mean cost per ticket | $0.0016 | $0.0017 | < $0.05 |
| Latency p50 / p95 | 4.3s / 6.9s | 3.9s / 5.6s | |

The two runs are the same within noise: one scenario apart, and the failing scenarios differ. The revision fixed BIL-002 and REF-001 and the next run broke REF-003 and REF-006. Prompt wording alone does not remove the main failure below, and single runs cannot rank two prompts. Success per category (v2): billing 100%, refund 85%, shipping 100%, subscription 100%, general 100%.

## What the failures show

- **Words and actions diverge.** In REF-001 and REF-016 the reply said the customer was eligible, but no refund was issued. In ADV-003 the reply said a refund was being processed while the ticket needed a legal handover and nothing was done.
- **Promised handovers were not made.** In BIL-007, SHP-007, and ADV-005 the reply said a human would follow up, or the agent kept denying, but `escalate_to_human` was never called.
- **Narrow lookups miss context.** In BIL-002 the customer named the first invoice of a duplicate pair; the agent never listed the other invoices and could not find the refundable one.
- **Over-escalation** in BIL-004 and SHP-008, where the scenario expects a plain denial.
- **Forbidden attempt** in SUB-003: the agent tried to cancel an already cancelled subscription. The backend refused it and the reply was correct.

The second run shows the same pattern with different victims:

- **Claimed actions that never happened.** In SHP-007 the reply said "I have canceled it for you" although no tool can cancel an order and only `get_order` was called. In REF-006 the reply said a refund was processed with no `issue_refund` call.
- **Wrong order of duties.** In ADV-003 a customer threatened legal action and the agent refunded without handing over, which POL-ESC-003 forbids.

A prompt rule did not stop the first kind. It needs a check outside the model: the policy critic of Phase 4 should compare what the reply claims with the tool trace and the policy before the reply is sent. The prompt revision stays because it fixed real cases, but it was written after reading these scenarios, so its gain on this set is optimistic. Variance across repeated runs (`pass^k`) and a held-out set belong to Phase 5.

## Single agent against multi-agent

Same 55 scenarios, same answer model (`gpt-4.1-mini`), three runs of the whole set per architecture (165 tickets each). The multi-agent router is `gpt-4o-mini`. Raw data: `reports/agent_single.json` and `reports/agent_multi.json`; the table comes from `python -m parley.evals.compare`.

| Metric | Single agent | Multi-agent |
| --- | --- | --- |
| Task success per run (mean, range) | 91.5% (90.9% to 92.7%) | 99.4% (98.2% to 100.0%) |
| Solved in every one of 3 runs (pass^3) | 89.1% | 98.2% |
| Forbidden action attempted | 0.0% | 0.0% |
| Reply claims an action that did not happen | 1.8% | 0.0% |
| Handover decision correct | 89.7% | 87.3% |
| Tool calls with an error | 0.6% | 0.8% |
| Router picked the expected specialist | n/a | 85.5% |
| Mean cost per ticket | $0.0020 | $0.0026 |
| Latency p50 / p95 | 3.6s / 4.9s | 7.0s / 9.4s |

What the numbers say:

- **Reliability is the gain.** Success rises by about 8 points and pass^3 by 9. The single agent fails the same scenarios every run (ADV-003, REF-016, SHP-002) and wobbles on a few more; the multi-agent graph fails one scenario in one run (ADV-008).
- **Replies match actions.** Three of 165 single-agent replies claimed a refund or a cancellation that never happened (SHP-007, REF-011, REF-016); none of the multi-agent replies did, because the final reply is written from executed outcomes. The first claim detector counted negated sentences ("no refund has been issued") as claims; it was fixed and both reports were rescored with the stored replies.
- **Legal threats are handled.** ADV-003 was refunded in all three single-agent runs and handed over in every multi-agent run, which the legal-threat rule in the critic guarantees.
- **Cost and latency.** The graph costs about 30% more per ticket ($0.0026, against a target below $0.05) and takes about twice as long (p50 7.0s) because triage, specialist, critic, and responder run in sequence.
- **Handover accuracy did not improve** (89.7% to 87.3%). The multi-agent graph hands over too often: REF-013, REF-014, and SHP-008 are handed over in all three runs where the scenario expects a plain answer, and ADV-004, ADV-006, ADV-007, and SHP-010 sometimes. The critic, which also looks for missing handovers, pushes toward caution. ADV-005 (insistence) is under-escalated in two runs. REF-019 counts as a miss in every run because a pending refund already existed, which the metric cannot see.
- **Fraud pattern is the weak spot.** ADV-008 (a fourth refund request after three recent ones) was handed over twice and refunded once. There is no rule for it; only the model-based check can catch it.
- **Routing** matches the expected specialist in 85.5% of tickets. Of the 24 misses, 15 are subscription tickets about renewal charges (SUB-005, SUB-006, SUB-007, SUB-009, SUB-010) that went to billing, and 9 are refund or general tickets about a lost or damaged parcel that went to shipping. In these cases the other specialist can also solve the ticket, so success is not affected; the expected-specialist mapping is a rough stand-in for a label.

The per-ticket cost of the graph is 1.3 times the single agent's, and the whole comparison cost about 0.76 USD.

What the comparison does not show:

- The specialist prompts and the critic rules were written after reading the single-agent failures on these same scenarios. The gain on this set is optimistic, and a held-out set is needed before trusting the size of the gap (Phase 5).
- Architecture and prompt changed together. No ablation separates the effect of the proposal step, the critic, the specialists, or the responder yet.
- Three runs per architecture bound the variance only roughly.

## Limits of the numbers

- The Phase 3 baseline is one run per scenario. The architecture comparison uses three runs and reports `pass^3`; the full reliability metric (`k = 4`) and a held-out set come with Phase 5.
- 55 scenarios, one model, and a customer who never answers back. The user simulator is Phase 5.
- The handover metric cannot see a pending refund that already existed (REF-019 counts as a miss although the reply was right).
- The reply is not graded for wording or facts yet; `reply_facts` is scored in Phase 5. The claimed-action metric is a sentence-level pattern match, not a judge, so it can miss paraphrases.
