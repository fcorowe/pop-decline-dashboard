const AxeBuilder = require("@axe-core/playwright").default;
const { test, expect } = require("@playwright/test");

for (const hash of ["#v=traj", "#v=year&y=2011", "#v=sig", "#v=sig&r=7"]) {
  test(`no serious or critical axe violations in ${hash}`, async ({ page }, info) => {
    test.skip(!["desktop", "iphone"].includes(info.project.name));
    await page.goto(`./${hash}`);
    await expect(page.locator("body")).toHaveAttribute("data-ready", "1");
    await page.evaluate(() => document.fonts.ready);
    const { violations } = await new AxeBuilder({ page }).analyze();
    expect(violations.filter(({ impact }) => ["serious", "critical"].includes(impact))
      .map(({ id, nodes }) => ({ id, targets: nodes.map((node) => node.target) }))).toEqual([]);
  });
}

test("keyboard tabs and legend keep focus, and search focuses the heading", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop");
  await page.goto("./");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "1");
  const trajectories = page.getByRole("tab", { name: "Trajectories" });
  await trajectories.focus();
  await page.keyboard.press("ArrowRight");
  const year = page.getByRole("tab", { name: "Year by year", selected: true });
  await expect(year).toBeFocused();
  await expect(page.getByRole("tabpanel")).toHaveAccessibleName("Year by year");
  await page.keyboard.press("End");
  await expect(page.getByRole("tab", { name: "Drivers", selected: true })).toBeFocused();
  await page.keyboard.press("Home");
  await expect(trajectories).toBeFocused();
  await expect(year).toHaveCount(0);
  const chip = page.locator("#legend .chip").first();
  await chip.focus();
  await page.keyboard.press("Space");
  await expect(chip).toBeFocused();
  await expect(chip).toHaveAttribute("aria-pressed", "true");
  await page.keyboard.press("Enter");
  await expect(chip).toBeFocused();
  await expect(chip).toHaveAttribute("aria-pressed", "false");
  const search = page.getByLabel("Find a region");
  await search.fill("Dibër");
  await search.press("Enter");
  await expect(page.getByRole("heading", { name: "Dibër" })).toBeFocused();
});

test("turning on reduced motion stops autoplay and makes zoom synchronous", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop");
  await page.goto("./#v=year");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "1");
  await page.getByRole("button", { name: "Play years" }).click();
  await expect(page.getByRole("button", { name: "Pause" })).toBeVisible();
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(page.getByRole("button", { name: "Play years" })).toBeDisabled();
  const currentYear = await page.locator("#yearout").textContent();
  const transform = await page.evaluate(() => {
    document.querySelector("#zin").click();
    return document.querySelector("#map svg > g").getAttribute("transform");
  });
  expect(transform).toContain("scale(1.8)");
  await page.waitForTimeout(850); // More than one playback interval.
  await expect(page.locator("#yearout")).toHaveText(currentYear);
});
