Model: `gpt-4.1-mini`. Scenarios: 55.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 98.2% |
| State matches expected diff | 98.2% |
| Forbidden action attempted | 0.0% |
| Tickets flagged by the injection scan | 3.6% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 94.5% |
| Tool calls that returned an error | 0.0% |
| Refunds and cancellations that were right (precision) | 100.0% |
| Expected refunds and cancellations that were done (recall) | 94.7% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Mean cost per ticket | $0.0029 |
| Latency p50 / p95 | 5.0s / 12.9s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 8 | 100% | 88% | $0.0027 |
| general | 1 | 100% | 100% | $0.0012 |
| refund | 26 | 96% | 92% | $0.0032 |
| shipping | 10 | 100% | 100% | $0.0027 |
| subscription | 10 | 100% | 100% | $0.0028 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 14 | 100% | 93% | $0.0023 |
| hard | 12 | 92% | 100% | $0.0032 |
| medium | 29 | 100% | 93% | $0.0031 |

Failed: REF-006
