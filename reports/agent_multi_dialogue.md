Model: `gpt-4.1-mini`. Scenarios: 56.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 98.2% |
| State matches expected diff | 98.2% |
| Forbidden action attempted | 0.0% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 83.9% |
| Tool calls that returned an error | 1.3% |
| Refunds and cancellations that were right (precision) | 100.0% |
| Expected refunds and cancellations that were done (recall) | 97.2% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Judge: facts covered | 87.5% |
| Judge: no false claims | 91.1% |
| Judge: no leak | 98.2% |
| Judge: professional tone | 100.0% |
| Mean cost per ticket | $0.0084 |
| Latency p50 / p95 | 18.9s / 35.4s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 4 | 100% | 100% | $0.0056 |
| refund | 28 | 96% | 68% | $0.0099 |
| shipping | 8 | 100% | 100% | $0.0105 |
| subscription | 16 | 100% | 100% | $0.0055 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 4 | 100% | 100% | $0.0033 |
| hard | 20 | 95% | 80% | $0.0095 |
| medium | 32 | 100% | 84% | $0.0084 |

Failed: DLG-011

Repeats: 4 runs. Success 92.9% to 100.0% (mean 98.2%). Solved in every run (pass^4): 92.9%. Solved in at least one run: 100.0%. Unstable scenarios: DLG-011.
