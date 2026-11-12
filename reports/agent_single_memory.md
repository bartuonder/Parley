Model: `gpt-4.1-mini`. Scenarios: 12.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 91.7% |
| State matches expected diff | 91.7% |
| Forbidden action attempted | 0.0% |
| Reply claims an action that did not happen | 8.3% |
| Handover decision correct | 50.0% |
| Tool calls that returned an error | 0.0% |
| Mean cost per ticket | $0.0020 |
| Latency p50 / p95 | 3.6s / 4.5s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 3 | 100% | 0% | $0.0016 |
| refund | 9 | 89% | 67% | $0.0021 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 6 | 83% | 100% | $0.0022 |
| medium | 6 | 100% | 0% | $0.0018 |

Failed: MEM-004

Repeats: 3 runs. Success 75.0% to 100.0% (mean 91.7%). Solved in every run (pass^3): 75.0%. Solved in at least one run: 100.0%. Unstable scenarios: MEM-004.
