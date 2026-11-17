const { test, expect } = require("@playwright/test");

const views = {
  trajectories: "#v=traj",
  "year-2011": "#v=year&y=2011",
  drivers: "#v=sig",
  "trajectory-area": "#v=traj&r=7",
  "driver-area": "#v=sig&r=7",
};

for (const [name, hash] of Object.entries(views)) {
  test(`approved appearance: ${name}`, async ({ page }, info) => {
    test.skip(!["desktop", "iphone"].includes(info.project.name));
    await page.goto(`./${hash}`);
    await expect(page.locator("body")).toHaveAttribute("data-ready", "1");
    await page.evaluate(() => document.fonts.ready);
    await expect(page).toHaveScreenshot(`${name}.png`, {
      animations: "disabled",
      maxDiffPixelRatio: 0.01,
    });
  });
}
