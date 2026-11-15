Model: `gpt-4.1-mini`. Scenarios: 31.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 96.8% |
| State matches expected diff | 96.8% |
| Forbidden action attempted | 0.0% |
| Tickets flagged by the injection scan | 3.2% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 96.8% |
| Tool calls that returned an error | 0.8% |
| Refunds and cancellations that were right (precision) | 100.0% |
| Expected refunds and cancellations that were done (recall) | 92.3% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Mean cost per ticket | $0.0069 |
| Latency p50 / p95 | 6.1s / 14.3s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 6 | 100% | 83% | $0.0064 |
| general | 1 | 100% | 100% | $0.0044 |
| refund | 12 | 92% | 100% | $0.0082 |
| shipping | 7 | 100% | 100% | $0.0069 |
| subscription | 5 | 100% | 100% | $0.0050 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 7 | 86% | 86% | $0.0070 |
| hard | 7 | 100% | 100% | $0.0081 |
| medium | 17 | 100% | 100% | $0.0064 |

Failed: HLD-001
