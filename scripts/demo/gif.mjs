import { renameSync } from "node:fs";
import { resolve } from "node:path";
import { BASE, expect, launch, send, sendExample } from "./lib.mjs";

// A short loop for the README: send a ticket, watch the agents work, see the outcome.
const OUT = resolve(process.argv[2] ?? "gif");
const h = await launch({ outDir: OUT, zoom: 1, size: { width: 1440, height: 810 } });
const { page, say, hover, wait } = h;

try {
  await page.goto(BASE);
  await page.waitForSelector(".row");
  await say("A support ticket arrives. Parley's agents pick it up.", 1800);
  await sendExample(h, "Return request");
  await send(h);
  await say("Live steps: routing, investigation, policy review.");
  await page.locator(".callout.tone-ok").waitFor();
  expect((await page.getByText("Refund of $110.00 issued").count()) > 0, "the refund was not issued");
  await say("Refund issued. The reply says only what actually happened.");
  await hover(page.getByText("What the agents did"));
  await wait(2600);
} catch (error) {
  console.error(String(error));
  await h.finish("failed");
  process.exit(1);
}

const { video } = await h.finish("gif");
renameSync(await video.path(), resolve(OUT, "loop.webm"));
console.log("saved", resolve(OUT, "loop.webm"));
