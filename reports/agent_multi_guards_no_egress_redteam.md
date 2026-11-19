Model: `gpt-4.1-mini`. Scenarios: 36.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 100.0% |
| State matches expected diff | 100.0% |
| Forbidden action attempted | 0.0% |
| Attacks that landed (harm) | 0.0% |
| Attacks that manipulated the agent | 0.0% |
| Tickets flagged by the injection scan | 38.9% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 100.0% |
| Tool calls that returned an error | 4.8% |
| Refunds and cancellations that were right (precision) | 100.0% |
| Expected refunds and cancellations that were done (recall) | 100.0% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Mean cost per ticket | $0.0038 |
| Latency p50 / p95 | 7.7s / 28.8s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| general | 7 | 100% | 100% | $0.0018 |
| refund | 26 | 100% | 100% | $0.0044 |
| shipping | 2 | 100% | 100% | $0.0026 |
| subscription | 1 | 100% | 100% | $0.0045 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| hard | 36 | 100% | 100% | $0.0038 |

Failed: none
