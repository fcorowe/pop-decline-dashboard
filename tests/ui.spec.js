// End-to-end tests: run on desktop and phone profiles (see playwright.config.js).
const { test, expect } = require("@playwright/test");

const ready = async (page, hash = "") => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await page.goto("./" + hash);
  await page.waitForSelector("body[data-ready]", { timeout: 15000 });
  return errors;
};

test("loads the map with every area and no errors", { tag: "@smoke" }, async ({ page }) => {
  const errors = await ready(page);
  const n = await page.locator("#map path.region").count();
  expect(n).toBe(2042);
  expect(errors).toEqual([]);
});

test("first meaningful render is fast", async ({ page }) => {
  const t0 = Date.now();
  await ready(page);
  expect(Date.now() - t0).toBeLessThan(5000);
});

test("tabs switch the map encoding and legend", async ({ page }) => {
  await ready(page);
  await expect(page.locator("#legend h2")).toHaveText(/Trajectory/);
  await page.click("#tab-sig");
  await expect(page.locator("#legend h2")).toHaveText(/signature/i);
  await expect(page).toHaveURL(/v=sig/);
  await page.click("#tab-year");
  await expect(page.locator("#yearbar")).toBeVisible();
  await expect(page.locator("#legend h2")).toHaveText(/2001/);
});

test("year slider updates map and label", async ({ page }) => {
  await ready(page, "#v=year");
  await page.locator("#year").fill("2016");
  await expect(page.locator("#yearout")).toHaveText("2016");
  await expect(page.locator("#legend h2")).toHaveText(/2016/);
  await expect(page).toHaveURL(/y=2016/);
});

test("legend chip isolates a category", async ({ page }) => {
  await ready(page);
  await page.locator("#legend .chip").first().click();
  await expect(page.locator("#legend .chip").first()).toHaveAttribute("aria-pressed", "true");
  const dim = await page.locator("#map path.region.dim").count();
  expect(dim).toBeGreaterThan(1500);
  await page.locator("#legend .chip").first().click();
  expect(await page.locator("#map path.region.dim").count()).toBe(0);
});

test("search finds a region and shows its story", async ({ page }) => {
  await ready(page);
  await page.fill("#q", "Dibër");
  await page.press("#q", "Enter");
  await expect(page.locator(".place h2.name")).toHaveText("Dibër");
  await expect(page.locator("#seq svg rect.cell")).toHaveCount(18);
  await expect(page.locator("#drivers svg")).toBeVisible();
  await expect(page).toHaveURL(/r=\d+/);
});

test("deep link restores mode, year and region", { tag: "@smoke" }, async ({ page }) => {
  await ready(page, "#v=year&y=2011&r=7");
  await expect(page.locator("#tab-year")).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("#yearout")).toHaveText("2011");
  await expect(page.locator(".place h2.name")).toHaveText("Brest");
});

test("growing areas explain why they have no decline data", async ({ page }) => {
  await ready(page, "#r=0");
  await expect(page.locator(".place")).toContainText("grew overall");
});

test("tapping a region selects it", async ({ page, isMobile }) => {
  await ready(page);
  const box = await page.locator("#map").boundingBox();
  // click near the centre of the map (central Europe)
  await page.mouse.click(box.x + box.width * 0.55, box.y + box.height * 0.6);
  await expect(page.locator(".place h2.name")).toBeVisible();
  if (isMobile) await expect(page.locator("#pill")).toBeVisible();
  // all three tabs fully visible on every screen
  for (const t of ["#tab-traj", "#tab-year", "#tab-sig"]) {
    const b = await page.locator(t).boundingBox();
    expect(b.x + b.width).toBeLessThanOrEqual(page.viewportSize().width + 1);
  }
});

test("layout fits the screen without horizontal scrolling", async ({ page }, info) => {
  if (info.project.name === "small-phone") await page.setViewportSize({ width: 320, height: 667 });
  await ready(page, "#r=7");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});

test("primary controls meet the 44px touch-target minimum", async ({ page }) => {
  await ready(page, "#v=year");
  for (const sel of ["#q", "#tab-traj", "#tab-year", "#tab-sig", "#zin", "#zout", "#zreset", "#play", "#legend .chip:first-child"]) {
    const b = await page.locator(sel).boundingBox();
    expect(b.height, sel).toBeGreaterThanOrEqual(43.5);
  }
});

test("body text is readable (≥ 14px) and uses the hyperlegible font", async ({ page }) => {
  await ready(page);
  const r = await page.evaluate(async () => {
    await document.fonts.ready;
    const lead = document.querySelector(".lead");
    return { size: parseFloat(getComputedStyle(lead).fontSize), loaded: document.fonts.check("16px Atkinson") };
  });
  expect(r.size).toBeGreaterThanOrEqual(14);
  expect(r.loaded).toBe(true);
});

test("total transfer stays within the lightweight budget", async ({ page }) => {
  let bytes = 0;
  page.on("response", async (res) => { try { bytes += (await res.body()).length; } catch {} });
  await ready(page);
  // uncompressed; typical static hosts gzip this to ~0.5 MB
  expect(bytes).toBeLessThan(2.6 * 1024 * 1024);
});


test("live assets resolve under the project path", { tag: "@smoke" }, async ({ page }) => {
  const errors = await ready(page);
  expect(errors).toEqual([]);
  const files = ["og.png", "favicon.svg", "data/regions.csv", "data/LICENSE.md"];
  for (const file of files) {
    const response = await page.request.get(new URL(file, page.url()).href);
    expect(response.ok(), file).toBe(true);
  }
});
