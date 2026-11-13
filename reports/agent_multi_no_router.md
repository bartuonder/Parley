Model: `gpt-4.1-mini`. Scenarios: 110.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 100.0% |
| State matches expected diff | 100.0% |
| Forbidden action attempted | 0.0% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 92.7% |
| Tool calls that returned an error | 0.2% |
| Refunds and cancellations that were right (precision) | 100.0% |
| Expected refunds and cancellations that were done (recall) | 100.0% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Mean cost per ticket | $0.0025 |
| Latency p50 / p95 | 6.1s / 9.9s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 16 | 100% | 94% | $0.0027 |
| general | 2 | 100% | 100% | $0.0011 |
| refund | 52 | 100% | 90% | $0.0026 |
| shipping | 20 | 100% | 90% | $0.0027 |
| subscription | 20 | 100% | 100% | $0.0022 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 28 | 100% | 93% | $0.0022 |
| hard | 24 | 100% | 83% | $0.0029 |
| medium | 58 | 100% | 97% | $0.0025 |

Failed: none

Repeats: 2 runs. Success 100.0% to 100.0% (mean 100.0%). Solved in every run (pass^2): 100.0%. Solved in at least one run: 100.0%. Unstable scenarios: none.
