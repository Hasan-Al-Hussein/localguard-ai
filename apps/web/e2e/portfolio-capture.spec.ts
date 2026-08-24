import { randomUUID } from "node:crypto";
import { mkdir, mkdtemp, readFile, rm } from "node:fs/promises";
import path from "node:path";
import {
  AuditEventsResponseSchema,
  CsrfResponseSchema,
  CurrentUserResponseSchema,
  DecisionAcceptedSchema,
  EvaluationHistoryDetailSchema,
  EvaluationHistoryEntrySchema,
  EvaluationRunSchema,
  ProposalSchema,
  ProposalsResponseSchema,
  QuestionJobSchema,
  TasksResponseSchema,
  WorkflowRunSchema,
  WorkflowStartAcceptedSchema,
  WorkflowTaskSchema,
  type AnswerCitation,
  type AuditEvent,
} from "@localguard/contracts";
import {
  expect,
  test,
  type APIResponse,
  type Page,
  type Request,
  type Response,
} from "@playwright/test";
import type { ZodType } from "zod";
import { publishScreenshotGeneration } from "./portfolio-publication";
import {
  findPortfolioAuditChain,
  isPortfolioCaptureEnabled,
  parsePortfolioArtifacts,
  PORTFOLIO_AUDIT_CHAIN,
  PORTFOLIO_DEMO_ARTIFACT,
  PORTFOLIO_EVALUATION_ARTIFACT,
  PORTFOLIO_RUNTIME_LOCK_ARTIFACT,
  PORTFOLIO_SCREENSHOT_FILENAMES,
  PORTFOLIO_SCREENSHOT_OPTIONS,
  PORTFOLIO_SCREENSHOT_ROOT,
  PORTFOLIO_SCREENSHOTS,
  PORTFOLIO_STAGING_ROOT,
  readPortfolioCredentials,
  validateApprovedProposal,
  validateExecutedProposal,
  validateExecutedTask,
  validateFreshQuestion,
  validatePendingProposal,
  validatePortfolioEvaluation,
  validatePortfolioEvaluationHistoryEntry,
} from "./portfolio-support";

async function responseJson<T>(response: APIResponse | Response, schema: ZodType<T>): Promise<T> {
  if (!response.ok()) {
    const pathname = new URL(response.url()).pathname;
    throw new Error(`Portfolio API request failed with ${response.status()} for ${pathname}`);
  }
  return schema.parse(await response.json() as unknown);
}

async function pollJson<T>(
  page: Page,
  requestPath: string,
  schema: ZodType<T>,
  terminal: (payload: T) => boolean,
  timeoutMs = 360_000,
): Promise<T> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const response = await page.request.get(requestPath, { failOnStatusCode: false });
    const payload = await responseJson(response, schema);
    if (terminal(payload)) return payload;
    await page.waitForTimeout(1_000);
  }
  throw new Error(`Portfolio API polling timed out for ${requestPath.split("?")[0]}`);
}

async function login(
  page: Page,
  credentials: { username: string; password: string },
): Promise<void> {
  await page.goto("/login");
  const usernameInput = page.getByLabel("Username");
  const passwordInput = page.getByLabel("Password", { exact: true });
  await usernameInput.fill(credentials.username);
  await passwordInput.fill(credentials.password);

  const loginResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === "/api/auth/login" && response.request().method() === "POST";
  });
  const passwordClearedAtRequest = new Promise<boolean>((resolve) => {
    const observeLoginRequest = (request: Request) => {
      const url = new URL(request.url());
      if (url.pathname !== "/api/auth/login" || request.method() !== "POST") return;
      page.off("request", observeLoginRequest);
      void passwordInput.inputValue().then(
        (value) => resolve(value === ""),
        () => resolve(false),
      );
    };
    page.on("request", observeLoginRequest);
  });
  await page.getByRole("button", { name: "Sign in" }).click();
  expect(
    await passwordClearedAtRequest,
    "The application must clear the password field before login leaves the browser",
  ).toBe(true);
  const loginResponse = await loginResponsePromise;
  expect(loginResponse.ok(), "The portfolio actor must authenticate successfully").toBe(true);
  await expect(page).toHaveURL(/\/overview$/);

  const currentUser = await responseJson(
    await page.request.get("/api/auth/me"),
    CurrentUserResponseSchema,
  );
  expect(currentUser.username).toBe(credentials.username);
}

async function capture(page: Page, stagingDirectory: string, filename: string): Promise<void> {
  await page.evaluate(async () => document.fonts.ready);
  await page.screenshot({
    path: path.join(stagingDirectory, filename),
    ...PORTFOLIO_SCREENSHOT_OPTIONS,
  });
}

