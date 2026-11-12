Model: `gpt-4.1-mini`. Scenarios: 12.

| Metric | Value |
| --- | --- |
| Task success (state matches and a reply was written) | 100.0% |
| State matches expected diff | 100.0% |
| Forbidden action attempted | 0.0% |
| Reply claims an action that did not happen | 0.0% |
| Handover decision correct | 50.0% |
| Tool calls that returned an error | 0.0% |
| Router picked the expected specialist | 100.0% |
| Mean cost per ticket | $0.0027 |
| Latency p50 / p95 | 7.1s / 7.9s |

| Category | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| billing | 3 | 100% | 0% | $0.0022 |
| refund | 9 | 100% | 67% | $0.0028 |

| Difficulty | n | success | handover | cost |
| --- | --- | --- | --- | --- |
| easy | 6 | 100% | 100% | $0.0030 |
| medium | 6 | 100% | 0% | $0.0023 |

Failed: none

Repeats: 3 runs. Success 100.0% to 100.0% (mean 100.0%). Solved in every run (pass^3): 100.0%. Solved in at least one run: 100.0%. Unstable scenarios: none.
