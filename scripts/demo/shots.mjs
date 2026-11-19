import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

// Takes the README screenshots of a console that already holds the demo tickets
// (run `make demo` against a clean database first).
const OUT = resolve(process.argv[2] ?? "shots");
const BASE = process.env.CONSOLE_URL ?? "http://127.0.0.1:3000";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1360, height: 900 },
  deviceScaleFactor: 2,
  colorScheme: "light",
});
const page = await context.newPage();
const problems = [];
page.on("console", (m) => ["error", "warning"].includes(m.type()) && problems.push(m.text()));
page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));

async function open(title) {
  await page.goto(BASE);
  await page.waitForSelector("table");
  await page.getByRole("link", { name: title }).click();
  await page.waitForSelector(".trace-row");
  await page.waitForTimeout(700);
}

await page.goto(BASE);
await page.waitForSelector("table");
await page.waitForTimeout(600);
await page.screenshot({ path: `${OUT}/console-home.png`, clip: { x: 0, y: 0, width: 1360, height: 560 } });

await open("Trail running shoes are too small");
await page.locator("button.trace-row", { hasText: "tool.check_refund_eligibility" }).first().click();
await page.evaluate(() => window.scrollTo(0, 0));
await page.waitForTimeout(300);
await page.screenshot({ path: `${OUT}/ticket-trace.png`, fullPage: true, clip: { x: 0, y: 0, width: 1360, height: 1380 } });

await page.goto(`${BASE}/approvals`);
await page.waitForSelector(".approval");
await page.getByRole("button", { name: "Approve" }).click();
await page.waitForTimeout(300);
await page.screenshot({ path: `${OUT}/approvals.png`, clip: { x: 0, y: 0, width: 1360, height: 420 } });

await open("Question about my order");
await page.waitForTimeout(300);
await page.screenshot({ path: `${OUT}/injection.png`, clip: { x: 0, y: 0, width: 1360, height: 900 } });

console.log("browser problems:", problems);
await browser.close();
