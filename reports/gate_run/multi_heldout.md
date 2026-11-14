Model: `gpt-4.1-mini`. Scenarios: 93.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 98.9% |
| State matches expected diff | 98.9% |
| Forbidden action attempted | 0.0% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 94.6% |
| Tool calls that returned an error | 0.0% |
| Refunds and cancellations that were right (precision) | 100.0% |
| Expected refunds and cancellations that were done (recall) | 97.4% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Judge: facts covered | 75.3% |
| Judge: no false claims | 93.5% |
| Judge: no leak | 100.0% |
| Judge: professional tone | 100.0% |
| Mean cost per ticket | $0.0033 |
| Latency p50 / p95 | 6.1s / 11.8s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 18 | 100% | 83% | $0.0031 |
| general | 3 | 100% | 100% | $0.0022 |
| refund | 36 | 97% | 97% | $0.0038 |
| shipping | 21 | 100% | 100% | $0.0032 |
| subscription | 15 | 100% | 93% | $0.0026 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 21 | 95% | 95% | $0.0032 |
| hard | 21 | 100% | 81% | $0.0036 |
| medium | 51 | 100% | 100% | $0.0032 |

Failed: HLD-001

Repeats: 3 runs. Success 96.8% to 100.0% (mean 98.9%). Solved in every run (pass^3): 96.8%. Solved in at least one run: 100.0%. Unstable scenarios: HLD-001.
