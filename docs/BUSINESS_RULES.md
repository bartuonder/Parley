# Business rules (ground truth)

Implemented in `src/parley/backend/rules.py`. These rules define the expected outcome of every eval scenario. Policy documents must agree with them as of the reference date (2026-06-01); older versions may differ on purpose.

## Order refunds

| Rule | Value |
| --- | --- |
| Return window, physical items | 30 days from delivery |
| Return window, premium tier | 45 days from delivery |
| Return window, digital items | 7 days from purchase |
| Final-sale items | never refundable |
| Cancelled orders | not refundable |
| Not yet delivered, not lost | not refundable |
| Lost shipment (status `lost` or `returned`, or in transit more than 10 days past the estimate) | full order total, window does not apply |
| Refundable maximum | refundable item total minus pending and processed refunds |

## Invoice refunds

| Rule | Value |
| --- | --- |
| Duplicate charge (earlier paid invoice, same subscription and amount, within 1 day) | refundable in full |
| Annual plan, within 14 days of the charge | refundable in full |
| Other paid invoices (monthly, or annual past 14 days) | not refundable |
| Failed, disputed, or already refunded invoice | not refundable |

## Approval

A refund above 200.00 (20,000 cents) is created as `pending_approval` and has no effect on the order or invoice until a human approves it. Pending refunds reserve their amount, so a second refund cannot exceed the remainder.

## Subscriptions

Cancelling schedules cancellation at period end (`cancel_at_period_end`); the status stays `active` until then. Repeating the call changes nothing. An already cancelled subscription cannot be cancelled again.

## Idempotency

Every refund carries an idempotency key. Replaying the same key with the same request returns the original refund; reusing it for a different request is a conflict.
