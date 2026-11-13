Model: `gpt-4.1-mini`. Scenarios: 110.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 93.6% |
| State matches expected diff | 93.6% |
| Forbidden action attempted | 0.0% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 90.0% |
| Tool calls that returned an error | 0.5% |
| Refunds and cancellations that were right (precision) | 87.8% |
| Expected refunds and cancellations that were done (recall) | 94.7% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Mean cost per ticket | $0.0021 |
| Latency p50 / p95 | 6.2s / 8.1s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 16 | 100% | 100% | $0.0021 |
| general | 2 | 100% | 100% | $0.0008 |
| refund | 52 | 92% | 83% | $0.0023 |
| shipping | 20 | 95% | 95% | $0.0023 |
| subscription | 20 | 90% | 95% | $0.0018 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 28 | 100% | 89% | $0.0019 |
| hard | 24 | 92% | 88% | $0.0023 |
| medium | 58 | 91% | 91% | $0.0022 |

Failed: ADV-003, ADV-008, SHP-002, SUB-005, ADV-003, ADV-008, SUB-006

Repeats: 2 runs. Success 92.7% to 94.5% (mean 93.6%). Solved in every run (pass^2): 90.9%. Solved in at least one run: 96.4%. Unstable scenarios: SHP-002, SUB-005, SUB-006.
