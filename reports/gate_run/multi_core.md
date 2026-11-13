Model: `gpt-4.1-mini`. Scenarios: 165.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 100.0% |
| State matches expected diff | 100.0% |
| Forbidden action attempted | 0.0% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 96.4% |
| Tool calls that returned an error | 0.1% |
| Refunds and cancellations that were right (precision) | 100.0% |
| Expected refunds and cancellations that were done (recall) | 100.0% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Judge: facts covered | 82.4% |
| Judge: no false claims | 97.0% |
| Judge: no leak | 100.0% |
| Judge: professional tone | 100.0% |
| Mean cost per ticket | $0.0029 |
| Latency p50 / p95 | 6.7s / 10.2s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 24 | 100% | 100% | $0.0028 |
| general | 3 | 100% | 100% | $0.0009 |
| refund | 78 | 100% | 95% | $0.0032 |
| shipping | 30 | 100% | 100% | $0.0030 |
| subscription | 30 | 100% | 93% | $0.0025 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 42 | 100% | 90% | $0.0024 |
| hard | 36 | 100% | 97% | $0.0033 |
| medium | 87 | 100% | 99% | $0.0030 |

Failed: none

Repeats: 3 runs. Success 100.0% to 100.0% (mean 100.0%). Solved in every run (pass^3): 100.0%. Solved in at least one run: 100.0%. Unstable scenarios: none.
