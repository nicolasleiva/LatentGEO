import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.PERF_BASE_URL || "http://127.0.0.1:3000";
const storageState = process.env.PERF_STORAGE_STATE_PATH || undefined;

export default defineConfig({
  testDir: ".",
  timeout: 120_000,
  expect: {
    timeout: 20_000,
  },
  reporter: [
    ["list"],
    ["html", { outputFolder: "playwright-report", open: "never" }],
  ],
  use: {
    baseURL,
    storageState,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
