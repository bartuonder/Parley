Model: `gpt-4.1-mini`. Scenarios: 14.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 85.7% |
| State matches expected diff | 85.7% |
| Forbidden action attempted | 0.0% |
| Tickets flagged by the injection scan | 7.1% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 85.7% |
| Tool calls that returned an error | 0.0% |
| Refunds and cancellations that were right (precision) | 88.9% |
| Expected refunds and cancellations that were done (recall) | 88.9% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Mean cost per ticket | $0.0085 |
| Latency p50 / p95 | 13.1s / 28.6s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 1 | 100% | 100% | $0.0044 |
| refund | 7 | 71% | 71% | $0.0101 |
| shipping | 2 | 100% | 100% | $0.0108 |
| subscription | 4 | 100% | 100% | $0.0056 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 1 | 0% | 0% | $0.0158 |
| hard | 5 | 100% | 100% | $0.0092 |
| medium | 8 | 88% | 88% | $0.0072 |

Failed: DLG-001, DLG-006
