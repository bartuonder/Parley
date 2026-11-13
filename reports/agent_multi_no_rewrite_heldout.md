Model: `gpt-4.1-mini`. Scenarios: 62.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 96.8% |
| State matches expected diff | 96.8% |
| Forbidden action attempted | 0.0% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 93.5% |
| Tool calls that returned an error | 0.4% |
| Refunds and cancellations that were right (precision) | 100.0% |
| Expected refunds and cancellations that were done (recall) | 92.3% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Mean cost per ticket | $0.0027 |
| Latency p50 / p95 | 6.7s / 12.0s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 12 | 100% | 83% | $0.0024 |
| general | 2 | 100% | 100% | $0.0015 |
| refund | 24 | 100% | 100% | $0.0031 |
| shipping | 14 | 86% | 100% | $0.0027 |
| subscription | 10 | 100% | 80% | $0.0023 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 14 | 100% | 100% | $0.0025 |
| hard | 14 | 100% | 79% | $0.0030 |
| medium | 34 | 94% | 97% | $0.0027 |

Failed: HLD-019, HLD-019

Repeats: 2 runs. Success 96.8% to 96.8% (mean 96.8%). Solved in every run (pass^2): 96.8%. Solved in at least one run: 96.8%. Unstable scenarios: none.
