import { readFileSync, renameSync } from "node:fs";
import { resolve } from "node:path";
import { BASE, expect, launch, send, sendExample } from "./lib.mjs";

const OUT = resolve(process.argv[2] ?? "out");
const FACTS = JSON.parse(readFileSync(process.argv[3] ?? "facts.json", "utf8"));

const h = await launch({ outDir: OUT, zoom: 1.25 });
const { page, say, click, hover, wait, card } = h;

try {
  // 1. title and the empty inbox
  await card("title", FACTS, 5200);
  await page.goto(BASE);
  await page.waitForSelector(".kpis");
  await say("Parley resolves support tickets with a team of agents. People approve the risky parts.", 4800);

  // 2. a refund inside the limit
  await say("A customer wants to return shoes that are too small.");
  await sendExample(h, "Return request");
  await send(h);
  await say("A router picks a team. The specialist reads the order and the policy. A critic reviews the plan.");
  await page.locator(".callout.tone-ok").waitFor();
  expect((await page.getByText("Refund of $110.00 issued").count()) > 0, "the refund was not issued");
  await say("The refund is issued, and the reply says only what actually happened.", 4200);
  if ((await page.getByText("Policy applied").count()) > 0) {
    await hover(page.getByText("Policy applied"));
    await say("The policy that applied is shown with its version.", 3200);
  }

  // 3. the trace for engineers
  await click(page.getByRole("tab", { name: "Trace" }));
  await page.waitForSelector(".trace-row");
  await say("For engineers, every model call and tool call is traced, with personal data masked.");
  await click(page.locator("button.trace-row", { hasText: "Checked refund eligibility" }).first());
  await wait(4200);
  await click(page.getByRole("tab", { name: "Overview" }));
  await say("");

  // 4. a refund above the threshold
  await say("A larger refund is different: $220 is above the approval threshold.");
  await sendExample(h, "Large refund");
  await send(h);
  const awaiting = page.getByText("Awaiting approval").first().waitFor().then(() => "awaiting").catch(() => "closed");
  const handed = page.getByText("Handed to a human").first().waitFor().then(() => "handed").catch(() => "closed");
  const result = await Promise.race([awaiting, handed]);
  expect(result === "awaiting", "the large refund was handed over instead of waiting");
  await say("The agents stop and wait. Nothing is paid until a person decides.", 4000);
  await click(page.getByRole("link", { name: /Approvals/ }));
  await page.waitForSelector(".approval-card");
  await say("The queue shows the request, the customer's message and the agents' reasoning.", 4200);
  await click(page.getByRole("button", { name: "Approve" }));
  await wait(400);
  await click(page.getByRole("button", { name: "Confirm decision" }));
  await page.getByText("Nothing is waiting").waitFor();
  await say("Approved. The paused workflow resumes from its checkpoint and tells the customer.", 3600);
  await click(page.getByRole("link", { name: /Inbox/ }));
  await page.waitForSelector(".row");
  await click(page.getByRole("link", { name: /Torn sole on my new shoes/ }));
  await page.getByText("After the decision").waitFor();
  await say("", 600);
  await wait(2600);

  // 5. an injection attempt
  await say("Now an attack: the message tries to give the agents orders.");
  await sendExample(h, "Injection attempt");
  await send(h);
  await page.getByText("Safety check triggered").waitFor({ timeout: 90000 });
  await say("The text is treated as data. Refunds are locked and a person takes over.", 3000);
  await hover(page.getByText("Safety check triggered"));
  await say("Across 108 attack runs with every guard on, none of them landed.", 4200);
  await say("");

  // 6. numbers and outro
  await card("metrics", FACTS, 9000);
  await card("outro", FACTS, 4200);
} catch (error) {
  console.error(String(error));
  const { video } = await h.finish("failed");
  void video;
  process.exit(1);
}

const { video } = await h.finish("demo");
const path = await video.path();
renameSync(path, resolve(OUT, "demo.webm"));
console.log("saved", resolve(OUT, "demo.webm"));
