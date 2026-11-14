Model: `gpt-4.1-mini`. Scenarios: 110.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 98.2% |
| State matches expected diff | 98.2% |
| Forbidden action attempted | 0.0% |
| Tickets flagged by the injection scan | 3.6% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 91.8% |
| Tool calls that returned an error | 0.5% |
| Refunds and cancellations that were right (precision) | 100.0% |
| Expected refunds and cancellations that were done (recall) | 94.7% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Judge: facts covered | 79.1% |
| Judge: no false claims | 98.2% |
| Judge: no leak | 100.0% |
| Judge: professional tone | 100.0% |
| Mean cost per ticket | $0.0030 |
| Latency p50 / p95 | 6.1s / 10.4s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 16 | 94% | 88% | $0.0029 |
| general | 2 | 100% | 100% | $0.0014 |
| refund | 52 | 98% | 94% | $0.0033 |
| shipping | 20 | 100% | 90% | $0.0031 |
| subscription | 20 | 100% | 90% | $0.0025 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 28 | 96% | 86% | $0.0027 |
| hard | 24 | 96% | 96% | $0.0035 |
| medium | 58 | 100% | 93% | $0.0030 |

Failed: REF-001, BIL-002

Repeats: 2 runs. Success 98.2% to 98.2% (mean 98.2%). Solved in every run (pass^2): 96.4%. Solved in at least one run: 100.0%. Unstable scenarios: BIL-002, REF-001.
