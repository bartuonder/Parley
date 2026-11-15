Model: `gpt-4.1-mini`. Scenarios: 31.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 67.7% |
| State matches expected diff | 67.7% |
| Forbidden action attempted | 0.0% |
| Tickets flagged by the injection scan | 3.2% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 38.7% |
| Tool calls that returned an error | 0.0% |
| Refunds and cancellations that were right (precision) | 100.0% |
| Expected refunds and cancellations that were done (recall) | 15.4% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Mean cost per ticket | $0.0051 |
| Latency p50 / p95 | 12.6s / 20.5s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 6 | 83% | 50% | $0.0049 |
| general | 1 | 100% | 100% | $0.0017 |
| refund | 12 | 58% | 42% | $0.0058 |
| shipping | 7 | 71% | 43% | $0.0043 |
| subscription | 5 | 60% | 0% | $0.0054 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 7 | 57% | 29% | $0.0050 |
| hard | 7 | 86% | 43% | $0.0059 |
| medium | 17 | 65% | 41% | $0.0049 |

Failed: HLD-012, HLD-001, HLD-004, HLD-005, HLD-006, HLD-007, HLD-019, HLD-022, HLD-026, HLD-027
