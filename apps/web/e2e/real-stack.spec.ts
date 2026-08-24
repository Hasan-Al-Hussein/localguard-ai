import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

const fixturePath = fileURLToPath(new URL("../../../fixtures/documents/clean/lg-pol-001-vendor-access.pdf", import.meta.url));
const username = process.env.LOCALGUARD_E2E_USERNAME ?? "demo-admin";
const password = process.env.BOOTSTRAP_ADMIN_PASSWORD;

type JsonResponse = { ok(): boolean; status(): number; url(): string; json(): Promise<unknown> };

async function responseJson<T>(response: JsonResponse): Promise<T> {
  if (!response.ok()) throw new Error(`Real-stack request failed: ${response.status()} ${response.url()}`);
  return response.json() as Promise<T>;
}

async function pollJson<T>(page: Page, path: string, terminal: (payload: T) => boolean, timeoutMs = 180_000): Promise<T> {
  const deadline = Date.now() + timeoutMs;
  let last: T | undefined;
  while (Date.now() < deadline) {
    const response = await page.request.get(path, { failOnStatusCode: false });
    last = await responseJson<T>(response);
    if (terminal(last)) return last;
    await page.waitForTimeout(1_000);
  }
  throw new Error(`Timed out polling ${path}; last payload: ${JSON.stringify(last)}`);
}

