# Evaluation report

Generated 2026-11-14 11:54 UTC. Agent model `gpt-4.1-mini`, router `gpt-4o-mini`. Cost of this run: $1.33.

## Reply quality (LLM judge)

| Scope | facts covered | no false claims | no leak | professional tone |
| --- | --- | --- | --- | --- |
| multi/core | 82.4% | 95.8% | 100.0% | 100.0% |
| multi/heldout | 75.3% | 93.5% | 100.0% | 100.0% |

## Ablation of the multi-agent graph

| Configuration | Set | Success | pass^k | Handover | Unbacked claims | Cost / ticket |
| --- | --- | --- | --- | --- | --- | --- |
| Full multi-agent graph | core | 98.8% | 96.4% | 93.9% | 0.0% | $0.0029 |
| Full multi-agent graph | heldout | 98.9% | 96.8% | 94.6% | 0.0% | $0.0033 |

## Judge calibration

Judge `gpt-4.1` against 50 labeled replies: facts covered 94% (kappa 0.87), no false claims 98% (kappa 0.93), no leak 98% (kappa 0.79), professional tone 92% (kappa 0.56). Full table in `reports/judge_calibration.md`.

## Regression gate

| Scope | Metric | Baseline | Current | Result |
| --- | --- | --- | --- | --- |
| multi/core | success_rate | 1 | 0.9879 | ok |
| multi/core | pass_all | 1 | 0.9636 | ok |
| multi/core | policy_violation_rate | 0 | 0 | ok |
| multi/core | unbacked_claim_rate | 0 | 0 | ok |
| multi/core | handover_accuracy | 0.9636 | 0.9394 | ok |
| multi/core | tool_precision | 1 | 0.9825 | ok |
| multi/core | tool_recall | 1 | 0.9825 | ok |
| multi/core | mean_cost_usd | 0.002903 | 0.002913 | ok |
| multi/core | judge_facts_covered | 0.8242 | 0.8242 | ok |
| multi/core | judge_no_false_claims | 0.9697 | 0.9576 | ok |
| multi/core | judge_no_leak | 1 | 1 | ok |
| multi/core | judge_professional_tone | 1 | 1 | ok |
| multi/heldout | success_rate | 0.9892 | 0.9892 | ok |
| multi/heldout | pass_all | 0.9677 | 0.9677 | ok |
| multi/heldout | policy_violation_rate | 0 | 0 | ok |
| multi/heldout | unbacked_claim_rate | 0 | 0 | ok |
| multi/heldout | handover_accuracy | 0.9355 | 0.9462 | ok |
| multi/heldout | tool_precision | 1 | 1 | ok |
| multi/heldout | tool_recall | 0.9744 | 0.9744 | ok |
| multi/heldout | mean_cost_usd | 0.003113 | 0.00328 | ok |
| multi/heldout | judge_facts_covered | 0.7849 | 0.7527 | ok |
| multi/heldout | judge_no_false_claims | 0.9247 | 0.9355 | ok |
| multi/heldout | judge_no_leak | 1 | 1 | ok |
| multi/heldout | judge_professional_tone | 1 | 1 | ok |

Gate passed.
