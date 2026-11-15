# Evaluation report

Generated 2026-11-15 11:22 UTC. Agent model `gpt-4.1-mini`, router `gpt-4o-mini`. Cost of this run: $1.13.

## Reply quality (LLM judge)

| Scope | facts covered | no false claims | no leak | professional tone |
| --- | --- | --- | --- | --- |
| multi/core | 81.8% | 93.6% | 100.0% | 100.0% |
| multi/heldout | 72.6% | 91.9% | 100.0% | 100.0% |

## Ablation of the multi-agent graph

| Configuration | Set | Success | pass^k | Handover | Unbacked claims | Cost / ticket |
| --- | --- | --- | --- | --- | --- | --- |
| Full multi-agent graph | core | 97.3% | 94.5% | 94.5% | 0.0% | $0.0028 |
| Full multi-agent graph | heldout | 100.0% | 100.0% | 88.7% | 0.0% | $0.0031 |

## Judge calibration

Judge `gpt-4.1` against 50 labeled replies: facts covered 94% (kappa 0.87), no false claims 98% (kappa 0.93), no leak 98% (kappa 0.79), professional tone 92% (kappa 0.56). Full table in `reports/judge_calibration.md`.

## Regression gate

| Scope | Metric | Baseline | Current | Result |
| --- | --- | --- | --- | --- |
| multi/core | success_rate | 0.9879 | 0.9727 | ok |
| multi/core | pass_all | 0.9636 | 0.9455 | ok |
| multi/core | policy_violation_rate | 0 | 0 | ok |
| multi/core | unbacked_claim_rate | 0 | 0 | ok |
| multi/core | handover_accuracy | 0.9394 | 0.9455 | ok |
| multi/core | tool_precision | 0.9825 | 1 | ok |
| multi/core | tool_recall | 0.9825 | 0.9211 | FAIL: worse than baseline by more than 0.05 |
| multi/core | mean_cost_usd | 0.002913 | 0.002785 | ok |
| multi/core | judge_facts_covered | 0.8242 | 0.8182 | ok |
| multi/core | judge_no_false_claims | 0.9576 | 0.9364 | ok |
| multi/core | judge_no_leak | 1 | 1 | ok |
| multi/core | judge_professional_tone | 1 | 1 | ok |
| multi/heldout | success_rate | 0.9892 | 1 | ok |
| multi/heldout | pass_all | 0.9677 | 1 | ok |
| multi/heldout | policy_violation_rate | 0 | 0 | ok |
| multi/heldout | unbacked_claim_rate | 0 | 0 | ok |
| multi/heldout | handover_accuracy | 0.9462 | 0.8871 | FAIL: worse than baseline by more than 0.05 |
| multi/heldout | tool_precision | 1 | 0.963 | ok |
| multi/heldout | tool_recall | 0.9744 | 1 | ok |
| multi/heldout | mean_cost_usd | 0.00328 | 0.003135 | ok |
| multi/heldout | judge_facts_covered | 0.7527 | 0.7258 | ok |
| multi/heldout | judge_no_false_claims | 0.9355 | 0.9194 | ok |
| multi/heldout | judge_no_leak | 1 | 1 | ok |
| multi/heldout | judge_professional_tone | 1 | 1 | ok |
| multi/redteam | success_rate | 1 | 0.9583 | ok |
| multi/redteam | pass_all | 1 | 0.9444 | ok |
| multi/redteam | policy_violation_rate | 0 | 0 | ok |
| multi/redteam | unbacked_claim_rate | 0.02778 | 0 | ok |
| multi/redteam | handover_accuracy | 1 | 1 | ok |
| multi/redteam | tool_precision | 1 | 1 | ok |
| multi/redteam | tool_recall | 1 | 0.5 | FAIL: worse than baseline by more than 0.05 |
| multi/redteam | mean_cost_usd | 0.004071 | 0.003687 | ok |
| multi/redteam | attack_success_rate | 0 | 0 | ok |

Gate failed: 3 check(s).
