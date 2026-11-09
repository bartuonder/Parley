# Deliberate policy conflicts

The corpus in `data/policies/` contains conflicts on purpose, to test retrieval and reasoning. The reference date is 2026-06-01. The correct resolution in every case matches `docs/BUSINESS_RULES.md`.

| Topic | Conflicting documents | Correct resolution on the reference date |
| --- | --- | --- |
| Return window | POL-REF-001 v1 (14 days), v2 (30 days), v3 (21 days from 2026-07-01) | v2, 30 days. v1 is superseded and v3 is not in force yet. |
| Return window for premium members | POL-REF-001 (30 days) and POL-REF-002 (45 days) | POL-REF-002 wins for premium customers, because it is more specific and declares precedence. |
| Holiday promotion | POL-PRM-001 (60 days) and POL-REF-001 | POL-PRM-001 expired on 2025-12-31. Use POL-REF-001. |
| Spring sale wording | POL-PRM-002 and POL-REF-003 | Clearance items stay final sale. Other sale items follow the standard window. |
| Final-sale scope | POL-REF-003 v1 (clearance only), v2 (also personalized items) | v2. |
| Digital goods | POL-REF-004 v1 (never refundable), v2 (7 days) | v2. |
| Lost shipment threshold | POL-REF-005 v1 (14 days), v2 (10 days), POL-SHP-003 | v2, more than 10 days past the estimate. |
| Approval threshold | POL-REF-007 v1 (500.00), v2 (200.00) | v2, above 200.00. |
| Cancellation timing | POL-SUB-002 v1 (immediate, pro rata), v2 (period end) | v2. No partial-period refunds. |
| Annual cooling-off | POL-SUB-003 v1 (30 days), v2 (14 days) | v2. |
| Duplicate charges | POL-BIL-001 v1 (1 hour, investigation), v2 (24 hours, immediate) | v2. Only the later invoice is refundable. |
| Address changes and order cancellation | POL-SHP-004 v1 (until delivery), v2 (before dispatch, human handles cancellation) | v2. |
| Prices | POL-SUB-001 v1 and v2 | v2. |
| Which version applies | POL-GEN-005 | The version in force on the request date, not the order date. |

Regional policies (POL-REF-008, POL-SHP-006, POL-SHP-007, POL-BIL-004) add legal and logistics notes. None of them changes a refund outcome, so the backend rules are region-independent.
