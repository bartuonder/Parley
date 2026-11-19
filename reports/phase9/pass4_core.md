Model: `gpt-4.1-mini`. Scenarios: 220.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 99.1% |
| State matches expected diff | 99.1% |
| Forbidden action attempted | 0.0% |
| Tickets flagged by the injection scan | 3.6% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 95.9% |
| Tool calls that returned an error | 1.0% |
| Refunds and cancellations that were right (precision) | 100.0% |
| Expected refunds and cancellations that were done (recall) | 97.4% |
| Router picked the expected specialist | 100.0% |
| Critic answer unreadable, plan approved unreviewed | 0.0% |
| Mean cost per ticket | $0.0031 |
| Latency p50 / p95 | 7.5s / 11.2s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 32 | 100% | 91% | $0.0029 |
| general | 4 | 100% | 100% | $0.0017 |
| refund | 104 | 100% | 97% | $0.0033 |
| shipping | 40 | 98% | 100% | $0.0031 |
| subscription | 40 | 98% | 92% | $0.0027 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 56 | 100% | 95% | $0.0026 |
| hard | 48 | 98% | 98% | $0.0034 |
| medium | 116 | 99% | 96% | $0.0032 |

Failed: SHP-002, SUB-007

Repeats: 4 runs. Success 98.2% to 100.0% (mean 99.1%). Solved in every run (pass^4): 96.4%. Solved in at least one run: 100.0%. Unstable scenarios: SHP-002, SUB-007.
