import { randomUUID } from "node:crypto";
import {
  copyFile,
  mkdir,
  readFile,
  rename,
  rm,
  stat,
  unlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const modeArgument = process.argv.find((argument) => argument.startsWith("--mode="));
const mode = modeArgument?.split("=")[1];
if (mode !== "screenshots" && mode !== "video") {
  throw new Error("Use --mode=screenshots or --mode=video");
}

const baseURL = process.env.LOCALGUARD_BASE_URL ?? "http://127.0.0.1:3000";
const username = requiredEnvironment("LOCALGUARD_DEMO_USERNAME");
const password = requiredEnvironment("LOCALGUARD_DEMO_PASSWORD");
const question = "How long does the Service Desk have to disable a vendor account after it receives an offboarding notice?";
const expectedAnswer = "The Service Desk must disable the vendor account within one hour after receiving the offboarding notice.";
const actionRequest = "For a synthetic September 1 scenario, an authorized sponsor's vendor offboarding notice was received at 2026-09-01T09:00:00Z. Propose the required account-disable task; do not execute it without review.";
const expectedTaskTitle = "Disable the vendor account";
const evaluation = JSON.parse(await readFile(path.join(repoRoot, "evals", "results", "latest.json"), "utf8"));
const runId = requiredString(evaluation.run_id, "latest evaluation run_id");
const outputRoot = path.join(repoRoot, "demo-video", "recording", "output");
const screenshotRoot = path.join(repoRoot, "docs", "screenshots");
const pipelineRoot = path.join(screenshotRoot, "pipeline");
const timeline = [];
const pageErrors = [];
let startedAt = 0;

const stepFiles = {
  login: "step-01-sign-in-local-workspace.png",
  overview: "step-02-overview-system-status.png",
  documents: "step-03-inspect-indexed-document.png",
  questionReady: "step-04-ask-evidence-question.png",
  questionQueued: "step-05-submit-grounded-question.png",
  answer: "step-06-grounded-answer-with-citation.png",
  citation: "step-07-open-exact-source-proof.png",
  actionReady: "step-08-propose-evidence-bound-action.png",
  approval: "step-09-review-pending-proposal.png",
  task: "step-10-approved-task-created-once.png",
  audit: "step-11-inspect-causal-audit-trail.png",
  evaluation: "step-12-verify-evaluation-results.png",
};

const rootAliases = {
  "overview.png": stepFiles.overview,
  "ask-cited-answer.png": stepFiles.answer,
  "document-citation.png": stepFiles.citation,
  "approval-pending.png": stepFiles.approval,
  "task-executed.png": stepFiles.task,
  "audit-event.png": stepFiles.audit,
  "evaluation-ollama.png": stepFiles.evaluation,
};

await mkdir(outputRoot, { recursive: true });
const browser = await chromium.launch({ headless: true });
let context;
let page;
let stagingDirectory = null;
let videoHandle = null;

try {
  if (mode === "video") {
    const authenticationContext = await browser.newContext({
      baseURL,
      viewport: { width: 1920, height: 1080 },
      colorScheme: "light",
    });
    const authenticationPage = await authenticationContext.newPage();
    await login(authenticationPage);
    const storageState = await authenticationContext.storageState();
    await authenticationContext.close();

    const rawDirectory = path.join(outputRoot, `raw-${randomUUID()}`);
    await mkdir(rawDirectory, { recursive: true });
    context = await browser.newContext({
      baseURL,
      viewport: { width: 1920, height: 1080 },
      colorScheme: "light",
      storageState,
      recordVideo: { dir: rawDirectory, size: { width: 1920, height: 1080 } },
    });
    page = await context.newPage();
    videoHandle = page.video();
    startedAt = Date.now();
  } else {
    stagingDirectory = path.join(screenshotRoot, `.pipeline-incoming-${randomUUID()}`);
    await mkdir(stagingDirectory, { recursive: true });
    context = await browser.newContext({
      baseURL,
      viewport: { width: 1440, height: 1000 },
      colorScheme: "light",
      deviceScaleFactor: 1,
    });
    page = await context.newPage();
  }

  page.on("pageerror", (error) => pageErrors.push(error.message));

  if (mode === "screenshots") {
    await page.goto("/login");
    await page.getByRole("button", { name: "Sign in" }).waitFor();
    await checkpoint("login");
    await login(page);
  }

  await page.goto("/overview");
  await page.getByRole("heading", { name: "Overview" }).waitFor();
  await checkpoint("overview", page.getByRole("heading", { name: "Overview" }));

  await page.goto("/documents");
  await page.getByRole("heading", { name: "Documents" }).waitFor();
  const documentFilter = page.getByPlaceholder("Filter this page by title");
  await documentFilter.fill("lg-pol-001-vendor-access");
  const documentLink = page.getByRole("link", { name: /lg-pol-001-vendor-access/i }).first();
  await documentLink.waitFor();
  await checkpoint("documents");

  await page.goto("/ask");
  await page.getByRole("heading", { name: "Ask LocalGuard" }).waitFor();
  const questionInput = page.getByLabel("Ask a question about indexed documents");
  await enterText(questionInput, question);
  await checkpoint("questionReady", questionInput);

  const questionResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === "/api/questions" && response.request().method() === "POST";
  });
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const questionResponse = await questionResponsePromise;
  ensureResponse(questionResponse, "question submission");
  const acceptedQuestion = await questionResponse.json();
  const questionId = requiredString(acceptedQuestion.id, "accepted question id");
  const checkingState = page.getByText(/LocalGuard is checking the evidence/i).first();
  await checkingState.waitFor({ timeout: 15_000 }).catch(() => undefined);
  await checkpoint("questionQueued");

  const completedQuestion = await pollJson(`/api/questions/${encodeURIComponent(questionId)}`, (payload) => {
    if (payload.state === "failed") throw new Error(`Question failed: ${payload.error_code ?? "unknown"}`);
    return payload.state === "succeeded";
  });
  if (completedQuestion.answer?.text !== expectedAnswer) {
    throw new Error("The fresh grounded answer did not match the verified one-hour fact");
  }
  const answerCard = page.locator("article").filter({ hasText: `Question job: ${questionId}` });
  await answerCard.getByText(expectedAnswer, { exact: true }).waitFor({ timeout: 60_000 });
  const answerDetails = answerCard.locator("summary").filter({ hasText: "Answer details" });
  if (await answerDetails.isVisible()) await answerDetails.click();
  const citationLink = answerCard.locator('a[href*="/documents/"][href*="anchor="]').first();
  await citationLink.waitFor();
  await checkpoint("answer", answerCard);

  await citationLink.click();
  await page.getByRole("heading", { name: "Cited passage" }).waitFor();
  const citedMark = page.locator("mark").first();
  await citedMark.waitFor();
  if (!(await citedMark.textContent())?.includes("within one hour")) {
    throw new Error("The opened source does not contain the one-hour obligation");
  }
  await checkpoint("citation", page.getByRole("heading", { name: "Cited passage" }));

  await page.goto("/ask");
  await page.getByRole("heading", { name: "Ask LocalGuard" }).waitFor();
  await page.getByText("Propose an action", { exact: true }).first().click();
  const actionInput = page.getByLabel("Describe an action to ground in indexed documents");
  await enterText(actionInput, actionRequest);
  await checkpoint("actionReady", actionInput);

  const workflowResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === "/api/workflow-runs" && response.request().method() === "POST";
  });
  await page.getByRole("button", { name: "Analyze action" }).click();
  const workflowResponse = await workflowResponsePromise;
  ensureResponse(workflowResponse, "workflow submission");
  const workflowAccepted = await workflowResponse.json();
  const workflowId = requiredString(workflowAccepted.run?.id, "workflow run id");
  const reviewLink = page.getByRole("link", { name: "Review proposal" });
  await reviewLink.waitFor({ timeout: 360_000 });
  await reviewLink.click();
  await page.getByText("Nothing has been created yet", { exact: true }).waitFor();
  await page.getByText("Service Desk", { exact: true }).first().waitFor();
  const proposalId = requiredString(new URL(page.url()).pathname.split("/").at(-1), "proposal id");
  await checkpoint("approval", page.getByText("Nothing has been created yet", { exact: true }));

  const approvalResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === `/api/approvals/${proposalId}/approve`
      && response.request().method() === "POST";
  });
  await page.getByRole("button", { name: "Approve unchanged" }).click();
  const approvalResponse = await approvalResponsePromise;
  ensureResponse(approvalResponse, "approval");
  const tasks = await pollJson("/api/tasks?offset=0&limit=100", (payload) => (
    Array.isArray(payload.items)
    && payload.items.filter((candidate) => candidate.proposal_id === proposalId).length === 1
  ));
  const matchingTasks = tasks.items.filter((candidate) => candidate.proposal_id === proposalId);
  if (matchingTasks.length !== 1) throw new Error("Approval did not create exactly one matching task");
  const task = matchingTasks[0];
  if (task.title !== expectedTaskTitle || task.assignee !== "Service Desk" || task.priority !== "high") {
    throw new Error("The task does not match the verified source-derived proposal");
  }
  await page.goto(`/tasks/${encodeURIComponent(task.id)}`);
  await page.getByRole("heading", { name: "Approval provenance" }).waitFor();
  await page.getByText(expectedTaskTitle, { exact: true }).waitFor();
  await checkpoint("task", page.getByText(expectedTaskTitle, { exact: true }));

  await page.goto(`/audit?thread=${encodeURIComponent(workflowId)}`);
  await page.getByRole("heading", { name: "Workflow audit chain" }).waitFor();
  await page.getByText(workflowId, { exact: true }).first().waitFor();
  await checkpoint("audit", page.getByRole("heading", { name: "Workflow audit chain" }));

  await page.goto(`/evaluations/${encodeURIComponent(runId)}`);
  await page.getByRole("heading", { name: runId }).waitFor();
  await page.getByText("25/25", { exact: true }).waitFor();
  await page.getByRole("region", { name: "Runtime model identity" }).waitFor();
  await checkpoint("evaluation", page.getByText("25/25", { exact: true }));

  if (pageErrors.length > 0) {
    throw new Error(`Browser page errors: ${pageErrors.join(" | ")}`);
  }

  if (mode === "screenshots") {
    await validateAndPublishScreenshots(stagingDirectory);
  }
} finally {
  if (context) await context.close();
  if (mode === "video" && videoHandle) {
    const sourcePath = await videoHandle.path();
    const finalVideoPath = path.join(outputRoot, "raw-product-flow.webm");
    await copyFile(sourcePath, finalVideoPath);
    timeline.push({ label: "recording-complete", ms: Date.now() - startedAt });
    await writeFile(
      path.join(outputRoot, "timeline.json"),
      `${JSON.stringify({ schemaVersion: 1, viewport: { width: 1920, height: 1080 }, timeline }, null, 2)}\n`,
      "utf8",
    );
  }
  await browser.close();
}

