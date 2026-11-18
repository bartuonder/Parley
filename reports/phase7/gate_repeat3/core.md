Model: `gpt-4.1-mini`. Scenarios: 165.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 99.4% |
| State matches expected diff | 99.4% |
| Forbidden action attempted | 0.0% |
| Tickets flagged by the injection scan | 3.6% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 92.7% |
| Tool calls that returned an error | 0.6% |
| Refunds and cancellations that were right (precision) | 98.3% |
| Expected refunds and cancellations that were done (recall) | 100.0% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Judge: facts covered | 80.6% |
| Judge: no false claims | 97.0% |
| Judge: no leak | 100.0% |
| Judge: professional tone | 100.0% |
| Mean cost per ticket | $0.0030 |
| Latency p50 / p95 | 7.1s / 10.5s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 24 | 100% | 92% | $0.0030 |
| general | 3 | 100% | 100% | $0.0016 |
| refund | 78 | 100% | 91% | $0.0033 |
| shipping | 30 | 100% | 93% | $0.0029 |
| subscription | 30 | 97% | 97% | $0.0027 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 42 | 100% | 90% | $0.0027 |
| hard | 36 | 100% | 94% | $0.0032 |
| medium | 87 | 99% | 93% | $0.0031 |

Failed: SUB-006

Repeats: 3 runs. Success 98.2% to 100.0% (mean 99.4%). Solved in every run (pass^3): 98.2%. Solved in at least one run: 100.0%. Unstable scenarios: SUB-006.
