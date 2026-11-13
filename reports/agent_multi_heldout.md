Model: `gpt-4.1-mini`. Scenarios: 124.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 99.2% |
| State matches expected diff | 99.2% |
| Forbidden action attempted | 0.0% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 87.1% |
| Tool calls that returned an error | 0.4% |
| Refunds and cancellations that were right (precision) | 100.0% |
| Expected refunds and cancellations that were done (recall) | 98.1% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Judge: facts covered | 71.8% |
| Judge: no false claims | 94.4% |
| Judge: no leak | 100.0% |
| Judge: professional tone | 100.0% |
| Mean cost per ticket | $0.0030 |
| Latency p50 / p95 | 6.7s / 12.8s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 24 | 100% | 83% | $0.0027 |
| general | 4 | 100% | 100% | $0.0021 |
| refund | 48 | 98% | 94% | $0.0034 |
| shipping | 28 | 100% | 86% | $0.0029 |
| subscription | 20 | 100% | 75% | $0.0025 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 28 | 100% | 96% | $0.0028 |
| hard | 28 | 96% | 68% | $0.0036 |
| medium | 68 | 100% | 91% | $0.0028 |

Failed: HLD-004

Repeats: 4 runs. Success 96.8% to 100.0% (mean 99.2%). Solved in every run (pass^4): 96.8%. Solved in at least one run: 100.0%. Unstable scenarios: HLD-004.
