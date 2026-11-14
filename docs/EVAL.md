# Evaluation harness

`make eval` runs everything below and writes one report, `reports/eval_report.md`. This page explains what is measured, how, and how far the numbers can be trusted. Agent architectures and their history are in `AGENT.md`.

## Scenario sets

| Set | Folder | Scenarios | Purpose |
| --- | --- | --- | --- |
| core | `data/eval/scenarios` | 55 | The development set. Prompts and critic rules were written while reading its failures. |
| heldout | `data/eval/heldout` | 31 | Written before any Phase 5 tuning, from the same policies and business rules but new situations and wording. It is reported separately and is not used to choose prompts. |
| dialogue | `data/eval/dialogue` | 14 | Multi-turn scenarios played against a simulated customer. |
| memory | `data/eval/memory` | 4 | Customer memory across tickets (Phase 4). |
| redteam | `data/eval/redteam` | 36 | Attacks (Phase 6): injection, exfiltration, manipulation. Scored by attack success, see `SECURITY.md`. |

Every scenario defines its own minimal world, the expected final database diff, a reference solution, and forbidden actions. Tests check the reference solution of every set against the backend rules, check that every forbidden action is refused, and replay every scenario through both agents with a scripted model, so the scoring pipeline itself is covered without any API call.

## What is measured

- **Task success:** the final database state matches the expected diff and a reply was written. The oracle is `backend/rules.py`, not a model.
- **Handover decision:** an escalation or a new pending-approval refund against `requires_human`. A scenario can mark its handover as already open (`handover_open`), as when a large refund is already waiting.
- **Policy violation:** a forbidden action was attempted or the reply cites a policy version that was not in force on the reference date.
- **Refund and cancellation precision and recall:** executed write calls against the reference solution.
- **Claimed-but-not-done:** the reply claims a refund, cancellation, or handover that did not happen (sentence-level pattern match).
- **Routing:** the router picked a specialist that can solve the ticket category (`ACCEPTED_SPECIALISTS`).
- **Reliability:** `pass^k`, the share of scenarios solved in all `k` runs. The suite uses `k = 4`.
- **Cost and latency** per ticket.
- **Reply quality (LLM judge):** four pass or fail criteria per reply: required facts covered, no false claims about actions, no leak of other customers' data, professional tone.

## User simulator

A dialogue scenario gives the simulated customer a persona, a goal, and facts it reveals only when asked. After each agent reply the simulator writes the next message or ends the conversation, up to four turns. Each turn is a fresh agent run on a ticket whose newest message comes first, followed by the history; the database state carries over, and refunds stay idempotent. The final state is scored like any other scenario. Simulator and judge cost count against the budget but not against the cost per ticket.

The dialogue set covers missing information (which order, which plan, which item), a customer who changes their mind, frustration and rudeness, a legal threat that appears only after a refusal, repeated insistence, a fake system override pasted in the second message, a wrong order number from another account, and two requests in one conversation.

## Judge and calibration

The judge is a stronger model than the agent (`PARLEY_JUDGE_MODEL`, default `gpt-4.1`; the agent is `gpt-4.1-mini`), to limit self-preference. `data/eval/judge/labels.yaml` holds 50 replies with labels for the four criteria: 36 real replies from the single and multi-agent runs (all failures first, then a seeded random sample of the rest) and 14 synthetic ones that inject a false promise, a data leak, or a bad tone into a real reply. `make judge-calibrate` compares the judge with the labels and writes `reports/judge_calibration.md`.

**The labels were written by the same assistant that built the harness, not by an independent person.** They are a reference to be reviewed, not ground truth, and the agreement below is agreement with those labels.

## Regression gate

`reports/baseline.json` holds the accepted metrics per scope (`multi/core`, `multi/heldout`). `make eval-gate` runs those scopes three times each with the judge and fails when a metric is worse than the baseline by more than its tolerance or breaks the project target. Tolerances (5 points for success, 8 for `pass^k`, 2 for policy violations and claimed-but-not-done, 25% for cost) sit above the run-to-run spread seen in the committed reports, about 2 points.

CI cannot call the API without a secret and spend, so it runs the offline gate instead: `make test` replays every scenario of every set through both agents with a scripted model and requires perfect scores, and the gate logic has its own tests. The live gate runs locally.

To accept new numbers as the baseline: `python -m parley.evals.gate --current reports/eval_suite.json --update-baseline`, reviewed like any other change.

## Ablation

`python -m parley.evals.agent_eval --arch multi --ablate critic|rewrite|router` turns one part of the graph off: the critic (rules and model check), the reply rewrite, or routing (every ticket goes to billing). The suite runs each on the core and held-out sets.

## Results

All numbers are for `gpt-4.1-mini` as the agent, `gpt-4o-mini` as the router, four runs per configuration. The full tables are in `reports/eval_report.md` and the per-scenario data in `reports/agent_*.json`.

### Single agent against multi-agent

| Set | | Task success (range) | `pass^4` | Claims an action that did not happen | Policy violation | Handover correct | Cost per ticket | p50 latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| core (55) | single | 93.2% (90.9 to 96.4) | 85.5% | 0.9% | 0.5% | 90.9% | $0.0019 | 4.1s |
| core (55) | multi | 99.5% (98.2 to 100) | 98.2% | 0.0% | 0.0% | 91.4% | $0.0027 | 7.1s |
| held-out (31) | single | 91.1% (87.1 to 96.8) | 83.9% | 4.0% | 4.0% | 88.7% | $0.0019 | 3.8s |
| held-out (31) | multi | 99.2% (96.8 to 100) | 96.8% | 0.0% | 0.0% | 87.1% | $0.0030 | 6.7s |
| dialogue (14) | single | 82.1% (78.6 to 85.7) | 64.3% | 0.0% | 0.0% | 92.9% | $0.0047 | 9.4s |
| dialogue (14) | multi | 98.2% (92.9 to 100) | 92.9% | 0.0% | 0.0% | 83.9% | $0.0084 | 18.9s |

