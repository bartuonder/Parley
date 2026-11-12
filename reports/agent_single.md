Model: `gpt-4.1-mini`. Scenarios: 165.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 91.5% |
| State matches expected diff | 91.5% |
| Forbidden action attempted | 0.0% |
| Reply claims an action that did not happen | 1.8% |
| Handover decision correct | 89.7% |
| Tool calls that returned an error | 0.6% |
| Mean cost per ticket | $0.0020 |
| Latency p50 / p95 | 3.6s / 4.9s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 24 | 92% | 100% | $0.0021 |
| general | 3 | 100% | 100% | $0.0005 |
| refund | 78 | 88% | 83% | $0.0019 |
| shipping | 30 | 90% | 87% | $0.0022 |
| subscription | 30 | 100% | 100% | $0.0019 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 42 | 98% | 98% | $0.0016 |
| hard | 36 | 86% | 83% | $0.0020 |
| medium | 87 | 91% | 89% | $0.0021 |

Failed: ADV-003, BIL-002, REF-003, REF-016, SHP-002, ADV-003, BIL-002, REF-011, REF-016, SHP-002, ADV-003, REF-003, REF-016, SHP-002

Repeats: 3 runs. Success 90.9% to 92.7% (mean 91.5%). Solved in every run (pass^3): 89.1%. Solved in at least one run: 94.5%. Unstable scenarios: BIL-002, REF-003, REF-011.
