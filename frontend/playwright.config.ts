import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["line"], ["html", { open: "never" }]] : "line",
  use: {
    baseURL: "http://127.0.0.1:3100",
    extraHTTPHeaders: { "x-forwarded-host": "microchips.by" },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], browserName: "chromium" } },
    // Keep one installed browser engine in local and CI runs while testing the
    // actual iPhone viewport and touch layout.
    { name: "mobile", use: { ...devices["iPhone 13"], browserName: "chromium" } },
  ],
  webServer: [
    {
      command: "node e2e/mock-api.mjs",
      port: 3101,
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "node e2e/start-frontend.mjs",
      port: 3100,
      reuseExistingServer: !process.env.CI,
      env: {
        LARAVEL_API_URL: "http://127.0.0.1:3101",
        DEFAULT_SITE_HOST: "microchips.by",
        LEAD_PROXY_SECRET: "testing-lead-proxy-secret-with-32-characters",
        HOSTNAME: "127.0.0.1",
        PORT: "3100",
      },
    },
  ],
});