The multi-agent graph is more reliable on every set and about 1.4 to 1.8 times as expensive, with about twice the latency. The single agent scores the same on the held-out set as on the core set, so the held-out set is not harder. The multi-agent graph scored lower on it at first, which is why the fixes below were needed; its numbers here are after those fixes.

### What the held-out and dialogue sets found

The first multi-agent run on the new sets, before any Phase 5 change to the agent (three runs, `reports/before_tuning`):

| Set | Task success before | After the fixes | Handover correct before | After |
| --- | --- | --- | --- | --- |
| core | 100.0% | 99.5% | 89.7% | 91.4% (96.4% after the last fix) |
| held-out | 91.4% | 99.2% | 89.2% | 87.1% (93.6% after the last fix) |
| dialogue | 85.7% | 98.2% | 76.2% | 83.9% |

The 8.6-point gap between core and held-out in the first run is the measurable cost of tuning on one set. The failures led to these changes, each a commit with a test:

- A lost parcel was denied because the model counted days itself: the prompt now says to call `check_refund_eligibility` and never work out day counts.
- Requests that policy denies (cancelling a dispatched order, pausing an annual plan) were handed to a human as "no tool can do this". The prompt now separates what a human may carry out from what policy denies, with an exception for insistence (a later run showed insistence handovers had dropped to zero without it).
- A refund plus a cancellation in one ticket failed because only the subscription specialist could propose a cancellation. All specialists can now.
- "Please cancel my subscription" with two active plans cancelled both, and "one of the items arrived damaged" refunded the whole order. Specialists now ask which record is meant, and the critic rejects several cancellations on a vague request.
- In later turns of a dialogue the reply denied refunds made in earlier turns, and some replies ended with an unfilled "[Your Name]". The responder now sees what earlier turns did and must not leave placeholders.

HLD-027 and HLD-028 were found or reworded after their first failure, and the DLG-002 and DLG-013 fixes were tuned on the dialogue set itself, so those four scenarios no longer count as unseen.

The last fix (insistence) came after the full suite. `make eval-gate` on that code, three runs, passed against the earlier baseline and was accepted as the new one (`reports/gate_run`, `reports/eval_gate.md`). That run used a prompt in which the insistence sentence was accidentally repeated three times. After the sentence was reduced to one (commit `6346883`), the gate was run again on the final prompt and passed: core 98.8% success and 96.4% `pass^3`, held-out 98.9% and 96.8%, handover correct 93.9% and 94.6%. That run is the accepted baseline.

| Scope | Task success | `pass^3` | Handover correct | Cost per ticket |
| --- | --- | --- | --- | --- |
| multi/core | 100.0% | 100.0% | 96.4% | $0.0029 |
| multi/heldout | 98.9% | 96.8% | 93.6% | $0.0031 |

### Ablation (two runs each)

| Configuration | core success | held-out success | core `pass^2` | Cost per ticket (core) |
| --- | --- | --- | --- | --- |
| Full graph (four runs) | 99.5% | 99.2% | 98.2% | $0.0027 |
| Without the critic | 93.6% | 96.8% | 90.9% | $0.0021 |
| Without the reply rewrite | 100.0% | 96.8% | 100.0% | $0.0025 |
| Without routing (always billing) | 100.0% | 98.4% | 100.0% | $0.0025 |

The critic is the one part with a clear effect: without it the core success falls by 6 points and the legal-threat and ambiguity rules disappear. The rewrite and the router show no gain here; the unbacked-claim rate stays at zero without the rewrite because the responder prompt already forbids invented actions. Two runs per configuration cannot resolve a difference of a few points, so these are candidates for simplification in Phase 7, not conclusions.

### Judge calibration

Against the 50 labels, overall agreement was 92.5% on the first prompt and 95.5% after one revision (the first prompt failed replies that mentioned existing data the record did not list, and one verdict format was unreadable). Per criterion after the revision: facts covered 94% (kappa 0.87), no false claims 98% (0.93), no leak 98% (0.79), professional tone 92% (0.56). The tone criterion is the weakest: the judge was too lenient on four replies, and almost all replies pass, so kappa stays moderate. The prompt was revised on the same 50 samples it is scored on, so these numbers are optimistic.

## What the numbers do not show

- The labels are by the assistant that built the harness; an independent review of `data/eval/judge/labels.yaml` is still open.
- The judge's "facts covered" is 72% to 84% for the multi-agent graph. Many replies do not state the hand-written phrases in `reply_facts`, and the judge is strict about that; read it as a relative number, not a defect rate.
- Handover correctness is about 87% to 96% depending on the set: the graph still hands over when policy denies a request outright (REF-014, SUB-003, HLD-013, HLD-030 in some runs).
- Sample sizes are small. The held-out set has 31 scenarios, the dialogue set 14, and four runs bound the variance only roughly.
- The simulator is one model playing 14 personas; real customers are less cooperative.
- The claimed-but-not-done metric is still a sentence-level pattern match; the judge's "no false claims" covers paraphrases but is itself 98% in agreement with the labels, not perfect.
