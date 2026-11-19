import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

export const BASE = process.env.CONSOLE_URL ?? "http://127.0.0.1:3000";
const CARDS = pathToFileURL(resolve("cards.html")).href;

// Caption bar and cursor are popovers so they stay above an open <dialog> (top layer).
const initScript = (zoom) => `(() => {
  const ZOOM = ${zoom};
  const apply = () => {
    document.documentElement.style.zoom = String(ZOOM);
    if (document.getElementById("__cap")) return;
    const style = document.createElement("style");
    style.textContent = \`
      #__cap { position: fixed; inset: auto; left: 50%; bottom: 26px; top: auto; right: auto; margin: 0; transform: translateX(-50%);
        max-width: 860px; padding: 12px 22px; border: 0; border-radius: 12px; background: rgba(15,18,22,.95); color: #fff;
        font: 500 19px/1.4 "Inter Variable", system-ui, sans-serif; border-left: 4px solid #818cf8;
        box-shadow: 0 8px 30px rgba(0,0,0,.35); opacity: 0; transition: opacity .35s ease; pointer-events: none; overflow: visible; }
      #__cap.on { opacity: 1; }
      #__cur { position: fixed; inset: auto; margin: 0; width: 20px; height: 20px; border: 2px solid #4f46e5; padding: 0; border-radius: 50%;
        background: rgba(255,255,255,.96); box-shadow: 0 2px 8px rgba(0,0,0,.4); pointer-events: none; transition: transform .12s ease; overflow: visible; }
      #__cur.down { transform: scale(.7); background: #818cf8; }
    \`;
    document.head.appendChild(style);
    const cap = document.createElement("div"); cap.id = "__cap"; cap.setAttribute("popover", "manual");
    const cur = document.createElement("div"); cur.id = "__cur"; cur.setAttribute("popover", "manual");
    cur.style.left = "-60px"; cur.style.top = "-60px";
    document.body.append(cap, cur);
    const top = () => { for (const el of [cap, cur]) { try { el.hidePopover(); el.showPopover(); } catch {} } };
    top();
    window.__top = top;
    window.__cap = (t) => { if (t) { cap.textContent = t; cap.classList.add("on"); } else { cap.classList.remove("on"); } top(); };
    document.addEventListener("mousemove", (e) => { cur.style.left = (e.clientX / ZOOM - 4) + "px"; cur.style.top = (e.clientY / ZOOM - 4) + "px"; }, true);
    document.addEventListener("mousedown", () => cur.classList.add("down"), true);
    document.addEventListener("mouseup", () => cur.classList.remove("down"), true);
    new MutationObserver(top).observe(document.body, { subtree: true, attributes: true, attributeFilter: ["open"] });
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", apply); else apply();
})();`;

export async function launch({ outDir, zoom = 1.25, size = { width: 1920, height: 1080 } }) {
  mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: size,
    recordVideo: { dir: outDir, size },
    colorScheme: "light",
  });
  await context.addInitScript(initScript(zoom));
  const page = await context.newPage();
  page.setDefaultTimeout(120000);

  const wait = (ms) => page.waitForTimeout(ms);
  const say = async (text, ms = 0) => {
    await page.evaluate((t) => window.__cap && window.__cap(t), text);
    if (ms) await wait(ms);
  };
  const card = async (scene, facts, ms) => {
    await page.goto(`${CARDS}?scene=${scene}&facts=${encodeURIComponent(JSON.stringify(facts))}`);
    await say("");
    await wait(ms);
  };
  const hover = async (locator) => {
    await locator.scrollIntoViewIfNeeded();
    const box = await locator.boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 26 });
    await wait(240);
  };
  const click = async (locator) => {
    await hover(locator);
    await page.mouse.down();
    await wait(90);
    await page.mouse.up();
  };
  const type = async (locator, text, delay = 24) => {
    await click(locator);
    await locator.fill("");
    await locator.pressSequentially(text, { delay });
  };
  const finish = async (name) => {
    const video = page.video();
    await context.close();
    await browser.close();
    return { video, name };
  };
  return { browser, context, page, wait, say, card, hover, click, type, finish };
}

export async function sendExample(h, label) {
  const { page, click } = h;
  await click(page.getByRole("button", { name: "New ticket" }));
  await page.waitForSelector("dialog[open]");
  await h.wait(500);
  await click(page.getByRole("button", { name: new RegExp(label) }));
  await h.wait(1300);
}

export async function send(h) {
  await h.click(h.page.getByRole("button", { name: "Send to the agents" }));
  await h.page.waitForSelector(".timeline");
}

export function expect(condition, message) {
  if (!condition) throw new Error(`take failed: ${message}`);
}