console.log(mode === "screenshots"
  ? `Published 12 screenshots to ${pipelineRoot}`
  : `Saved raw recording and timeline to ${outputRoot}`);

async function login(targetPage) {
  await targetPage.goto("/login");
  const usernameInput = targetPage.getByLabel("Username");
  const passwordInput = targetPage.getByLabel("Password", { exact: true });
  await usernameInput.fill(username);
  await passwordInput.fill(password);
  const loginResponsePromise = targetPage.waitForResponse((response) => (
    new URL(response.url()).pathname === "/api/auth/login"
    && response.request().method() === "POST"
  ));
  await targetPage.getByRole("button", { name: "Sign in" }).click();
  const loginResponse = await loginResponsePromise;
  ensureResponse(loginResponse, "login");
  await targetPage.waitForURL(/\/overview$/);
}

async function enterText(locator, value) {
  await locator.fill("");
  if (mode === "video") {
    await locator.pressSequentially(value, { delay: 12 });
  } else {
    await locator.fill(value);
  }
}

async function checkpoint(label, focusLocator = null) {
  if (focusLocator) {
    await focusLocator.scrollIntoViewIfNeeded().catch(() => undefined);
  }
  await page.evaluate(async () => {
    await document.fonts.ready;
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
  });
  if (mode === "screenshots" && (label === "documents" || label === "questionQueued" || label === "approval")) {
    await page.evaluate(() => {
      window.scrollTo(0, 0);
      document.documentElement.scrollTop = 0;
      document.body.scrollTop = 0;
      for (const element of document.querySelectorAll("*")) {
        if (element instanceof HTMLElement && element.scrollTop > 0) element.scrollTop = 0;
      }
    });
    await page.waitForFunction(() => (
      window.scrollY === 0
      && document.documentElement.scrollTop === 0
      && document.body.scrollTop === 0
      && [...document.querySelectorAll("*")].every((element) => (
        !(element instanceof HTMLElement) || element.scrollTop === 0
      ))
    ));
  }
  await page.waitForTimeout(mode === "video" ? 2_000 : 500);
  if (mode === "video") {
    timeline.push({ label, ms: Date.now() - startedAt, url: new URL(page.url()).pathname });
    return;
  }
  await page.screenshot({
    path: path.join(stagingDirectory, stepFiles[label]),
    animations: "disabled",
    fullPage: false,
  });
}

