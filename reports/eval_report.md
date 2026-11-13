# Evaluation report

Generated 2026-11-13 22:20 UTC. Agent model `gpt-4.1-mini`, router `gpt-4o-mini`. Cost of this run: $5.39.

## Single agent against multi-agent: core set

| Metric | Single agent | Multi-agent |
| --- | --- | --- |
| Task success per run (mean, range) | 93.2% (90.9% to 96.4%) | 99.5% (98.2% to 100.0%) |
| Solved in every one of 4 runs (pass^4) | 85.5% | 98.2% |
| Forbidden action attempted | 0.5% | 0.0% |
| Reply claims an action that did not happen | 0.9% | 0.0% |
| Handover decision correct | 90.9% | 91.4% |
| Policy violation (forbidden action or stale citation) | 0.5% | 0.0% |
| Refunds and cancellations that were right (precision) | 93.0% | 98.7% |
| Expected refunds and cancellations that were done (recall) | 86.8% | 100.0% |
| Tool calls with an error | 0.9% | 0.1% |
| Router picked the expected specialist | n/a | 100.0% |
| Mean cost per ticket | $0.0019 | $0.0027 |
| Latency p50 / p95 | 4.1s / 6.2s | 7.1s / 10.3s |

## Single agent against multi-agent: heldout set

| Metric | Single agent | Multi-agent |
| --- | --- | --- |
| Task success per run (mean, range) | 91.1% (87.1% to 96.8%) | 99.2% (96.8% to 100.0%) |
| Solved in every one of 4 runs (pass^4) | 83.9% | 96.8% |
| Forbidden action attempted | 4.0% | 0.0% |
| Reply claims an action that did not happen | 4.0% | 0.0% |
| Handover decision correct | 88.7% | 87.1% |
| Policy violation (forbidden action or stale citation) | 4.0% | 0.0% |
| Refunds and cancellations that were right (precision) | 84.9% | 100.0% |
| Expected refunds and cancellations that were done (recall) | 86.5% | 98.1% |
| Tool calls with an error | 1.8% | 0.4% |
| Router picked the expected specialist | n/a | 100.0% |
| Mean cost per ticket | $0.0019 | $0.0030 |
| Latency p50 / p95 | 3.8s / 5.5s | 6.7s / 12.8s |

## Single agent against multi-agent: dialogue set

| Metric | Single agent | Multi-agent |
| --- | --- | --- |
| Task success per run (mean, range) | 82.1% (78.6% to 85.7%) | 98.2% (92.9% to 100.0%) |
| Solved in every one of 4 runs (pass^4) | 64.3% | 92.9% |
| Forbidden action attempted | 0.0% | 0.0% |
| Reply claims an action that did not happen | 0.0% | 0.0% |
| Handover decision correct | 92.9% | 83.9% |
| Policy violation (forbidden action or stale citation) | 0.0% | 0.0% |
| Refunds and cancellations that were right (precision) | 59.3% | 100.0% |
| Expected refunds and cancellations that were done (recall) | 91.7% | 97.2% |
| Tool calls with an error | 3.3% | 1.3% |
| Router picked the expected specialist | n/a | 100.0% |
| Mean cost per ticket | $0.0047 | $0.0084 |
| Latency p50 / p95 | 9.4s / 16.4s | 18.9s / 35.4s |

## Reply quality (LLM judge)

| Scope | facts covered | no false claims | no leak | professional tone |
| --- | --- | --- | --- | --- |
| single/core | 78.2% | 95.5% | 100.0% | 100.0% |
| multi/core | 83.2% | 97.3% | 100.0% | 100.0% |
| single/heldout | 79.8% | 91.9% | 100.0% | 100.0% |
| multi/heldout | 71.8% | 94.4% | 100.0% | 100.0% |
| single/dialogue | 87.5% | 85.7% | 98.2% | 100.0% |
| multi/dialogue | 87.5% | 91.1% | 98.2% | 100.0% |

## Ablation of the multi-agent graph

| Configuration | Set | Success | pass^k | Handover | Unbacked claims | Cost / ticket |
| --- | --- | --- | --- | --- | --- | --- |
| Full multi-agent graph | core | 99.5% | 98.2% | 91.4% | 0.0% | $0.0027 |
| Full multi-agent graph | heldout | 99.2% | 96.8% | 87.1% | 0.0% | $0.0030 |
| Without the critic | core | 93.6% | 90.9% | 90.0% | 0.0% | $0.0021 |
| Without the critic | heldout | 96.8% | 93.5% | 90.3% | 0.0% | $0.0022 |
| Without the reply rewrite | core | 100.0% | 100.0% | 92.7% | 0.0% | $0.0025 |
| Without the reply rewrite | heldout | 96.8% | 96.8% | 93.5% | 0.0% | $0.0027 |
| Without routing (always billing) | core | 100.0% | 100.0% | 92.7% | 0.0% | $0.0025 |
| Without routing (always billing) | heldout | 98.4% | 96.8% | 83.9% | 0.0% | $0.0028 |

## Judge calibration

Judge `gpt-4.1` against 50 labeled replies: facts covered 94% (kappa 0.87), no false claims 98% (kappa 0.93), no leak 98% (kappa 0.79), professional tone 92% (kappa 0.56). Full table in `reports/judge_calibration.md`.
