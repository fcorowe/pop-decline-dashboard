// Run: npx playwright test   (starts a local static server automatically)
const { defineConfig, devices } = require("@playwright/test");

const remoteURL = process.env.BASE_URL;
const baseURL = remoteURL ? remoteURL.replace(/\/?$/, "/") : "http://127.0.0.1:8766/";

module.exports = defineConfig({
  testDir: "tests",
  testMatch: /.*\.spec\.js/,
  timeout: 30000,
  workers: 1,
  reporter: [["list"]],
  use: { baseURL },
  webServer: remoteURL ? undefined : {
    command: "python3 -m http.server 8766 --bind 127.0.0.1 --protocol HTTP/1.1 -d site",
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