test("@real-stack login, cited evidence, approval boundary, and exactly-once task", async ({ page }) => {
  test.setTimeout(360_000);
  if (!password) throw new Error("BOOTSTRAP_ADMIN_PASSWORD is required for the real-stack Playwright project");

  await page.goto("/login");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/overview$/);
  const sessionCookieName = process.env.SESSION_COOKIE_NAME ?? "localguard_session";
  const sessionCookie = (await page.context().cookies()).find((cookie) => cookie.name === sessionCookieName);
  expect(sessionCookie, `Expected HttpOnly ${sessionCookieName} cookie`).toBeDefined();
  expect(sessionCookie?.httpOnly).toBe(true);
  expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length }))).toEqual({ local: 0, session: 0 });

  await page.goto("/documents");
  await page.getByRole("button", { name: "Upload document" }).first().click();
  const uploadDialog = page.getByRole("dialog", { name: "Upload a document" });
  await uploadDialog.locator('input[type="file"]').setInputFiles(fixturePath);
  const uploadResponsePromise = page.waitForResponse((response) => new URL(response.url()).pathname === "/api/documents" && response.request().method() === "POST");
  await uploadDialog.getByRole("button", { name: "Upload document" }).click();
  const uploadResponse = await uploadResponsePromise;
  const upload = await responseJson<{ document: { id: string }; revision_id: string }>(uploadResponse);
  const documentId = upload.document.id;

  await pollJson<{ state: string; current_revision: { state: string } | null }>(
    page,
    `/api/documents/${encodeURIComponent(documentId)}`,
    (document) => {
      if (document.state === "failed" || document.current_revision?.state === "failed") throw new Error("Document ingestion failed");
      return document.state === "ready" && document.current_revision?.state === "ready";
    },
  );

  const csrf = await responseJson<{ csrf_token: string }>(await page.request.get("/api/auth/csrf"));
  const mutationHeaders = { "X-CSRF-Token": csrf.csrf_token, "Content-Type": "application/json" };
  const questionResponse = await page.request.post("/api/questions", {
    headers: { ...mutationHeaders, "Idempotency-Key": `e2e-question-${crypto.randomUUID()}` },
    data: { question: "How long does the Service Desk have to disable a vendor account after it receives an offboarding notice?", document_ids: [documentId] },
  });
  const question = await responseJson<{ id: string }>(questionResponse);
  const completedQuestion = await pollJson<{
    state: string;
    error_detail: string | null;
    answer: { text: string; insufficient_evidence: boolean; citations: Array<{ document_id: string; revision_id: string; anchor_key: string; start_offset: number; end_offset: number; quote: string }> } | null;
  }>(page, `/api/questions/${encodeURIComponent(question.id)}`, (job) => {
    if (job.state === "failed") throw new Error(`Question failed: ${job.error_detail ?? "unknown"}`);
    return job.state === "succeeded";
  });
  expect(completedQuestion.answer?.insufficient_evidence).toBe(false);
  expect(`${completedQuestion.answer?.text ?? ""} ${completedQuestion.answer?.citations.map((item) => item.quote).join(" ") ?? ""}`).toMatch(/one hour/i);
  const citation = completedQuestion.answer?.citations[0];
  expect(citation, "Expected a server-resolved immutable citation").toBeDefined();
  expect(citation?.document_id).toBe(documentId);
  expect(citation?.end_offset).toBeGreaterThan(citation?.start_offset ?? -1);

  const citationParameters = new URLSearchParams({
    anchor: citation?.anchor_key ?? "",
    revision_id: citation?.revision_id ?? "",
    start: String(citation?.start_offset ?? ""),
    end: String(citation?.end_offset ?? ""),
  });
  await page.goto(`/documents/${encodeURIComponent(documentId)}?${citationParameters.toString()}`);
  await expect(page.getByRole("heading", { name: "Cited passage" })).toBeVisible();
  await expect(page.locator("mark").first()).not.toBeEmpty();
  await expect(page.getByText(citation?.quote ?? "", { exact: false }).first()).toBeVisible();

  const workflowKey = `e2e-workflow-${crypto.randomUUID()}`;
  const workflowPayload = {
    question: "An authorized sponsor's vendor offboarding notice was received at 2026-09-01T09:00:00Z. Propose the required account-disable task; do not execute it without review.",
    document_ids: [documentId],
  };
  const workflowHeaders = { ...mutationHeaders, "Idempotency-Key": workflowKey };
  const workflowResponse = await page.request.post("/api/workflow-runs", { headers: workflowHeaders, data: workflowPayload });
  const started = await responseJson<{ run: { id: string } }>(workflowResponse);
  const workflowId = started.run.id;

  const samePayloadReplay = await responseJson<{ run: { id: string } }>(await page.request.post("/api/workflow-runs", {
    headers: workflowHeaders,
    data: workflowPayload,
  }));
  expect(samePayloadReplay.run.id).toBe(workflowId);
  const changedPayloadReplay = await page.request.post("/api/workflow-runs", {
    headers: workflowHeaders,
    data: { ...workflowPayload, question: `${workflowPayload.question} Changed payload.` },
    failOnStatusCode: false,
  });
  expect(changedPayloadReplay.status()).toBe(409);
  await expect(changedPayloadReplay.json()).resolves.toMatchObject({ error: { code: "idempotency_payload_mismatch" } });
  await pollJson<{ state: string; error_detail: string | null }>(page, `/api/workflow-runs/${encodeURIComponent(workflowId)}`, (run) => {
    if (["failed", "insufficient"].includes(run.state)) throw new Error(`Workflow did not reach approval: ${run.error_detail ?? run.state}`);
    return run.state === "waiting_approval";
  });

  const proposalList = await responseJson<{ items: Array<{ id: string; workflow_run_id: string; version: number; payload_hash: string; evidence_snapshot_hash: string }> }>(await page.request.get("/api/approvals?offset=0&limit=100"));
  const proposal = proposalList.items.find((item) => item.workflow_run_id === workflowId);
  expect(proposal, "Expected a pending proposal for the workflow").toBeDefined();
  const proposalId = proposal?.id ?? "";

  const tasksBefore = await responseJson<{ items: Array<{ proposal_id: string }> }>(await page.request.get("/api/tasks?offset=0&limit=100"));
  expect(tasksBefore.items.filter((task) => task.proposal_id === proposalId)).toHaveLength(0);

  await page.goto(`/approvals/${encodeURIComponent(proposalId)}`);
  await expect(page.getByText("Nothing has been created yet")).toBeVisible();
  const approveResponsePromise = page.waitForResponse((response) => new URL(response.url()).pathname === `/api/approvals/${proposalId}/approve` && response.request().method() === "POST");
  await page.getByRole("button", { name: "Approve unchanged" }).click();
  const approveResponse = await approveResponsePromise;
  expect(approveResponse.status()).toBe(202);

  const tasksAfter = await pollJson<{ items: Array<{ id: string; proposal_id: string }> }>(page, "/api/tasks?offset=0&limit=100", (payload) => payload.items.filter((task) => task.proposal_id === proposalId).length === 1);
  const matchingTasks = tasksAfter.items.filter((task) => task.proposal_id === proposalId);
  expect(matchingTasks).toHaveLength(1);
  const task = await responseJson<{ id: string; proposal_id: string }>(await page.request.get(`/api/tasks/${encodeURIComponent(matchingTasks[0]?.id ?? "")}`));
  expect(task.proposal_id).toBe(proposalId);

  const replay = await page.request.post(`/api/approvals/${encodeURIComponent(proposalId)}/approve`, {
    headers: mutationHeaders,
    data: {
      version: proposal?.version,
      payload_hash: proposal?.payload_hash,
      evidence_snapshot_hash: proposal?.evidence_snapshot_hash,
      comment: "Real-stack duplicate-approval proof",
    },
    failOnStatusCode: false,
  });
  expect(replay.status()).toBe(409);
  await expect(replay.json()).resolves.toMatchObject({ error: { code: "proposal_not_pending" } });
  const tasksAfterReplay = await responseJson<{ items: Array<{ proposal_id: string }> }>(await page.request.get("/api/tasks?offset=0&limit=100"));
  expect(tasksAfterReplay.items.filter((item) => item.proposal_id === proposalId)).toHaveLength(1);
});
