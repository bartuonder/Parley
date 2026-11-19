import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

// README screenshots of a console that already holds the demo tickets
// (see docs/DEMO.md: a refund, a large refund waiting for approval, an injection attempt).
const OUT = resolve(process.argv[2] ?? "shots");
const BASE = process.env.CONSOLE_URL ?? "http://127.0.0.1:3000";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  colorScheme: "light",
});
const page = await context.newPage();
const problems = [];
page.on("console", (m) => ["error", "warning"].includes(m.type()) && problems.push(m.text()));
page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
const shot = (name, clip) => page.screenshot({ path: `${OUT}/${name}.png`, ...(clip ? { clip } : {}) });

async function open(title) {
  await page.goto(BASE);
  await page.waitForSelector(".row");
  await page.getByRole("link", { name: new RegExp(title) }).click();
  await page.waitForSelector(".thread");
  await page.waitForTimeout(900);
}

await page.goto(BASE);
await page.waitForSelector(".row");
await page.waitForTimeout(700);
await shot("console-home");

await open("Trail running shoes are too small");
await shot("ticket");

await page.getByRole("tab", { name: "Trace" }).click();
await page.waitForSelector(".trace-row");
await page.locator("button.trace-row", { hasText: "Checked refund eligibility" }).first().click();
await page.waitForTimeout(300);
await shot("trace");

await page.goto(`${BASE}/approvals`);
await page.waitForSelector(".approval-card");
await page.getByRole("button", { name: "Approve" }).click();
await page.waitForTimeout(300);
await shot("approvals", { x: 248, y: 0, width: 1192, height: 620 });

await open("Question about my order");
await shot("injection");

await page.goto(BASE);
await page.getByRole("button", { name: "New ticket" }).click();
await page.getByRole("button", { name: /Large refund/ }).click();
await page.waitForTimeout(1200);
await shot("composer");

console.log("browser problems:", problems);
await browser.close();
