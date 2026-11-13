Model: `gpt-4.1-mini`. Scenarios: 62.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 98.4% |
| State matches expected diff | 98.4% |
| Forbidden action attempted | 0.0% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 83.9% |
| Tool calls that returned an error | 0.4% |
| Refunds and cancellations that were right (precision) | 96.3% |
| Expected refunds and cancellations that were done (recall) | 100.0% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Mean cost per ticket | $0.0028 |
| Latency p50 / p95 | 6.2s / 10.9s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 12 | 100% | 83% | $0.0028 |
| general | 2 | 100% | 100% | $0.0017 |
| refund | 24 | 96% | 92% | $0.0031 |
| shipping | 14 | 100% | 79% | $0.0027 |
| subscription | 10 | 100% | 70% | $0.0024 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 14 | 100% | 100% | $0.0025 |
| hard | 14 | 93% | 50% | $0.0036 |
| medium | 34 | 100% | 91% | $0.0026 |

Failed: HLD-011

Repeats: 2 runs. Success 96.8% to 100.0% (mean 98.4%). Solved in every run (pass^2): 96.8%. Solved in at least one run: 100.0%. Unstable scenarios: HLD-011.
