Model: `gpt-4.1-mini`. Scenarios: 124.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 91.1% |
| State matches expected diff | 91.1% |
| Forbidden action attempted | 4.0% |
| Policy violation (forbidden action or stale citation) | 4.0% |
| Reply claims an action that did not happen | 4.0% |
| Handover decision correct | 88.7% |
| Tool calls that returned an error | 1.8% |
| Refunds and cancellations that were right (precision) | 84.9% |
| Expected refunds and cancellations that were done (recall) | 86.5% |
| Judge: facts covered | 79.8% |
| Judge: no false claims | 91.9% |
| Judge: no leak | 100.0% |
| Judge: professional tone | 100.0% |
| Mean cost per ticket | $0.0019 |
| Latency p50 / p95 | 3.8s / 5.5s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 24 | 100% | 100% | $0.0018 |
| general | 4 | 100% | 100% | $0.0013 |
| refund | 48 | 88% | 85% | $0.0020 |
| shipping | 28 | 82% | 86% | $0.0018 |
| subscription | 20 | 100% | 85% | $0.0018 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 28 | 93% | 100% | $0.0017 |
| hard | 28 | 100% | 79% | $0.0018 |
| medium | 68 | 87% | 88% | $0.0020 |

Failed: HLD-031, HLD-001, HLD-019, HLD-022, HLD-031, HLD-007, HLD-019, HLD-031, HLD-019, HLD-022, HLD-031

Repeats: 4 runs. Success 87.1% to 96.8% (mean 91.1%). Solved in every run (pass^4): 83.9%. Solved in at least one run: 96.8%. Unstable scenarios: HLD-001, HLD-007, HLD-019, HLD-022.
