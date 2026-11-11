Model: `gpt-4.1-mini`. Scenarios: 55.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 92.7% |
| State matches expected diff | 92.7% |
| Forbidden action attempted | 0.0% |
| Handover decision correct | 85.5% |
| Tool calls that returned an error | 1.2% |
| Mean cost per ticket | $0.0017 |
| Latency p50 / p95 | 3.9s / 5.6s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 8 | 100% | 100% | $0.0017 |
| general | 1 | 100% | 100% | $0.0003 |
| refund | 26 | 85% | 81% | $0.0017 |
| shipping | 10 | 100% | 70% | $0.0019 |
| subscription | 10 | 100% | 100% | $0.0017 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 14 | 100% | 93% | $0.0017 |
| hard | 12 | 83% | 83% | $0.0016 |
| medium | 29 | 93% | 83% | $0.0018 |

Failed: ADV-003, REF-003, REF-006, REF-016
