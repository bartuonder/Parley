Model: `gpt-4.1-mini`. Scenarios: 62.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 96.8% |
| State matches expected diff | 96.8% |
| Forbidden action attempted | 0.0% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 90.3% |
| Tool calls that returned an error | 0.4% |
| Refunds and cancellations that were right (precision) | 92.6% |
| Expected refunds and cancellations that were done (recall) | 96.2% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Mean cost per ticket | $0.0022 |
| Latency p50 / p95 | 5.9s / 8.1s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 12 | 100% | 100% | $0.0021 |
| general | 2 | 100% | 100% | $0.0015 |
| refund | 24 | 92% | 88% | $0.0024 |
| shipping | 14 | 100% | 93% | $0.0022 |
| subscription | 10 | 100% | 80% | $0.0019 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 14 | 93% | 100% | $0.0021 |
| hard | 14 | 100% | 71% | $0.0024 |
| medium | 34 | 97% | 94% | $0.0022 |

Failed: HLD-001, HLD-031

Repeats: 2 runs. Success 93.5% to 100.0% (mean 96.8%). Solved in every run (pass^2): 93.5%. Solved in at least one run: 100.0%. Unstable scenarios: HLD-001, HLD-031.
