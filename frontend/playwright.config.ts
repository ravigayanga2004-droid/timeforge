import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  webServer:
    process.env.E2E_REUSE === "1"
      ? undefined
      : [
          {
            command: "node ../scripts/e2e-runner.mjs",
            url: "http://localhost:8000/api/health",
            timeout: 180000,
            reuseExistingServer: false,
          },
          {
            command: "npm run dev",
            url: "http://localhost:5173",
            timeout: 30000,
            reuseExistingServer: false,
          },
        ],
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 90000,
  expect: { timeout: 10000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
