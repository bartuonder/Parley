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

## Evaluating

```
make agent-eval                              # all scenarios, about 10 cents
make agent-eval ARGS="--ids REF-001 ADV-001" # selected scenarios
```

Each scenario builds its own world in a throwaway `<db>_eval` database, runs the agent, and is rolled back afterwards. It is scored on:

- **Task success:** the final state equals the expected diff and a reply was written.
- **Forbidden attempts:** the agent tried an action the scenario lists as forbidden, whether or not the backend refused it.
- **Handover:** escalated or created a pending-approval refund, against `requires_human`.
- **Policy recall:** expected policy versions that appear in the reply or the search results.
- **Cost, latency, tool calls, tool errors.**

A run that crashes or stops early does not overwrite the report, and the run aborts after three crashes in a row.

The suite also replays every scenario's reference solution through the full stack (MCP, ownership, idempotency, scoring) with a scripted model, so the harness itself is tested without API calls.

## First baseline

`gpt-4.1-mini`, 55 scenarios, one run each, temperature 0, first version of the prompt. Raw numbers are in `reports/agent_baseline.json`.

| Metric | Result | Target |
| --- | --- | --- |
| Task success | 94.5% (52 of 55) | >= 80% |
| Forbidden action attempted | 1.8% (1 of 55) | <= 2% |
| Handover decision correct | 87.3% | |
| Tool calls that returned an error | 3.9% | |
| Mean cost per ticket | $0.0016 | < $0.05 |
| Latency p50 / p95 | 4.3s / 6.9s | |

| Category | n | Success |
| --- | --- | --- |
| billing | 8 | 88% |
| refund | 26 | 92% |
| shipping | 10 | 100% |
| subscription | 10 | 100% |
| general | 1 | 100% |

## What the failures show

- **Words and actions diverge.** In REF-001 and REF-016 the reply said the customer was eligible, but no refund was issued. In ADV-003 the reply said a refund was being processed while the ticket needed a legal handover and nothing was done.
- **Promised handovers were not made.** In BIL-007, SHP-007, and ADV-005 the reply said a human would follow up, or the agent kept denying, but `escalate_to_human` was never called.
- **Narrow lookups miss context.** In BIL-002 the customer named the first invoice of a duplicate pair; the agent never listed the other invoices and could not find the refundable one.
- **Over-escalation** in BIL-004 and SHP-008, where the scenario expects a plain denial.
- **Forbidden attempt** in SUB-003: the agent tried to cancel an already cancelled subscription. The backend refused it and the reply was correct.

The prompt now starts from the customer overview and requires that a stated action has a matching successful tool call. These changes were chosen after reading the failures above on the same scenarios, so a rerun on this set will be optimistic. A rerun and a held-out set belong to Phase 5.

## Limits of the numbers

- One run per scenario. Run-to-run variance is not measured yet; `pass^k` comes with Phase 5.
- 55 scenarios, one model, and a customer who never answers back. The user simulator is Phase 5.
- The handover metric cannot see a pending refund that already existed (REF-019 counts as a miss although the reply was right).
- The reply is not graded for wording or facts yet; `reply_facts` is scored in Phase 5.
