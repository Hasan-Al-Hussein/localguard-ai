const { chromium } = require("playwright");
const path = require("node:path");
const fs = require("node:fs");

const outputDirectory = path.resolve(__dirname, "../../output/archived-capture");
fs.mkdirSync(outputDirectory, { recursive: true });

async function capture(page, name) {
  await page.screenshot({
    animations: "disabled",
    fullPage: true,
    path: path.join(outputDirectory, name),
  });
}

async function main() {
  const password = process.env.LOCALGUARD_CAPTURE_PASSWORD;
  if (!password) throw new Error("LOCALGUARD_CAPTURE_PASSWORD is required");
  const baseUrl = process.env.LOCALGUARD_CAPTURE_BASE_URL || "http://127.0.0.1:3000";

  const browser = await chromium.launch({ headless: true });
  const desktop = await browser.newContext({
    colorScheme: "light",
    reducedMotion: "no-preference",
    viewport: { width: 1440, height: 1000 },
  });
  const page = await desktop.newPage();
  await page.goto(`${baseUrl}/login`, { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  await capture(page, "showcase-login-final.png");

  await page.getByLabel("Username").fill("demo-reviewer");
  await page.locator("#password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/overview", { timeout: 20_000 });
  await page.getByRole("heading", { name: "Overview" }).waitFor();
  await page.waitForTimeout(1_400);
  await capture(page, "showcase-overview-final.png");

  await page.goto(`${baseUrl}/ask`, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "Ask LocalGuard" }).waitFor();
  await page.waitForTimeout(900);
  await capture(page, "showcase-ask-final.png");

  const state = await desktop.storageState();
  const mobile = await browser.newContext({
    colorScheme: "light",
    reducedMotion: "no-preference",
    storageState: state,
    viewport: { width: 390, height: 844 },
  });
  const mobilePage = await mobile.newPage();
  await mobilePage.goto(`${baseUrl}/overview`, { waitUntil: "networkidle" });
  await mobilePage.getByRole("heading", { name: "Overview" }).waitFor();
  await mobilePage.waitForTimeout(900);
  await capture(mobilePage, "showcase-overview-mobile-final.png");
  await mobilePage.goto(`${baseUrl}/ask`, { waitUntil: "networkidle" });
  await mobilePage.getByRole("heading", { name: "Ask LocalGuard" }).waitFor();
  await mobilePage.waitForTimeout(700);
  await capture(mobilePage, "showcase-ask-mobile-final.png");

  await mobile.close();
  await desktop.close();
  await browser.close();
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
