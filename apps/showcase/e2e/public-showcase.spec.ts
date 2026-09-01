import {
  expect,
  test,
  type ConsoleMessage,
  type Page,
  type Request,
  type TestInfo,
} from "@playwright/test";
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const showcaseOrigin = "http://127.0.0.1:4173";
const showcaseRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const disclosureText =
  "Public portfolio demo with synthetic data. No uploads, persistence, live AI, or real-world actions.";
const browserDocument404ConsoleMessage =
  "Failed to load resource: the server responded with a status of 404 (Not Found)";

const publicDemoIds = {
  documents: [
    "11111111-1111-4111-8111-111111111111",
    "12121212-1212-4121-8121-121212121212",
    "13131313-1313-4131-8131-131313131313",
  ],
  approval: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  tasks: [
    "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    "d1d1d1d1-d1d1-4d1d-8d1d-d1d1d1d1d1d1",
  ],
  evaluation: "20260830T091500000000Z-deterministic-showcase",
  auditEvents: [
    "e1111111-1111-4111-8111-111111111111",
    "e2222222-2222-4222-8222-222222222222",
    "e3333333-3333-4333-8333-333333333333",
    "e4444444-4444-4444-8444-444444444444",
    "e5555555-5555-4555-8555-555555555555",
  ],
} as const;

const coreRoutes = [
  "/overview/",
  "/documents/",
  "/ask/",
  "/approvals/",
  "/tasks/",
  "/evaluations/",
  "/audit/",
] as const;

const stableDetailRoutes = [
  ...publicDemoIds.documents.map((documentId) => `/documents/${documentId}/`),
  `/approvals/${publicDemoIds.approval}/`,
  `/tasks/${publicDemoIds.tasks[1]}/`,
  `/evaluations/${publicDemoIds.evaluation}/`,
  ...publicDemoIds.auditEvents
    .slice(0, 4)
    .map((eventId) => `/audit/${eventId}/`),
] as const;

const stateDependentDetailRoutes = [
  {
    message: "The requested synthetic workflow task is not available.",
    route: `/tasks/${publicDemoIds.tasks[0]}/`,
  },
  {
    message: "The requested synthetic audit event is not available.",
    route: `/audit/${publicDemoIds.auditEvents[4]}/`,
  },
] as const;