function liveCitationHref(citation: AnswerCitation): string {
  const parameters = new URLSearchParams({
    anchor: citation.anchor_key,
    revision_id: citation.revision_id,
    start: String(citation.start_offset),
    end: String(citation.end_offset),
  });
  return `/documents/${encodeURIComponent(citation.document_id)}?${parameters.toString()}`;
}

test.skip(
  !isPortfolioCaptureEnabled(process.env),
  "portfolio capture requires LOCALGUARD_PORTFOLIO_CAPTURE=1",
);

test("@portfolio-capture publishes real Ollama and approval-boundary portfolio evidence", async ({ page }) => {
  test.setTimeout(900_000);
  page.setDefaultTimeout(30_000);
  page.setDefaultNavigationTimeout(30_000);
  const credentials = readPortfolioCredentials(process.env);
  const [demoBytes, evaluationBytes, runtimeLockBytes] = await Promise.all([
    readFile(PORTFOLIO_DEMO_ARTIFACT, "utf8"),
    readFile(PORTFOLIO_EVALUATION_ARTIFACT, "utf8"),
    readFile(PORTFOLIO_RUNTIME_LOCK_ARTIFACT, "utf8"),
  ]);
  const { demo, evaluation } = parsePortfolioArtifacts(
    JSON.parse(demoBytes) as unknown,
    JSON.parse(evaluationBytes) as unknown,
    JSON.parse(runtimeLockBytes) as unknown,
  );

  await mkdir(PORTFOLIO_STAGING_ROOT, { recursive: true });
  const stagingDirectory = await mkdtemp(path.join(PORTFOLIO_STAGING_ROOT, "run-"));
  try {
    await login(page, credentials.viewer);
    await page.goto("/ask");
    await expect(page.getByRole("heading", { name: "Ask LocalGuard" })).toBeVisible();
    await page.getByLabel("Ask a question about indexed documents").fill(demo.question.prompt);
    const questionResponsePromise = page.waitForResponse((response) => (
      new URL(response.url()).pathname === "/api/questions"
      && response.request().method() === "POST"
    ));
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    const acceptedQuestion = await responseJson(await questionResponsePromise, QuestionJobSchema);
    const completedQuestion = await pollJson(
      page,
      `/api/questions/${encodeURIComponent(acceptedQuestion.id)}`,
      QuestionJobSchema,
      (job) => {
        if (job.state === "failed") {
          throw new Error(`The fresh portfolio question failed: ${job.error_code ?? "unknown"}`);
        }
        return job.state === "succeeded";
      },
    );
    const liveCitation = validateFreshQuestion(completedQuestion, demo);
    const citationHref = liveCitationHref(liveCitation);

    const answerCard = page.locator("article").filter({
      hasText: `Question job: ${completedQuestion.id}`,
    });
    await expect(answerCard).toBeVisible({ timeout: 30_000 });
    for (const paragraph of (completedQuestion.answer?.text ?? "").split(/\n{2,}/).filter(Boolean)) {
      await expect(answerCard.getByText(paragraph, { exact: true })).toBeVisible();
    }
    await answerCard.locator("summary").filter({ hasText: "Answer details" }).click();
    await expect(answerCard.getByText(liveCitation.quote, { exact: false })).toBeVisible();
    await expect(answerCard.getByText(completedQuestion.answer?.model_name ?? "", { exact: true })).toBeVisible();
    const liveCitationLink = answerCard.locator(`a[href="${citationHref}"]`).first();
    await expect(liveCitationLink).toBeVisible();
    await capture(page, stagingDirectory, PORTFOLIO_SCREENSHOTS.ask);

    await liveCitationLink.click();
    await expect(page.getByRole("heading", { name: "Cited passage" })).toBeVisible();
    await expect(page.locator("mark").first()).toContainText(liveCitation.quote);
    const openedUrl = new URL(page.url());
    expect(openedUrl.pathname).toBe(`/documents/${liveCitation.document_id}`);
    expect(Object.fromEntries(openedUrl.searchParams)).toEqual({
      anchor: liveCitation.anchor_key,
      revision_id: liveCitation.revision_id,
      start: String(liveCitation.start_offset),
      end: String(liveCitation.end_offset),
    });
    await capture(page, stagingDirectory, PORTFOLIO_SCREENSHOTS.document);

    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login$/);
    await login(page, credentials.reviewer);

    const latestEvaluation = await responseJson(
      await page.request.get("/api/evaluations/latest"),
      EvaluationHistoryEntrySchema,
    );
    validatePortfolioEvaluationHistoryEntry(latestEvaluation, evaluation, "summary_verified");
    const evaluationDetail = await responseJson(
      await page.request.get(`/api/evaluations/${encodeURIComponent(evaluation.run_id)}`),
      EvaluationHistoryDetailSchema,
    );
    validatePortfolioEvaluationHistoryEntry(
      evaluationDetail.metadata,
      evaluation,
      "run_verified",
    );
    if (evaluationDetail.current_run === null || evaluationDetail.legacy_run_metadata !== null) {
      throw new Error("The portfolio evaluation detail is not a verified current-schema run");
    }
    const liveEvaluation = EvaluationRunSchema.parse(evaluationDetail.current_run);
    validatePortfolioEvaluation(liveEvaluation, evaluation, demo);

    await page.goto("/overview");
    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
    await expect(page.locator(`a[href="/evaluations/${evaluation.run_id}"]`)).toBeVisible();
    await expect(page.getByText("ollama", { exact: true })).toBeVisible();
    await expect(page.getByText("25/25 cases completed", { exact: true })).toBeVisible();
    await capture(page, stagingDirectory, PORTFOLIO_SCREENSHOTS.overview);

    const csrf = await responseJson(
      await page.request.get("/api/auth/csrf"),
      CsrfResponseSchema,
    );
    const mutationHeaders = {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrf.csrf_token,
    };
    const workflowResponse = await page.request.post("/api/workflow-runs", {
      headers: {
        ...mutationHeaders,
        "Idempotency-Key": `portfolio-workflow-${randomUUID()}`,
      },
      data: {
        question: demo.approval_workflow.prompt,
        document_ids: [demo.document.document_id],
      },
    });
    const workflow = await responseJson(workflowResponse, WorkflowStartAcceptedSchema);
    const workflowId = workflow.run.id;
    await pollJson(
      page,
      `/api/workflow-runs/${workflowId}`,
      WorkflowRunSchema,
      (run) => {
        if (["failed", "insufficient", "rejected"].includes(run.state)) {
          throw new Error(`The portfolio workflow stopped in terminal state ${run.state}`);
        }
        return run.state === "waiting_approval";
      },
    );

    const proposals = await pollJson(
      page,
      "/api/approvals?offset=0&limit=100",
      ProposalsResponseSchema,
      (payload) => payload.items.some((item) => item.workflow_run_id === workflowId),
      60_000,
    );
    const proposal = proposals.items.find((item) => item.workflow_run_id === workflowId);
    if (!proposal) throw new Error("The fresh portfolio workflow did not create a proposal");
    validatePendingProposal(proposal, workflowId, demo);
    const proposalId = proposal.id;

    const tasksBefore = await responseJson(
      await page.request.get("/api/tasks?offset=0&limit=100"),
      TasksResponseSchema,
    );
    expect(tasksBefore.items.filter((item) => item.proposal_id === proposalId)).toHaveLength(0);

    await page.goto(`/approvals/${proposalId}`);
    await expect(page.getByText("Nothing has been created yet", { exact: true })).toBeVisible();
    await expect(page.getByText("Service Desk", { exact: true })).toBeVisible();
    await expect(page.getByText("high", { exact: true })).toBeVisible();
    await expect(page.getByText(/LG-POL-001:L010/)).toBeVisible();
    await capture(page, stagingDirectory, PORTFOLIO_SCREENSHOTS.pendingApproval);

    let approvalPostCount = 0;
    const countApprovalRequest = (request: Request) => {
      const url = new URL(request.url());
      if (
        url.pathname === `/api/approvals/${proposalId}/approve`
        && request.method() === "POST"
      ) approvalPostCount += 1;
    };
    page.on("request", countApprovalRequest);
    const approvalResponsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return url.pathname === `/api/approvals/${proposalId}/approve`
        && response.request().method() === "POST";
    });
    await page.getByRole("button", { name: "Approve unchanged" }).click();
    const approvalResponse = await approvalResponsePromise;
    page.off("request", countApprovalRequest);
    expect(approvalResponse.status()).toBe(202);
    expect(approvalPostCount, "The capture lane must submit approval exactly once").toBe(1);
    const acceptedDecision = await responseJson(approvalResponse, DecisionAcceptedSchema);
    expect(acceptedDecision.replacement).toBeNull();
    expect(acceptedDecision.decision).toMatchObject({
      proposal_id: proposalId,
      proposal_version: proposal.version,
      decision: "approve",
      payload_hash: proposal.payload_hash,
      evidence_snapshot_hash: proposal.evidence_snapshot_hash,
    });
    validateApprovedProposal(acceptedDecision.proposal, proposal);

    const tasksAfter = await pollJson(
      page,
      "/api/tasks?offset=0&limit=100",
      TasksResponseSchema,
      (payload) => {
        const matching = payload.items.filter((item) => item.proposal_id === proposalId);
        if (matching.length > 1) throw new Error("Approval created more than one matching task");
        return matching.length === 1;
      },
    );
    const matchingTasks = tasksAfter.items.filter((item) => item.proposal_id === proposalId);
    expect(matchingTasks).toHaveLength(1);
    const taskId = matchingTasks[0]?.id;
    if (!taskId) throw new Error("The approved portfolio task has no identifier");
    const task = await responseJson(
      await page.request.get(`/api/tasks/${encodeURIComponent(taskId)}`),
      WorkflowTaskSchema,
    );
    validateExecutedTask(task, proposal);
    expect(task.approval_decision_id).toBe(acceptedDecision.decision.id);
    const executedProposal = await responseJson(
      await page.request.get(`/api/approvals/${encodeURIComponent(proposalId)}`),
      ProposalSchema,
    );
    validateExecutedProposal(executedProposal, proposal);

    await page.goto(`/tasks/${taskId}`);
    await expect(page.getByRole("heading", { name: "Approval provenance" })).toBeVisible();
    await expect(page.locator(`a[href="/approvals/${proposalId}"]`)).toBeVisible();
    await expect(page.getByText(task.title, { exact: true })).toBeVisible();
    await capture(page, stagingDirectory, PORTFOLIO_SCREENSHOTS.task);

    const auditEvents = await pollJson(
      page,
      "/api/audit-events?offset=0&limit=100",
      AuditEventsResponseSchema,
      (payload) => findPortfolioAuditChain(payload.items, {
          workflowId,
          proposalId,
          decisionId: acceptedDecision.decision.id,
          taskId,
        }) !== null,
      60_000,
    );
    const auditChain: AuditEvent[] | null = findPortfolioAuditChain(auditEvents.items, {
      workflowId,
      proposalId,
      decisionId: acceptedDecision.decision.id,
      taskId,
    });
    if (!auditChain) throw new Error("The fresh workflow audit chain is incomplete");
    expect(auditChain).toHaveLength(PORTFOLIO_AUDIT_CHAIN.length);

    await page.goto(`/audit?thread=${encodeURIComponent(workflowId)}`);
    await expect(page.getByRole("heading", { name: "Workflow audit chain" })).toBeVisible();
    await expect(page.getByText(workflowId, { exact: true }).first()).toBeVisible();
    for (const requirement of PORTFOLIO_AUDIT_CHAIN) {
      const row = page.getByRole("row")
        .filter({ hasText: requirement.action })
        .filter({ hasText: requirement.outcome });
      await expect(row.first()).toBeVisible();
    }
    await capture(page, stagingDirectory, PORTFOLIO_SCREENSHOTS.audit);

    await page.goto(`/evaluations/${evaluation.run_id}`);
    await expect(page.getByRole("heading", { name: evaluation.run_id })).toBeVisible();
    await expect(page.getByText(/ollama runtime/i)).toBeVisible();
    await expect(page.getByText("25/25", { exact: true })).toBeVisible();
    const runtimeIdentity = page.getByRole("region", { name: "Runtime model identity" });
    await expect(runtimeIdentity.getByText(
      evaluation.runtime_model_identity.chat_model_name,
      { exact: true },
    )).toBeVisible();
    await expect(runtimeIdentity.getByText(
      evaluation.runtime_model_identity.chat_model_digest,
      { exact: true },
    )).toBeVisible();
    await expect(runtimeIdentity.getByText(
      evaluation.runtime_model_identity.embedding_model_name,
      { exact: true },
    )).toBeVisible();
    await expect(runtimeIdentity.getByText(
      evaluation.runtime_model_identity.embedding_model_digest,
      { exact: true },
    )).toBeVisible();
    await expect(runtimeIdentity.getByText(
      evaluation.structured_extraction_mode,
      { exact: true },
    )).toBeVisible();
    const provenance = page.getByRole("region", { name: "Claim provenance" });
    await expect(provenance).toBeVisible();
    for (const caseId of evaluation.claim_provenance.deterministic_normalizer_case_ids) {
      await expect(provenance.getByText(caseId, { exact: false })).toBeVisible();
    }
    const corpusIntegrity = page.getByRole("region", { name: "Corpus integrity" });
    await expect(corpusIntegrity.getByText(evaluation.cases_sha256, { exact: true })).toBeVisible();
    await expect(corpusIntegrity.getByText(
      evaluation.corpus_bundle_sha256,
      { exact: true },
    )).toBeVisible();
    await capture(page, stagingDirectory, PORTFOLIO_SCREENSHOTS.evaluation);

    await publishScreenshotGeneration(
      stagingDirectory,
      PORTFOLIO_SCREENSHOT_ROOT,
      PORTFOLIO_SCREENSHOT_FILENAMES,
    );
  } finally {
    await rm(stagingDirectory, { recursive: true, force: true });
  }
});
