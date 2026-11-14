Model: `gpt-4.1-mini`. Scenarios: 165.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 98.8% |
| State matches expected diff | 98.8% |
| Forbidden action attempted | 0.0% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 93.9% |
| Tool calls that returned an error | 0.5% |
| Refunds and cancellations that were right (precision) | 98.2% |
| Expected refunds and cancellations that were done (recall) | 98.2% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Judge: facts covered | 82.4% |
| Judge: no false claims | 95.8% |
| Judge: no leak | 100.0% |
| Judge: professional tone | 100.0% |
| Mean cost per ticket | $0.0029 |
| Latency p50 / p95 | 5.8s / 8.9s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 24 | 100% | 96% | $0.0028 |
| general | 3 | 100% | 100% | $0.0012 |
| refund | 78 | 99% | 91% | $0.0032 |
| shipping | 30 | 100% | 97% | $0.0030 |
| subscription | 30 | 97% | 97% | $0.0024 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 42 | 100% | 90% | $0.0025 |
| hard | 36 | 100% | 100% | $0.0031 |
| medium | 87 | 98% | 93% | $0.0030 |

Failed: SUB-005, ADV-006

Repeats: 3 runs. Success 98.2% to 100.0% (mean 98.8%). Solved in every run (pass^3): 96.4%. Solved in at least one run: 100.0%. Unstable scenarios: ADV-006, SUB-005.
