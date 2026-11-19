# Service, console and deployment

Phase 8 turns the agent graph into something a person can use: an HTTP API with live progress, a web console with a trace viewer and an approval queue, and a Compose setup that starts all of it with one command.

## Running it

| Command | What it does |
| --- | --- |
| `make serve` | API on port 8000 with the real model (needs `PARLEY_LLM_API_KEY` and `make rag-index`) |
| `make serve-sim` | API with a simulated model (fixed answers, 0.4 s delay per call): no key, no cost |
| `make console-dev` | Next.js console on port 3000, talking to the API on port 8000 |
| `make stack` | Postgres, API and console in containers; open http://localhost:3000 |

Set `PARLEY_API_KEY` in `.env` to protect the API (the example file has a placeholder); without it the API is open, which is fine on localhost only. Compose does not need it for `make up`. `make stack` starts in simulated mode; set `PARLEY_LLM_MODE=live` and `PARLEY_LLM_API_KEY` for real model calls. On first start the API container applies the migrations and, when the database is empty, seeds the synthetic world (and builds the policy index in live mode). The demo clock is pinned to the world's reference date (`PARLEY_FIXED_NOW`), so ticket dates make sense against the seeded orders; production refuses a pinned clock.

## API

All routes except `/health` need the `X-API-Key` header when `PARLEY_API_KEY` is set (it is required when `PARLEY_ENV=prod`).

| Route | Purpose |
| --- | --- |
| `POST /tickets` | Accept a ticket (sender email, subject, body, optional id) and start working on it; returns 202. A repeated id returns the stored ticket instead of running it again. An unknown sender is 422. |
| `GET /tickets`, `GET /tickets/{id}` | List (filter by status) and read tickets: status, reply, cost, latency, actions, handovers, pending refunds. |
| `GET /tickets/{id}/events` | Server-sent events: every stored event is replayed, then new ones follow until the ticket resolves, fails or waits for approval. `Last-Event-ID` resumes. |
| `GET /tickets/{id}/trace` | The ticket's spans (model calls, tools, graph nodes) with redacted tool arguments and results. |
| `GET /approvals`, `POST /approvals/{id}/decision` | The queue of refunds above the approval threshold and the human decision that resumes the paused graph. |
| `GET /stats` | Tickets by status, total and mean cost, mean time. |

A ticket is stored first and processed in the background. Its status moves through `queued`, `running`, then `resolved`, `failed` or `awaiting_approval`. Events and status live in Postgres (`service_tickets`, `ticket_events`), so a stream can be replayed after a reconnect and several API processes could share it. The graph state of a paused refund lives in the LangGraph checkpointer, as before, so a decision still works after a restart.

Design points:

- **Bounded work.** At most `PARLEY_MAX_CONCURRENT_TICKETS` (default 8) tickets run at once; the rest wait as `queued`. The connection pool is sized from that number. The graph uses synchronous database sessions inside async code, and without the bound a burst of tickets exhausted the pool, which blocked the event loop that would have released it (the first load test stalled the service this way).
- **Restart safety.** On startup tickets left `queued` or `running` by a stopped process are marked `failed` ("interrupted by a restart"); a paused refund keeps waiting.
- **Tracing.** Spans go to Postgres from a background thread. In the service, tool arguments and results are recorded (personal data masked, 4,000 characters at most; switch off with `PARLEY_TRACE_CONTENT=false`). Prompts and replies are never put in spans. Evals do not record content.
- **Simulated model.** `PARLEY_LLM_MODE=simulated` answers with fixed text and a configurable delay so the console, CI and load tests need no key. It is refused when `PARLEY_ENV=prod`.

## Console

A Next.js app in `console/` (App Router, TypeScript, no UI library). Pages: the ticket list with a new-ticket form and cost and time totals, a ticket page (conversation, live steps from the event stream, trace waterfall with expandable tool arguments and results, approval panel), and the approval queue.

The browser only talks to the console's own `/api/...` route, which forwards a fixed set of paths to the API and adds the API key on the server, so the key never reaches the browser. Server-sent events pass through that route unbuffered.

Checks: `make console-check` (lint, typecheck, unit and component tests, production build); CI runs the same in a separate job.

## Load test

`python -m parley.service.loadtest --key KEY --tickets 200 --concurrency 20` submits tickets from seeded customers and follows each one until it resolves. Result against the containers on one developer machine (Docker Desktop), simulated model with 0.3 s per call, 8 ticket slots:

| Metric | Value |
| --- | --- |
| Tickets | 200 |
| Failed or timed out | 0 |
| Throughput | 4.0 tickets/s |
| Accept latency p50 / p95 | 19 ms / 302 ms |
| Time to reply p50 / p95 / max | 4.6 s / 5.6 s / 6.6 s |

This measures the service, database and tracing overhead, not the provider: with a real model a ticket takes about 6 seconds (see `docs/OBSERVABILITY.md`) and the provider's rate limits become the ceiling. The test found the stall described above; before the fix even two parallel clients timed out after a burst.

## Deployment

The two Dockerfiles (`docker/api.Dockerfile`, `docker/console.Dockerfile`) and the Compose file are the deployable unit: the same stack runs on any host with Docker. For a public host:

1. Set `PARLEY_ENV=prod`, a long random `PARLEY_API_KEY`, `PARLEY_LLM_MODE=live`, `PARLEY_LLM_API_KEY`, and a strong `POSTGRES_PASSWORD` (the settings class rejects prod without a key, with a pinned clock, or with the simulated model).
2. Put a TLS-terminating reverse proxy in front of the console port only; the API port does not need to be public because the console reaches it inside the Compose network.
3. The API key protects the API but there is no per-user login in the console; put it behind the proxy's own authentication before exposing it.

This has not been deployed to a cloud provider: no account or credentials were used, so the steps above are untested beyond the local Compose stack.

## Limits

- No login in the console; one shared API key.
- The graph's database access is synchronous, so one process serves a few concurrent tickets well and a large number only through the bound above; scale by running more API processes.
- The HTTP service ran end to end with the real model on a single ticket (a return question: 7 model calls including the router and critic, 8.6 s, $0.0037, the policy search and the trace with tool content working) and under load only in simulated mode. A load test with a real model was not run; it would be limited by the provider's rate limits and would cost money.
- Console behavior was checked by component tests, a production build and requests through its proxy; it was not opened in a browser during development.
