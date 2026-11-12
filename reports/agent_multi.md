Model: `gpt-4.1-mini`. Scenarios: 165.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 99.4% |
| State matches expected diff | 99.4% |
| Forbidden action attempted | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 87.3% |
| Tool calls that returned an error | 0.8% |
| Router picked the expected specialist | 85.5% |
| Mean cost per ticket | $0.0026 |
| Latency p50 / p95 | 7.0s / 9.4s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 24 | 100% | 100% | $0.0025 |
| general | 3 | 100% | 67% | $0.0011 |
| refund | 78 | 99% | 79% | $0.0027 |
| shipping | 30 | 100% | 87% | $0.0029 |
| subscription | 30 | 100% | 100% | $0.0023 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 42 | 100% | 93% | $0.0021 |
| hard | 36 | 97% | 89% | $0.0028 |
| medium | 87 | 100% | 84% | $0.0028 |

Failed: ADV-008

Repeats: 3 runs. Success 98.2% to 100.0% (mean 99.4%). Solved in every run (pass^3): 98.2%. Solved in at least one run: 100.0%. Unstable scenarios: ADV-008.
