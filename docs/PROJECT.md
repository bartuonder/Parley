# Parley

Eval-driven, multi-agent customer operations platform.

## Problem

Support teams spend most of their time on repetitive e-commerce and subscription tickets: refunds, shipping issues, cancellations, billing disputes. Resolving them correctly requires reading the right policy version, checking backend state, and acting within limits. LLM agents can automate this, but without measurement there is no way to know whether they are correct, compliant, cheap, or safe.

Parley builds an agent platform where quality is proven by measurement, not by demos.

## Approach

- A triage agent routes each ticket to a specialist (billing, shipping, subscription).
- Specialists combine RAG over versioned company policies with tool calls against a simulated backend.
- A policy critic reviews proposed actions; risky actions require human approval.
- Every run produces a reply, a full trace, and a cost record.
- A strict evaluation harness scores every change against a fixed scenario set.

## Target metrics

Targets are adjusted after the first baseline.

| Metric | Target |
| --- | --- |
| Task success (final DB state matches expected) | >= 80% |
| Policy violation rate | <= 2% |
| Reliability (pass^k, k=4) | >= 60% |
| Cost per resolved ticket | < $0.05 |
| Prompt injection attack success rate (after guardrails) | < 5% |

## Non-goals

- Production-grade integration with real payment, shipping, or CRM providers. The backend is simulated.
- Voice or other non-text channels.
- Multi-tenant isolation, billing, or user management for the platform itself.
- Training or fine-tuning foundation models. Small classifier experiments are optional and scoped to routing.
- Multi-language support. Tickets and policies are in English.
