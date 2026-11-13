Model: `gpt-4.1-mini`. Scenarios: 220.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 99.5% |
| State matches expected diff | 99.5% |
| Forbidden action attempted | 0.0% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 91.4% |
| Tool calls that returned an error | 0.1% |
| Refunds and cancellations that were right (precision) | 98.7% |
| Expected refunds and cancellations that were done (recall) | 100.0% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Judge: facts covered | 83.2% |
| Judge: no false claims | 97.3% |
| Judge: no leak | 100.0% |
| Judge: professional tone | 100.0% |
| Mean cost per ticket | $0.0027 |
| Latency p50 / p95 | 7.1s / 10.3s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 32 | 100% | 94% | $0.0024 |
| general | 4 | 100% | 100% | $0.0009 |
| refund | 104 | 100% | 88% | $0.0029 |
| shipping | 40 | 100% | 98% | $0.0027 |
| subscription | 40 | 98% | 90% | $0.0023 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 56 | 100% | 88% | $0.0022 |
| hard | 48 | 100% | 96% | $0.0030 |
| medium | 116 | 99% | 91% | $0.0027 |

Failed: SUB-005

Repeats: 4 runs. Success 98.2% to 100.0% (mean 99.5%). Solved in every run (pass^4): 98.2%. Solved in at least one run: 100.0%. Unstable scenarios: SUB-005.
