# Synthetic world

`make seed` starts Postgres, applies migrations, validates the static data, and rebuilds the whole world from scratch. The output is deterministic: the same seed gives the same fingerprint, which is printed at the end.

## Pieces

| Piece | Where | Notes |
| --- | --- | --- |
| Schema | `src/parley/db/`, `migrations/` | customers, orders, order items, shipments, subscriptions, invoices, refunds, tickets |
| Seed generators | `src/parley/seed/` | one module and one RNG stream per domain; fixed reference date 2026-06-01 |
| Backend rules | `src/parley/backend/rules.py` | ground truth for eligibility and approval, see `BUSINESS_RULES.md` |
| Backend API | `src/parley/backend/api.py` | `make api`; refunds are idempotent and large ones wait for approval |
| Policies | `data/policies/` | 38 documents in 50 files, with versions, effective dates, and conflicts, see `POLICY_CONFLICTS.md` |
| Historical tickets | `tickets` table | about 670 template-based conversations that cite the policy version in force at the time |
| Eval scenarios | `data/eval/scenarios/` | 55 scenarios, each with its own minimal world and an expected database diff |

## Default size

200 customers, about 520 orders, 460 shipments, 130 subscriptions, 670 invoices, 54 refunds, and 670 tickets. The mix includes late, lost, returned, and stuck parcels, duplicate and failed charges, disputes, final-sale and digital items.

## Eval scenarios

A scenario describes a customer world relative to the reference date, a ticket, the expected state change, and a reference solution. The tests check three things for every scenario:

1. Running `reference_actions` through the backend produces exactly the expected diff.
2. Every `forbidden_actions` entry is refused by the backend, which proves the denial is rule-correct.
3. Every cited policy version is in force on the reference date.

Subjective expectations (`requires_human`, `reply_facts`) are not checked against the backend. They are scored in Phase 5.

Ticket text uses `{alias}` placeholders that are replaced with database ids when the world is built.

## Commands

```
make seed     # migrate and rebuild the world
make api      # run the backend API
make test     # unit, schema, seed, policy, and scenario tests
```
