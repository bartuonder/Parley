# Evaluation report

Generated 2026-11-13 22:56 UTC. Agent model `gpt-4.1-mini`, router `gpt-4o-mini`. Cost of this run: $1.31.

## Reply quality (LLM judge)

| Scope | facts covered | no false claims | no leak | professional tone |
| --- | --- | --- | --- | --- |
| multi/core | 82.4% | 97.0% | 100.0% | 100.0% |
| multi/heldout | 78.5% | 92.5% | 100.0% | 100.0% |

## Ablation of the multi-agent graph

| Configuration | Set | Success | pass^k | Handover | Unbacked claims | Cost / ticket |
| --- | --- | --- | --- | --- | --- | --- |
| Full multi-agent graph | core | 100.0% | 100.0% | 96.4% | 0.0% | $0.0029 |
| Full multi-agent graph | heldout | 98.9% | 96.8% | 93.5% | 0.0% | $0.0031 |

## Judge calibration

Judge `gpt-4.1` against 50 labeled replies: facts covered 94% (kappa 0.87), no false claims 98% (kappa 0.93), no leak 98% (kappa 0.79), professional tone 92% (kappa 0.56). Full table in `reports/judge_calibration.md`.

## Regression gate

| Scope | Metric | Baseline | Current | Result |
| --- | --- | --- | --- | --- |
| multi/core | success_rate | 0.9955 | 1 | ok |
| multi/core | pass_all | 0.9818 | 1 | ok |
| multi/core | policy_violation_rate | 0 | 0 | ok |
| multi/core | unbacked_claim_rate | 0 | 0 | ok |
| multi/core | handover_accuracy | 0.9136 | 0.9636 | ok |
| multi/core | tool_precision | 0.987 | 1 | ok |
| multi/core | tool_recall | 1 | 1 | ok |
| multi/core | mean_cost_usd | 0.002657 | 0.002903 | ok |
| multi/core | judge_facts_covered | 0.8318 | 0.8242 | ok |
| multi/core | judge_no_false_claims | 0.9727 | 0.9697 | ok |
| multi/core | judge_no_leak | 1 | 1 | ok |
| multi/core | judge_professional_tone | 1 | 1 | ok |
| multi/heldout | success_rate | 0.9919 | 0.9892 | ok |
| multi/heldout | pass_all | 0.9677 | 0.9677 | ok |
| multi/heldout | policy_violation_rate | 0 | 0 | ok |
| multi/heldout | unbacked_claim_rate | 0 | 0 | ok |
| multi/heldout | handover_accuracy | 0.871 | 0.9355 | ok |
| multi/heldout | tool_precision | 1 | 1 | ok |
| multi/heldout | tool_recall | 0.9808 | 0.9744 | ok |
| multi/heldout | mean_cost_usd | 0.002956 | 0.003113 | ok |
| multi/heldout | judge_facts_covered | 0.7177 | 0.7849 | ok |
| multi/heldout | judge_no_false_claims | 0.9435 | 0.9247 | ok |
| multi/heldout | judge_no_leak | 1 | 1 | ok |
| multi/heldout | judge_professional_tone | 1 | 1 | ok |

Gate passed.
