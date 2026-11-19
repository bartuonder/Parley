# Demo

The video in `docs/media/parley-demo.mp4` is a screen recording of the real console, running against the real model, with captions added on screen. It is about two minutes long and has no voice-over. Nothing in it is mocked: the tickets below go through the same service, graph, tools, policy search and critic as any other ticket.

## What it shows

| Scene | What to notice |
| --- | --- |
| Title card | What the project is, in one sentence |
| Inbox and overview | The inbox with a few earlier tickets, the key numbers, how a ticket is handled |
| A refund inside the limit | A customer wants to return shoes that are too small (order 95, $110). The "New ticket" dialog has this as a ready example. The steps appear live in plain words; the resolution says the refund was issued; the policy that applied is shown with its version |
| The trace | A developer view on its own tab: every model call and tool step with timing and masked arguments |
| A refund above the threshold | Torn shoes, order 160, $220. The agents stop and the ticket waits for a person |
| Approval queue | The request, the customer's message and the agents' reasoning; a decision resumes the paused workflow and the customer gets the follow-up |
| An injection attempt | The message tries to give the agents orders. It is treated as untrusted text, refunds are locked and the ticket goes to a human |
| Numbers card and closing card | The measured results with the same caveats as the README, then the repository and license |

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

The video, the README loop and the screenshots are scripted with Playwright (`scripts/demo`), so they can be regenerated after a change to the console. Use a freshly seeded world and a real model, with the service and the console running. Send two background tickets first so that the inbox is not empty (a parcel question from `sophie.demir.11@example.com` and a plan cancellation from `margaret.hamilton.2@example.com`).

```bash
cd scripts/demo
npm ci && npx playwright install chromium
cp facts.example.json facts.json        # the numbers shown on the metrics card
node record.mjs out facts.json          # out/demo.webm, 1920x1080, about 110 s
node gif.mjs out/gif                    # out/gif/loop.webm, the short README loop
node shots.mjs ../../docs/media         # needs the three demo tickets to exist
ffmpeg -i out/demo.webm -c:v libx264 -crf 22 -preset slow -pix_fmt yuv420p -movflags +faststart ../../docs/media/parley-demo.mp4
ffmpeg -i out/gif/loop.webm -vf "fps=12,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4" ../../docs/media/parley-demo.gif
```

The recording needs the model to answer, so it takes a few seconds per ticket and costs about two cents in model calls. The model does not always take the path the story needs (a large refund is handed over instead of waiting about half the time), so the script checks each step and fails loudly instead of recording a wrong story: reseed and record again until a take completes. The screenshots expect the three demo tickets in that state, so retry the setup until the large refund waits for approval.
