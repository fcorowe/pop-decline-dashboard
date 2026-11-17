// Run: npx playwright test   (starts a local static server automatically)
const { defineConfig, devices } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "tests",
  testMatch: /.*\.spec\.js/,
  timeout: 30000,
  reporter: [["list"]],
  use: { baseURL: "http://localhost:8766" },
  webServer: {
    command: "python3 -m http.server 8766 -d site",
    port: 8766,
    reuseExistingServer: true,
    stdout: "ignore",
    stderr: "ignore",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1366, height: 850 } } },
    { name: "laptop-small", use: { ...devices["Desktop Chrome"], viewport: { width: 1024, height: 700 } } },
    { name: "iphone", use: { ...devices["iPhone 13"], browserName: "chromium" } },
    { name: "android", use: { ...devices["Pixel 7"] } },
    { name: "small-phone", use: { ...devices["iPhone SE"], browserName: "chromium" } },
  ],
});
