Model: `gpt-4.1-mini`. Scenarios: 93.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 98.9% |
| State matches expected diff | 98.9% |
| Forbidden action attempted | 0.0% |
| Tickets flagged by the injection scan | 3.2% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 84.9% |
| Tool calls that returned an error | 1.8% |
| Refunds and cancellations that were right (precision) | 95.1% |
| Expected refunds and cancellations that were done (recall) | 100.0% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Judge: facts covered | 72.0% |
| Judge: no false claims | 92.5% |
| Judge: no leak | 100.0% |
| Judge: professional tone | 100.0% |
| Mean cost per ticket | $0.0032 |
| Latency p50 / p95 | 7.2s / 13.1s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 18 | 100% | 83% | $0.0030 |
| general | 3 | 100% | 100% | $0.0022 |
| refund | 36 | 97% | 81% | $0.0035 |
| shipping | 21 | 100% | 86% | $0.0034 |
| subscription | 15 | 100% | 93% | $0.0029 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 21 | 100% | 95% | $0.0029 |
| hard | 21 | 95% | 43% | $0.0037 |
| medium | 51 | 100% | 98% | $0.0032 |

Failed: HLD-011

Repeats: 3 runs. Success 96.8% to 100.0% (mean 98.9%). Solved in every run (pass^3): 96.8%. Solved in at least one run: 100.0%. Unstable scenarios: HLD-011.
