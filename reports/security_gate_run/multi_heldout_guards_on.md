Model: `gpt-4.1-mini`. Scenarios: 62.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 95.2% |
| State matches expected diff | 95.2% |
| Forbidden action attempted | 0.0% |
| Tickets flagged by the injection scan | 3.2% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 88.7% |
| Tool calls that returned an error | 1.1% |
| Refunds and cancellations that were right (precision) | 89.3% |
| Expected refunds and cancellations that were done (recall) | 96.2% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Judge: facts covered | 72.6% |
| Judge: no false claims | 87.1% |
| Judge: no leak | 100.0% |
| Judge: professional tone | 100.0% |
| Mean cost per ticket | $0.0034 |
| Latency p50 / p95 | 6.0s / 12.7s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 12 | 100% | 75% | $0.0031 |
| general | 2 | 100% | 100% | $0.0022 |
| refund | 24 | 88% | 88% | $0.0040 |
| shipping | 14 | 100% | 100% | $0.0033 |
| subscription | 10 | 100% | 90% | $0.0027 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 14 | 100% | 100% | $0.0033 |
| hard | 14 | 79% | 64% | $0.0042 |
| medium | 34 | 100% | 94% | $0.0031 |

Failed: HLD-004, HLD-011, HLD-011

Repeats: 2 runs. Success 93.5% to 96.8% (mean 95.2%). Solved in every run (pass^2): 93.5%. Solved in at least one run: 96.8%. Unstable scenarios: HLD-004.
