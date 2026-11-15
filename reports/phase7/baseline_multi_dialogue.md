Model: `gpt-4.1-mini`. Scenarios: 14.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 100.0% |
| State matches expected diff | 100.0% |
| Forbidden action attempted | 0.0% |
| Tickets flagged by the injection scan | 7.1% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 100.0% |
| Tool calls that returned an error | 3.2% |
| Refunds and cancellations that were right (precision) | 100.0% |
| Expected refunds and cancellations that were done (recall) | 100.0% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Mean cost per ticket | $0.0086 |
| Latency p50 / p95 | 14.9s / 30.2s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 1 | 100% | 100% | $0.0030 |
| refund | 7 | 100% | 100% | $0.0105 |
| shipping | 2 | 100% | 100% | $0.0079 |
| subscription | 4 | 100% | 100% | $0.0071 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 1 | 100% | 100% | $0.0032 |
| hard | 5 | 100% | 100% | $0.0101 |
| medium | 8 | 100% | 100% | $0.0083 |

Failed: none
