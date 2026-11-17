import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const base = process.argv[2] ?? "http://127.0.0.1:8000/";
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1 });
  await page.goto(new URL("#v=traj", base).href);
  await page.waitForSelector("body[data-ready]");
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: fileURLToPath(new URL("../site/og.png", import.meta.url)),
    animations: "disabled",
  });
} finally {
  await browser.close();
}