const approvedExternalLinks = [
  /^https:\/\/github\.com\/Hasan-Al-Hussein\/localguard-ai(?:[/?#]|$)/u,
  /^https:\/\/youtu\.be\/CQOcgDrGuR8(?:[/?#]|$)/u,
] as const;

type NetworkRecord = {
  method: string;
  resourceType: string;
  url: string;
};

type ResponseRecord = {
  resourceType: string;
  status: number;
  url: string;
};

function requestFailure(request: Request) {
  return {
    ...toNetworkRecord(request),
    error: request.failure()?.errorText ?? "unknown request failure",
  };
}

function toNetworkRecord(request: Request): NetworkRecord {
  return {
    method: request.method(),
    resourceType: request.resourceType(),
    url: request.url(),
  };
}

function createRuntimeRecorder(page: Page) {
  const requests: NetworkRecord[] = [];
  const responses: ResponseRecord[] = [];
  const failedRequests: ReturnType<typeof requestFailure>[] = [];
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];

  page.on("request", (request) => requests.push(toNetworkRecord(request)));
  page.on("requestfailed", (request) =>
    failedRequests.push(requestFailure(request)),
  );
  page.on("response", (response) => {
    responses.push({
      resourceType: response.request().resourceType(),
      status: response.status(),
      url: response.url(),
    });
  });
  page.on("console", (message: ConsoleMessage) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));

  return {
    async assertClean(
      testInfo: TestInfo,
      options: {
        allowedExternalDocumentUrls?: readonly RegExp[];
        allowedHttpErrors?: ReadonlyArray<{ path: string; status: number }>;
      } = {},
    ) {
      const allowedExternalDocumentUrls =
        options.allowedExternalDocumentUrls ?? [];
      const allowedHttpErrors = options.allowedHttpErrors ?? [];

      await testInfo.attach("public-showcase-runtime.json", {
        body: Buffer.from(
          JSON.stringify(
            { requests, responses, failedRequests, consoleErrors, pageErrors },
            null,
            2,
          ),
        ),
        contentType: "application/json",
      });

      const unsafeMethods = requests.filter(
        ({ method }) => method !== "GET" && method !== "HEAD",
      );
      expect(
        unsafeMethods,
        "The static showcase must never issue a mutating HTTP request.",
      ).toEqual([]);

      const apiRequests = requests.filter(({ url }) =>
        new URL(url).pathname.startsWith("/api/"),
      );
      expect(
        apiRequests,
        "The public showcase must never contact an API route.",
      ).toEqual([]);

      const unexpectedCrossOrigin = requests.filter((request) => {
        const requestUrl = new URL(request.url);
        if (requestUrl.origin === showcaseOrigin) {
          return false;
        }

        return !(
          request.resourceType === "document" &&
          request.method === "GET" &&
          allowedExternalDocumentUrls.some((allowedUrl) =>
            allowedUrl.test(request.url),
          )
        );
      });
      expect(
        unexpectedCrossOrigin,
        "Only an explicitly approved, user-initiated document navigation may leave the showcase origin.",
      ).toEqual([]);

      const unexpectedHttpErrors = responses.filter(({ status, url }) => {
        if (status < 400) {
          return false;
        }

        const responsePath = new URL(url).pathname;
        return !allowedHttpErrors.some(
          (allowed) =>
            allowed.path === responsePath && allowed.status === status,
        );
      });

      const consoleErrorsToReview = [...consoleErrors];
      for (const allowedError of allowedHttpErrors) {
        const isExpectedDocument404 = responses.some(
          ({ resourceType, status, url }) => {
            return (
              resourceType === "document" &&
              status === 404 &&
              status === allowedError.status &&
              new URL(url).pathname === allowedError.path
            );
          },
        );
        if (!isExpectedDocument404) {
          continue;
        }

        const browserMessageIndex = consoleErrorsToReview.indexOf(
          browserDocument404ConsoleMessage,
        );
        if (browserMessageIndex >= 0) {
          // Chromium reports a deliberately requested 404 document as a console resource error.
          // Remove only the single message tied to the independently verified 404 response.
          consoleErrorsToReview.splice(browserMessageIndex, 1);
        }
      }

      expect(
        unexpectedHttpErrors,
        "Every non-deliberate showcase response must succeed.",
      ).toEqual([]);
      expect(
        failedRequests,
        "The showcase must not lose static asset or navigation requests.",
      ).toEqual([]);
      expect(
        consoleErrorsToReview,
        "The showcase must not emit console errors.",
      ).toEqual([]);
      expect(
        pageErrors,
        "The showcase must not raise uncaught browser errors.",
      ).toEqual([]);
    },
  };
}

async function expectDisclosure(page: Page) {
  const disclosure = page.locator("[data-public-demo-disclosure]");
  await expect(disclosure).toHaveCount(1);
  await expect(disclosure).toBeVisible();

  await expect(disclosure).toHaveText(disclosureText);
}

async function expectStaticRoute(page: Page, route: string) {
  const response = await page.goto(route, { waitUntil: "networkidle" });
  expect(
    response?.status(),
    `Direct navigation to ${route} must return HTTP 200.`,
  ).toBe(200);
  await expect(page).toHaveURL(
    new RegExp(`${route.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&")}$`, "u"),
  );
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
  await expect(page.getByRole("main")).toBeVisible();
  await expectDisclosure(page);
}

async function expectExternalLinksHardened(page: Page) {
  const links = page.locator('a[href^="https://"], a[href^="http://"]');
  const count = await links.count();

  for (let index = 0; index < count; index += 1) {
    const link = links.nth(index);
    const href = await link.getAttribute("href");
    expect(href, "Every absolute link must have an href.").toBeTruthy();
    expect(
      approvedExternalLinks.some((allowedLink) => allowedLink.test(href ?? "")),
      `External link is not in the recruiter-demo allowlist: ${href}`,
    ).toBe(true);
    await expect(link).toHaveAttribute("target", "_blank");
    const rel = (await link.getAttribute("rel"))?.split(/\s+/u) ?? [];
    expect(rel).toEqual(expect.arrayContaining(["noopener", "noreferrer"]));
  }
}

test.describe("public showcase static contract", () => {
  for (const route of coreRoutes) {
    test(`serves ${route} directly without runtime services`, async ({
      page,
    }, testInfo) => {
      const runtime = createRuntimeRecorder(page);
      await expectStaticRoute(page, route);
      await expectExternalLinksHardened(page);
      await runtime.assertClean(testInfo);
    });
  }

  for (const route of stableDetailRoutes) {
    test(`deep-links directly to ${route}`, async ({ page }, testInfo) => {
      const runtime = createRuntimeRecorder(page);
      await expectStaticRoute(page, route);
      await runtime.assertClean(testInfo);
    });
  }

  for (const { message, route } of stateDependentDetailRoutes) {
    test(`explains reset-only state when deep-linking to ${route}`, async ({
      page,
    }, testInfo) => {
      const runtime = createRuntimeRecorder(page);
      const response = await page.goto(route, { waitUntil: "networkidle" });
      expect(
        response?.status(),
        `The exported state-dependent route ${route} must remain reachable.`,
      ).toBe(200);
      await expect(page.getByRole("main")).toBeVisible();
      await expectDisclosure(page);

      const errorState = page.getByRole("main").getByRole("alert");
      await expect(
        errorState.getByRole("heading", {
          level: 2,
          name: "We could not load this view",
        }),
      ).toBeVisible();
      await expect(
        errorState.getByText(message, { exact: true }),
      ).toBeVisible();
      await runtime.assertClean(testInfo);
    });
  }

  test("serves the root and keeps the synthetic-demo boundary visible", async ({
    page,
  }, testInfo) => {
    const runtime = createRuntimeRecorder(page);
    const response = await page.goto("/", { waitUntil: "networkidle" });
    expect(response?.status()).toBe(200);
    await expectDisclosure(page);
    await runtime.assertClean(testInfo);
  });

  test("hydrates the exported overview when the host serves it without a trailing slash", async ({
    page,
  }, testInfo) => {
    const runtime = createRuntimeRecorder(page);
    const overviewHtml = await readFile(
      join(showcaseRoot, "out", "overview", "index.html"),
      "utf8",
    );

    await page.route(`${showcaseOrigin}/overview`, async (route) => {
      await route.fulfill({
        body: overviewHtml,
        contentType: "text/html; charset=utf-8",
        status: 200,
      });
    });

    const response = await page.goto("/overview", { waitUntil: "networkidle" });
    expect(response?.status()).toBe(200);
    await expect(page).toHaveURL(`${showcaseOrigin}/overview`);
    await expect(
      page.getByRole("heading", { level: 1, name: "Overview", exact: true }),
    ).toBeVisible();
    await expectDisclosure(page);
    await runtime.assertClean(testInfo);
  });

  test("serves the recruiter-safe login entry without accepting credentials", async ({
    page,
  }, testInfo) => {
    const runtime = createRuntimeRecorder(page);
    const response = await page.goto("/login/", { waitUntil: "networkidle" });
    expect(response?.status()).toBe(200);
    await expectDisclosure(page);
    await expect(page.locator('input[type="password"]')).toHaveCount(0);
    await runtime.assertClean(testInfo);
  });

  test("serves the custom static 404 without runtime errors", async ({
    page,
  }, testInfo) => {
    const runtime = createRuntimeRecorder(page);
    const path = "/this-public-demo-route-does-not-exist/";
    const response = await page.goto(path, { waitUntil: "networkidle" });
    expect(response?.status()).toBe(404);
    await expect(
      page.getByRole("heading", { level: 1, name: "Page not found" }),
    ).toBeVisible();
    await expectDisclosure(page);
    await runtime.assertClean(testInfo, {
      allowedHttpErrors: [{ path, status: 404 }],
    });
  });
});

test.describe("public showcase responsive contract", () => {
  test.use({
    hasTouch: true,
    isMobile: true,
    viewport: { width: 390, height: 844 },
  });

  test("keeps the mobile shell operable and overflow-free", async ({
    page,
  }, testInfo) => {
    const runtime = createRuntimeRecorder(page);
    await expectStaticRoute(page, "/overview/");
    const navigationTrigger = page.getByRole("button", {
      name: "Open navigation",
    });
    await expect(navigationTrigger).toBeVisible();
    await navigationTrigger.click();
    const navigation = page.getByRole("dialog", {
      name: "Workspace navigation",
    });
    await expect(navigation).toBeVisible();
    await navigation.getByRole("link", { name: "Documents" }).click();
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveURL(/\/documents\/$/u);
    await expectDisclosure(page);

    const geometry = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      viewportWidth: window.innerWidth,
    }));
    expect(geometry.scrollWidth).toBeLessThanOrEqual(
      geometry.viewportWidth + 1,
    );
    expect(geometry.clientWidth).toBeLessThanOrEqual(
      geometry.viewportWidth + 1,
    );
    await runtime.assertClean(testInfo);
  });
});

test.describe("public showcase reduced-motion contract", () => {
  test("removes ambient Proof Plane animations", async ({
    browser,
  }, testInfo) => {
    const context = await browser.newContext({ reducedMotion: "reduce" });
    const page = await context.newPage();

    try {
      const runtime = createRuntimeRecorder(page);
      await expectStaticRoute(page, "/overview/");
      expect(
        await page.evaluate(
          () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
        ),
      ).toBe(true);

      const animatedElements = page.locator(
        ".proof-flow-packet, .proof-gate-core",
      );
      expect(await animatedElements.count()).toBeGreaterThan(0);
      const animationNames = await animatedElements.evaluateAll((elements) =>
        elements.map(
          (element) => window.getComputedStyle(element).animationName,
        ),
      );
      expect(
        animationNames.every((animationName) => animationName === "none"),
      ).toBe(true);
      await runtime.assertClean(testInfo);
    } finally {
      await context.close();
    }
  });
});
