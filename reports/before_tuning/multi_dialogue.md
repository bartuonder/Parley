Model: `gpt-4.1-mini`. Scenarios: 42.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 85.7% |
| State matches expected diff | 85.7% |
| Forbidden action attempted | 0.0% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 76.2% |
| Tool calls that returned an error | 0.9% |
| Refunds and cancellations that were right (precision) | 81.8% |
| Expected refunds and cancellations that were done (recall) | 88.9% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Judge: facts covered | 69.0% |
| Judge: no false claims | 61.9% |
| Judge: no leak | 97.6% |
| Judge: professional tone | 100.0% |
| Mean cost per ticket | $0.0086 |
| Latency p50 / p95 | 26.6s / 37.3s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 3 | 100% | 100% | $0.0051 |
| refund | 21 | 90% | 81% | $0.0088 |
| shipping | 6 | 100% | 67% | $0.0106 |
| subscription | 12 | 67% | 67% | $0.0083 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 3 | 100% | 100% | $0.0025 |
| hard | 15 | 80% | 80% | $0.0096 |
| medium | 24 | 88% | 71% | $0.0088 |

Failed: DLG-002, DLG-002, DLG-013, DLG-002, DLG-012, DLG-013

Repeats: 3 runs. Success 78.6% to 92.9% (mean 85.7%). Solved in every run (pass^3): 78.6%. Solved in at least one run: 92.9%. Unstable scenarios: DLG-012, DLG-013.
