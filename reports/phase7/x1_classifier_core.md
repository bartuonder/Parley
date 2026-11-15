Model: `gpt-4.1-mini`. Scenarios: 55.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 100.0% |
| State matches expected diff | 100.0% |
| Forbidden action attempted | 0.0% |
| Tickets flagged by the injection scan | 3.6% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 90.9% |
| Tool calls that returned an error | 0.4% |
| Refunds and cancellations that were right (precision) | 100.0% |
| Expected refunds and cancellations that were done (recall) | 100.0% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Mean cost per ticket | $0.0032 |
| Latency p50 / p95 | 5.6s / 10.0s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 8 | 100% | 100% | $0.0028 |
| general | 1 | 100% | 100% | $0.0013 |
| refund | 26 | 100% | 92% | $0.0034 |
| shipping | 10 | 100% | 100% | $0.0035 |
| subscription | 10 | 100% | 70% | $0.0029 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 14 | 100% | 86% | $0.0027 |
| hard | 12 | 100% | 100% | $0.0032 |
| medium | 29 | 100% | 90% | $0.0034 |

Failed: none
