const { chromium } = require("playwright");
const path = require("node:path");
const fs = require("node:fs");

const outputDirectory = path.resolve(__dirname, "../../output/archived-capture");
fs.mkdirSync(outputDirectory, { recursive: true });

const baseUrl = process.env.LOCALGUARD_CAPTURE_BASE_URL || "http://127.0.0.1:3000";
const routes = ["overview", "ask", "documents", "approvals", "tasks", "evaluations", "audit"];

async function captureRoutes(browser, storageState, label, viewport, selectedRoutes = routes) {
  const context = await browser.newContext({ colorScheme: "light", reducedMotion: "no-preference", storageState, viewport });
  const page = await context.newPage();
  const results = [];
  for (const route of selectedRoutes) {
    await page.goto(`${baseUrl}/${route}`, { waitUntil: "networkidle" });
    await page.locator("main").waitFor({ state: "visible" });
    await page.waitForTimeout(route === "overview" || route === "ask" ? 900 : 350);
    const metrics = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      scrollHeight: document.documentElement.scrollHeight,
    }));
    await page.screenshot({
      animations: "disabled",
      fullPage: true,
      path: path.join(outputDirectory, `refinement-${route}-${label}.png`),
    });
    results.push({ route, viewport, ...metrics });
  }
  await context.close();
  return results;
}

async function main() {
  const password = process.env.LOCALGUARD_CAPTURE_PASSWORD;
  if (!password) throw new Error("LOCALGUARD_CAPTURE_PASSWORD is required");
  const browser = await chromium.launch({ headless: true });
  try {
    const authContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const authPage = await authContext.newPage();
    await authPage.goto(`${baseUrl}/login`, { waitUntil: "networkidle" });
    await authPage.getByLabel("Username").fill("demo-reviewer");
    await authPage.locator("#password").fill(password);
    await authPage.getByRole("button", { name: "Sign in" }).click();
    await authPage.waitForURL("**/overview", { timeout: 20_000 });
    const storageState = await authContext.storageState();
    await authContext.close();

    const results = [];
    results.push(...await captureRoutes(browser, storageState, "1920", { width: 1920, height: 1080 }, ["overview", "ask"]));
    results.push(...await captureRoutes(browser, storageState, "1440", { width: 1440, height: 1000 }));
    results.push(...await captureRoutes(browser, storageState, "1280", { width: 1280, height: 900 }, ["overview", "ask", "documents"]));
    results.push(...await captureRoutes(browser, storageState, "1024", { width: 1024, height: 768 }, ["overview", "ask", "documents"]));
    results.push(...await captureRoutes(browser, storageState, "768", { width: 768, height: 1024 }, ["overview", "ask", "documents"]));
    results.push(...await captureRoutes(browser, storageState, "390", { width: 390, height: 844 }));
    console.log(JSON.stringify(results));
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
