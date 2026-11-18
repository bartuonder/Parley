# Gate check, core and held-out, three repeats

Run 2026-11-18 after the prompt fixes of commit 41a7de1. The red-team scope did not finish: the provider credit ran out during it, so no red-team numbers exist for this code and no baseline was refreshed.

| Scope | Metric | Baseline | Current | Result |
| --- | --- | --- | --- | --- |
| multi/core | success_rate | 0.9879 | 0.9939 | ok |
| multi/core | pass_all | 0.9636 | 0.9818 | ok |
| multi/core | policy_violation_rate | 0 | 0 | ok |
| multi/core | unbacked_claim_rate | 0 | 0 | ok |
| multi/core | handover_accuracy | 0.9394 | 0.9273 | ok |
| multi/core | tool_precision | 0.9825 | 0.9828 | ok |
| multi/core | tool_recall | 0.9825 | 1 | ok |
| multi/core | mean_cost_usd | 0.002913 | 0.003021 | ok |
| multi/core | judge_facts_covered | 0.8242 | 0.8061 | ok |
| multi/core | judge_no_false_claims | 0.9576 | 0.9697 | ok |
| multi/core | judge_no_leak | 1 | 1 | ok |
| multi/core | judge_professional_tone | 1 | 1 | ok |
| multi/heldout | success_rate | 0.9892 | 0.9892 | ok |
| multi/heldout | pass_all | 0.9677 | 0.9677 | ok |
| multi/heldout | policy_violation_rate | 0 | 0 | ok |
| multi/heldout | unbacked_claim_rate | 0 | 0 | ok |
| multi/heldout | handover_accuracy | 0.9462 | 0.8495 | FAIL: worse than baseline by more than 0.05 |
| multi/heldout | tool_precision | 1 | 0.9512 | ok |
| multi/heldout | tool_recall | 0.9744 | 1 | ok |
| multi/heldout | mean_cost_usd | 0.00328 | 0.00323 | ok |
| multi/heldout | judge_facts_covered | 0.7527 | 0.7204 | ok |
| multi/heldout | judge_no_false_claims | 0.9355 | 0.9247 | ok |
| multi/heldout | judge_no_leak | 1 | 1 | ok |
| multi/heldout | judge_professional_tone | 1 | 1 | ok |

Gate failed: 1 check(s).
