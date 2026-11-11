Model: `gpt-4.1-mini`. Scenarios: 55.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 94.5% |
| State matches expected diff | 94.5% |
| Forbidden action attempted | 1.8% |
| Handover decision correct | 87.3% |
| Tool calls that returned an error | 3.9% |
| Mean cost per ticket | $0.0016 |
| Latency p50 / p95 | 4.3s / 6.9s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 8 | 88% | 75% | $0.0015 |
| general | 1 | 100% | 100% | $0.0006 |
| refund | 26 | 92% | 88% | $0.0016 |
| shipping | 10 | 100% | 80% | $0.0019 |
| subscription | 10 | 100% | 100% | $0.0017 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 14 | 93% | 86% | $0.0013 |
| hard | 12 | 83% | 92% | $0.0018 |
| medium | 29 | 100% | 86% | $0.0017 |

Failed: BIL-002, REF-001, REF-016
