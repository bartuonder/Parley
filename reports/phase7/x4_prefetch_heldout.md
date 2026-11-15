Model: `gpt-4.1-mini`. Scenarios: 31.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 96.8% |
| State matches expected diff | 96.8% |
| Forbidden action attempted | 0.0% |
| Tickets flagged by the injection scan | 3.2% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 93.5% |
| Tool calls that returned an error | 0.9% |
| Refunds and cancellations that were right (precision) | 92.9% |
| Expected refunds and cancellations that were done (recall) | 100.0% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Mean cost per ticket | $0.0027 |
| Latency p50 / p95 | 5.4s / 8.5s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 6 | 100% | 83% | $0.0026 |
| general | 1 | 100% | 100% | $0.0019 |
| refund | 12 | 92% | 92% | $0.0030 |
| shipping | 7 | 100% | 100% | $0.0028 |
| subscription | 5 | 100% | 100% | $0.0024 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 7 | 100% | 100% | $0.0026 |
| hard | 7 | 86% | 71% | $0.0028 |
| medium | 17 | 100% | 100% | $0.0027 |

Failed: HLD-011
