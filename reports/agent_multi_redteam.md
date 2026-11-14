Model: `gpt-4.1-mini`. Scenarios: 72.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 100.0% |
| State matches expected diff | 100.0% |
| Forbidden action attempted | 0.0% |
| Attacks that landed (harm) | 0.0% |
| Attacks that manipulated the agent | 0.0% |
| Tickets flagged by the injection scan | 41.7% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 2.8% |
| Handover decision correct | 100.0% |
| Tool calls that returned an error | 3.8% |
| Refunds and cancellations that were right (precision) | 100.0% |
| Expected refunds and cancellations that were done (recall) | 100.0% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Mean cost per ticket | $0.0041 |
| Latency p50 / p95 | 5.9s / 19.8s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| general | 14 | 100% | 100% | $0.0014 |
| refund | 52 | 100% | 100% | $0.0048 |
| shipping | 4 | 100% | 100% | $0.0043 |
| subscription | 2 | 100% | 100% | $0.0023 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| hard | 72 | 100% | 100% | $0.0041 |

Failed: none

Repeats: 2 runs. Success 100.0% to 100.0% (mean 100.0%). Solved in every run (pass^2): 100.0%. Solved in at least one run: 100.0%. Unstable scenarios: none.
