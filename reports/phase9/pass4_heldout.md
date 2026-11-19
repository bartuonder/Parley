Model: `gpt-4.1-mini`. Scenarios: 124.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 100.0% |
| State matches expected diff | 100.0% |
| Forbidden action attempted | 0.0% |
| Tickets flagged by the injection scan | 3.2% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 95.2% |
| Tool calls that returned an error | 1.4% |
| Refunds and cancellations that were right (precision) | 100.0% |
| Expected refunds and cancellations that were done (recall) | 100.0% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Mean cost per ticket | $0.0034 |
| Latency p50 / p95 | 8.2s / 14.5s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 24 | 100% | 96% | $0.0032 |
| general | 4 | 100% | 100% | $0.0023 |
| refund | 48 | 100% | 96% | $0.0039 |
| shipping | 28 | 100% | 89% | $0.0033 |
| subscription | 20 | 100% | 100% | $0.0028 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 28 | 100% | 100% | $0.0035 |
| hard | 28 | 100% | 82% | $0.0039 |
| medium | 68 | 100% | 99% | $0.0032 |

Failed: none

Repeats: 4 runs. Success 100.0% to 100.0% (mean 100.0%). Solved in every run (pass^4): 100.0%. Solved in at least one run: 100.0%. Unstable scenarios: none.
