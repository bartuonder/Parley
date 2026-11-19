# Demo

The video in `docs/media/parley-demo.mp4` is a screen recording of the real console, running against the real model, with captions added on screen. It is about two minutes long and has no voice-over. Nothing in it is mocked: the tickets below go through the same service, graph, tools, policy search and critic as any other ticket.

## What it shows

| Time | Scene | What to notice |
| --- | --- | --- |
| 0:00 | Title card | What the project is, in one sentence |
| 0:05 | Console home | Stats, ticket list, the new-ticket form |
| 0:10 | A refund inside the limit | A customer wants to return shoes that are too small (order 95, $110). The router picks a specialist, which reads the order and the policy, proposes a refund; the critic approves; the refund is issued |
| 0:50 | The trace | Every step has a span: model calls, tool calls with their arguments and results, time and cost |
| 1:00 | A refund above the threshold | Torn shoes, order 160, $220. The agents stop and the ticket waits |
| 1:10 | Approval queue | A human approves; the paused graph resumes from its checkpoint and the customer gets the follow-up |
| 1:35 | An injection attempt | The ticket text tries to give the agent orders. It is fenced as data and scanned; refunds and cancellations are locked and the ticket goes to a human |
| 1:50 | Numbers card | The measured results, with the same caveats as the README |
| 2:00 | Closing card | Repository and license |

## Run the same tickets yourself

```bash
make up && make seed            # a clean world
make rag-index                  # policy index (first time only)
make serve                      # real model; or make serve-sim for fixed answers
make console-install && make console-dev
make demo                       # sends the three tickets of the video
```

`make demo` prints, for each ticket, the final status, cost, time and the actions the agents took. The refund ticket resolves, the second ticket ends as `awaiting_approval` (open the approval queue in the console and decide it), and the third is handed to a human with the guard flags shown on its page.

The seeded world is dated 2026-06-01, so the service runs with `PARLEY_FIXED_NOW` pinned to that date (the example `.env` does this). That is why the console shows absolute times and why every ticket carries the same timestamp.

## Record it again

The recording and the README screenshots are scripted with Playwright (`scripts/demo`), so they can be regenerated after a change to the console.

```bash
cd scripts/demo
npm ci && npx playwright install chromium
cp facts.example.json facts.json        # the numbers shown on the metrics card
# with the service and the console running on a freshly seeded world:
node record.mjs out facts.json          # out/demo.webm, 1920x1080
node shots.mjs ../../docs/media         # needs the three demo tickets to exist
ffmpeg -i out/demo.webm -c:v libx264 -crf 22 -preset slow -pix_fmt yuv420p -movflags +faststart ../../docs/media/parley-demo.mp4
```

The recording needs the model to answer, so it takes a few seconds per ticket and costs about two cents in model calls. If a take goes wrong (a model answer that does not trigger the approval, for example), reseed and record again; the script fails loudly instead of recording a wrong story.
