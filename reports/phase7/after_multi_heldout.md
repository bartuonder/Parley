Model: `gpt-4.1-mini`. Scenarios: 31.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 100.0% |
| State matches expected diff | 100.0% |
| Forbidden action attempted | 0.0% |
| Tickets flagged by the injection scan | 3.2% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 83.9% |
| Tool calls that returned an error | 0.9% |
| Refunds and cancellations that were right (precision) | 100.0% |
| Expected refunds and cancellations that were done (recall) | 100.0% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Mean cost per ticket | $0.0030 |
| Latency p50 / p95 | 5.1s / 10.0s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 6 | 100% | 67% | $0.0026 |
| general | 1 | 100% | 100% | $0.0018 |
| refund | 12 | 100% | 100% | $0.0035 |
| shipping | 7 | 100% | 71% | $0.0025 |
| subscription | 5 | 100% | 80% | $0.0032 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 7 | 100% | 100% | $0.0028 |
| hard | 7 | 100% | 71% | $0.0036 |
| medium | 17 | 100% | 82% | $0.0028 |

Failed: none
