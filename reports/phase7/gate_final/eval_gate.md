# Evaluation report

Generated 2026-11-15 12:27 UTC. Agent model `gpt-4.1-mini`, router `gpt-4o-mini`. Cost of this run: $0.59.

## Reply quality (LLM judge)

| Scope | facts covered | no false claims | no leak | professional tone |
| --- | --- | --- | --- | --- |
| multi/core | 85.5% | 94.5% | 100.0% | 100.0% |
| multi/heldout | 67.7% | 90.3% | 100.0% | 100.0% |

## Ablation of the multi-agent graph

| Configuration | Set | Success | pass^k | Handover | Unbacked claims | Cost / ticket |
| --- | --- | --- | --- | --- | --- | --- |
| Full multi-agent graph | core | 100.0% | n/a | 92.7% | 0.0% | $0.0032 |
| Full multi-agent graph | heldout | 96.8% | n/a | 90.3% | 0.0% | $0.0031 |

## Judge calibration

Judge `gpt-4.1` against 50 labeled replies: facts covered 94% (kappa 0.87), no false claims 98% (kappa 0.93), no leak 98% (kappa 0.79), professional tone 92% (kappa 0.56). Full table in `reports/judge_calibration.md`.

## Regression gate

| Scope | Metric | Baseline | Current | Result |
| --- | --- | --- | --- | --- |
| multi/core | success_rate | 0.9879 | 1 | ok |
| multi/core | pass_all | 0.9636 | n/a | FAIL: missing from the current run |
| multi/core | policy_violation_rate | 0 | 0 | ok |
| multi/core | unbacked_claim_rate | 0 | 0 | ok |
| multi/core | handover_accuracy | 0.9394 | 0.9273 | ok |
| multi/core | tool_precision | 0.9825 | 1 | ok |
| multi/core | tool_recall | 0.9825 | 1 | ok |
| multi/core | mean_cost_usd | 0.002913 | 0.003181 | ok |
| multi/core | judge_facts_covered | 0.8242 | 0.8545 | ok |
| multi/core | judge_no_false_claims | 0.9576 | 0.9455 | ok |
| multi/core | judge_no_leak | 1 | 1 | ok |
| multi/core | judge_professional_tone | 1 | 1 | ok |
| multi/heldout | success_rate | 0.9892 | 0.9677 | ok |
| multi/heldout | pass_all | 0.9677 | n/a | FAIL: missing from the current run |
| multi/heldout | policy_violation_rate | 0 | 0 | ok |
| multi/heldout | unbacked_claim_rate | 0 | 0 | ok |
| multi/heldout | handover_accuracy | 0.9462 | 0.9032 | ok |
| multi/heldout | tool_precision | 1 | 1 | ok |
| multi/heldout | tool_recall | 0.9744 | 0.9231 | FAIL: worse than baseline by more than 0.05 |
| multi/heldout | mean_cost_usd | 0.00328 | 0.003063 | ok |
| multi/heldout | judge_facts_covered | 0.7527 | 0.6774 | FAIL: worse than baseline by more than 0.05 |
| multi/heldout | judge_no_false_claims | 0.9355 | 0.9032 | ok |
| multi/heldout | judge_no_leak | 1 | 1 | ok |
| multi/heldout | judge_professional_tone | 1 | 1 | ok |
| multi/redteam | success_rate | 1 | 0.9722 | ok |
| multi/redteam | pass_all | 1 | n/a | FAIL: missing from the current run |
| multi/redteam | policy_violation_rate | 0 | 0 | ok |
| multi/redteam | unbacked_claim_rate | 0.02778 | 0 | ok |
| multi/redteam | handover_accuracy | 1 | 1 | ok |
| multi/redteam | tool_precision | 1 | 1 | ok |
| multi/redteam | tool_recall | 1 | 0.6667 | FAIL: worse than baseline by more than 0.05 |
| multi/redteam | mean_cost_usd | 0.004071 | 0.003779 | ok |
| multi/redteam | attack_success_rate | 0 | 0 | ok |

Gate failed: 6 check(s).
