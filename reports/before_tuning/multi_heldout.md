Model: `gpt-4.1-mini`. Scenarios: 93.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 91.4% |
| State matches expected diff | 91.4% |
| Forbidden action attempted | 0.0% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 89.2% |
| Tool calls that returned an error | 1.0% |
| Refunds and cancellations that were right (precision) | 94.3% |
| Expected refunds and cancellations that were done (recall) | 84.6% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Judge: facts covered | 74.2% |
| Judge: no false claims | 88.2% |
| Judge: no leak | 100.0% |
| Judge: professional tone | 98.9% |
| Mean cost per ticket | $0.0027 |
| Latency p50 / p95 | 7.8s / 12.3s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 18 | 100% | 89% | $0.0026 |
| general | 3 | 100% | 100% | $0.0016 |
| refund | 36 | 100% | 100% | $0.0029 |
| shipping | 21 | 86% | 90% | $0.0030 |
| subscription | 15 | 67% | 60% | $0.0024 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 21 | 100% | 100% | $0.0023 |
| hard | 21 | 100% | 76% | $0.0029 |
| medium | 51 | 84% | 90% | $0.0029 |

Failed: HLD-019, HLD-027, HLD-028, HLD-019, HLD-027, HLD-019, HLD-027, HLD-028

Repeats: 3 runs. Success 90.3% to 93.5% (mean 91.4%). Solved in every run (pass^3): 90.3%. Solved in at least one run: 93.5%. Unstable scenarios: HLD-028.
