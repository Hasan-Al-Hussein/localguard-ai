import { defineConfig, devices } from "@playwright/test";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const showcaseRoot = dirname(fileURLToPath(import.meta.url));
const port = 4173;

export default defineConfig({
  testDir: "./e2e",
  outputDir: "../../output/playwright/public-showcase",
  expect: { timeout: 15_000 },
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  timeout: 90_000,
  workers: 1,
  reporter: process.env.CI
    ? [
        ["line"],
        [
          "html",
          {
            open: "never",
            outputFolder: "../../output/playwright/public-showcase-report",
          },
        ],
      ]
    : "line",
  use: {
    ...devices["Desktop Chrome"],
    actionTimeout: 30_000,
    baseURL: `http://127.0.0.1:${port}`,
    navigationTimeout: 60_000,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "retain-on-failure",
  },
  webServer: {
    command: `serve out --listen tcp://127.0.0.1:${port} --no-clipboard`,
    cwd: showcaseRoot,
    url: `http://127.0.0.1:${port}/overview/`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
