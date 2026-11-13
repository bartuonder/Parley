Model: `gpt-4.1-mini`. Scenarios: 56.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 82.1% |
| State matches expected diff | 82.1% |
| Forbidden action attempted | 0.0% |
| Policy violation (forbidden action or stale citation) | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 92.9% |
| Tool calls that returned an error | 3.3% |
| Refunds and cancellations that were right (precision) | 59.3% |
| Expected refunds and cancellations that were done (recall) | 91.7% |
| Judge: facts covered | 87.5% |
| Judge: no false claims | 85.7% |
| Judge: no leak | 98.2% |
| Judge: professional tone | 100.0% |
| Mean cost per ticket | $0.0047 |
| Latency p50 / p95 | 9.4s / 16.4s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 4 | 100% | 100% | $0.0024 |
| refund | 28 | 86% | 86% | $0.0052 |
| shipping | 8 | 88% | 100% | $0.0046 |
| subscription | 16 | 69% | 100% | $0.0043 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 4 | 100% | 100% | $0.0027 |
| hard | 20 | 85% | 95% | $0.0050 |
| medium | 32 | 78% | 91% | $0.0047 |

Failed: DLG-002, DLG-003, DLG-004, DLG-002, DLG-013, DLG-002, DLG-013, DLG-001, DLG-002, DLG-013

Repeats: 4 runs. Success 78.6% to 85.7% (mean 82.1%). Solved in every run (pass^4): 64.3%. Solved in at least one run: 92.9%. Unstable scenarios: DLG-001, DLG-003, DLG-004, DLG-013.
