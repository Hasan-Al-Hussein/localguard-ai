import { defineConfig, devices } from "@playwright/test";
import {
  isPortfolioCaptureEnabled,
  PORTFOLIO_BROWSER_USE,
  PORTFOLIO_CAPTURE_TAG,
  PORTFOLIO_PROJECT_NAME,
} from "./e2e/portfolio-support";

const realStackEnabled = process.env.LOCALGUARD_REAL_STACK === "1";
const portfolioCaptureEnabled = isPortfolioCaptureEnabled(process.env);
const baseURL = process.env.LOCALGUARD_BASE_URL ?? "http://127.0.0.1:3000";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: portfolioCaptureEnabled
    ? [["list"]]
    : [["list"], ["html", { open: "never", outputFolder: "output/playwright-report" }]],
  outputDir: "output/playwright-results",
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: portfolioCaptureEnabled
    ? [{
        name: PORTFOLIO_PROJECT_NAME,
        testMatch: "portfolio-capture.spec.ts",
        grep: PORTFOLIO_CAPTURE_TAG,
        retries: 0,
        use: { ...devices["Desktop Chrome"], ...PORTFOLIO_BROWSER_USE },
      }]
    : realStackEnabled
    ? [{
        name: "real-stack",
        testMatch: "real-stack.spec.ts",
        grep: /@real-stack/,
        // Trace action metadata can retain submitted credentials. Real-stack
        // failures use screenshots/video plus API, worker, and web logs instead.
        use: { ...devices["Desktop Chrome"], trace: "off" },
      }]
    : [
        { name: "ui-contract-chromium", testIgnore: ["real-stack.spec.ts", "portfolio-capture.spec.ts"], use: { ...devices["Desktop Chrome"] } },
        { name: "ui-contract-mobile", testIgnore: ["real-stack.spec.ts", "portfolio-capture.spec.ts"], use: { ...devices["Pixel 7"] } },
      ],
  ...(realStackEnabled || portfolioCaptureEnabled ? {} : {
    webServer: {
      command: "npm run dev",
      url: `${baseURL}/login`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  }),
});
