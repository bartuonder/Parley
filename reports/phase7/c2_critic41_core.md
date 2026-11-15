Model: `gpt-4.1-mini`. Scenarios: 55.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 96.4% |
| State matches expected diff | 96.4% |
| Forbidden action attempted | 0.0% |
| Tickets flagged by the injection scan | 3.6% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 96.4% |
| Tool calls that returned an error | 1.4% |
| Refunds and cancellations that were right (precision) | 100.0% |
| Expected refunds and cancellations that were done (recall) | 89.5% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Mean cost per ticket | $0.0059 |
| Latency p50 / p95 | 6.0s / 10.7s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 8 | 88% | 100% | $0.0051 |
| general | 1 | 100% | 100% | $0.0024 |
| refund | 26 | 100% | 96% | $0.0065 |
| shipping | 10 | 100% | 90% | $0.0062 |
| subscription | 10 | 90% | 100% | $0.0049 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 14 | 100% | 100% | $0.0048 |
| hard | 12 | 83% | 92% | $0.0077 |
| medium | 29 | 100% | 97% | $0.0056 |

Failed: BIL-002, SUB-007
