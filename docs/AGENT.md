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

## Limits of the numbers

- One run per scenario. Run-to-run variance is not measured yet; `pass^k` comes with Phase 5.
- 55 scenarios, one model, and a customer who never answers back. The user simulator is Phase 5.
- The handover metric cannot see a pending refund that already existed (REF-019 counts as a miss although the reply was right).
- The reply is not graded for wording or facts yet; `reply_facts` is scored in Phase 5.
