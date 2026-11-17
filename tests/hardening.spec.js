const fs = require("node:fs");
const path = require("node:path");
const { test, expect } = require("@playwright/test");

test("4× CPU throttling keeps Android start and pinch zoom responsive", async ({ page }, info) => {
  test.skip(info.project.name !== "android");
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  await page.addInitScript(() => {
    window.timings = { tasks: [] };
    const ready = new MutationObserver(() => {
      if (!document.body?.dataset.ready) return;
      window.timings.ready = performance.now();
      ready.disconnect();
    });
    ready.observe(document, { attributes: true, subtree: true, attributeFilter: ["data-ready"] });
    new PerformanceObserver((list) => {
      window.timings.tasks.push(...list.getEntries().map(({ startTime, duration }) => ({ startTime, duration })));
    }).observe({ type: "longtask", buffered: true });
  });
  await page.goto("./");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "1");
  const startup = await page.evaluate(() => window.timings.ready);
  expect(startup, "Navigation start to data-ready").toBeLessThan(4000);
  const box = await page.locator("#map").boundingBox();
  const x = Math.round(box.x + box.width / 2), y = Math.round(box.y + box.height / 2);
  const touches = (r) => [{ x: x - r, y, id: 0 }, { x: x + r, y, id: 1 }];
  const start = await page.evaluate(() => performance.now());
  await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: touches(28) });
  for (const distance of [34, 40, 46, 52, 58, 64]) {
    await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: touches(distance) });
  }
  await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  await expect(page.locator("#map svg > g")).toHaveAttribute("transform", /scale\(2\./);
  await page.evaluate(() => new Promise((resolve) => setTimeout(resolve, 220)));
  const longest = await page.evaluate((t) =>
    Math.max(0, ...window.timings.tasks.filter(({ startTime, duration }) => startTime + duration > t)
      .map(({ duration }) => duration)), start);
  expect(longest, "Longest main-thread task during pinch").toBeLessThan(200);
  await info.attach("performance", { body: JSON.stringify({ startupMs: startup, longestPinchTaskMs: longest }), contentType: "application/json" });
});

test("far-east Russia stays compact when zooming out and panning east", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("./");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "1");
  const map = page.locator("#map svg");
  const chukot = map.locator("path.region");
  const getBounds = (id) => chukot.evaluateAll((shapes, id) => {
    const shape = shapes.find((p) => p.__data__.properties.id === id);
    const { x, y, width, height } = shape.getBBox();
    return { x, y, width, height };
  }, id);
  const bounds = await getBounds(264);
  const island = await getBounds(95);
  expect(island.width).toBeGreaterThan(0);
  expect(island.height).toBeGreaterThan(0);
  const box = await map.boundingBox();
  expect(bounds.width / box.width).toBeLessThan(0.4);
  expect(bounds.height / box.height).toBeLessThan(0.35);
  await page.getByRole("button", { name: "Zoom out" }).click();
  const x = box.x + 0.7 * box.width, y = box.y + 0.5 * box.height;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x - 0.35 * box.width, y, { steps: 8 });
  await page.mouse.up();
  await expect(map.locator("g").first()).toHaveAttribute("transform", /scale\(0\.6\)/);
  const extent = await map.locator("g").first().evaluate((g) => {
    const chukot = [...g.querySelectorAll("path.region")].find((p) => p.__data__.properties.id === 264);
    return chukot.getBoundingClientRect().toJSON();
  });
  expect(extent.width / box.width).toBeLessThan(0.25);
});

test("optional characteristics are absent by default and render from the supplied fixture", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop");
  await page.goto("./#v=sig&r=7");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "1");
  await expect(page.getByRole("heading", { name: "What sort of place is this?" })).toHaveCount(0);
  await page.evaluate(() => { location.hash = "#v=sig&r=300"; });
  await expect(page.getByRole("heading", { name: "North Ossetia" })).toBeVisible();
  await expect(page.locator(".place")).not.toContainText(/coast/i);
  const [header, ...rows] = fs.readFileSync(path.join(__dirname, "fixtures/place-attributes.csv"), "utf8").trim().split("\n");
  const fields = header.split(",").slice(3);
  await page.route("**/data/regions.json", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    for (const line of rows) {
      const [code, name, , ...values] = line.split(",");
      const area = data.regions.find((r) => code ? r.code === code : r.name === name);
      area.place = Object.fromEntries(fields.map((key, index) =>
        [key, index === fields.length - 1 ? values[index] : Number(values[index])]));
    }
    await route.fulfill({ response, json: data });
  });
  await page.goto("./#v=sig&r=7");
  await page.reload();
  await expect(page.getByRole("heading", { name: "What sort of place is this?" })).toBeVisible();
  await expect(page.locator(".rank-strip")).toHaveCount(6);
  await page.getByText("Show place characteristics as a table").click();
  const table = page.getByRole("table", { name: "Place characteristics in 2011" });
  const aged = table.getByRole("row").filter({ hasText: "Aged 65 or over" });
  await expect(aged.getByRole("cell")).toHaveText(["20%", "50", "25%", "3"]);
  await page.getByRole("button", { name: "All areas" }).click();
  const summary = page.getByRole("table", { name: "Place characteristics in 2011" });
  await expect(summary.getByRole("row").filter({ hasText: "Aged 65 or over" })).toContainText("25%");
});

test("About & cite opens an accessible dialog and returns focus", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop");
  await page.goto("./#v=sig&r=7");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "1");
  const about = page.getByRole("button", { name: "About & cite" });
  await about.click();
  const dialog = page.getByRole("dialog", { name: "About & cite" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("link", { name: /Understanding trajectories/ })).toHaveAttribute("href", "https://doi.org/10.1002/psp.2630");
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(about).toBeFocused();
  await expect(page.getByRole("heading", { name: "Brest" })).toBeVisible();
});