async function pollJson(requestPath, terminal, timeoutMs = 360_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const response = await page.request.get(requestPath, { failOnStatusCode: false });
    ensureResponse(response, requestPath);
    const payload = await response.json();
    if (terminal(payload)) return payload;
    await page.waitForTimeout(1_000);
  }
  throw new Error(`Timed out polling ${requestPath.split("?")[0]}`);
}

async function validateAndPublishScreenshots(staging) {
  const expectedFiles = Object.values(stepFiles);
  for (const filename of expectedFiles) {
    const screenshotPath = path.join(staging, filename);
    const metadata = await stat(screenshotPath);
    if (metadata.size < 25_000) throw new Error(`Screenshot is unexpectedly small: ${filename}`);
    const header = await readFile(screenshotPath);
    if (header.subarray(0, 8).toString("hex") !== "89504e470d0a1a0a") {
      throw new Error(`Screenshot is not a valid PNG: ${filename}`);
    }
  }

  const backup = path.join(tmpdir(), `localguard-pipeline-backup-${randomUUID()}`);
  try {
    await rename(pipelineRoot, backup).catch((error) => {
      if (error.code !== "ENOENT") throw error;
    });
    await rename(staging, pipelineRoot);
    stagingDirectory = null;
    await rm(backup, { recursive: true, force: true });
  } catch (error) {
    await rename(backup, pipelineRoot).catch(() => undefined);
    throw error;
  }

  for (const [alias, source] of Object.entries(rootAliases)) {
    const target = path.join(screenshotRoot, alias);
    const incoming = `${target}.incoming`;
    await copyFile(path.join(pipelineRoot, source), incoming);
    await unlink(target).catch((error) => {
      if (error.code !== "ENOENT") throw error;
    });
    await rename(incoming, target);
  }
}

function ensureResponse(response, operation) {
  if (!response.ok()) throw new Error(`${operation} failed with HTTP ${response.status()}`);
}

function requiredEnvironment(name) {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

function requiredString(value, label) {
  if (typeof value !== "string" || value.length === 0) throw new Error(`${label} is missing`);
  return value;
}
