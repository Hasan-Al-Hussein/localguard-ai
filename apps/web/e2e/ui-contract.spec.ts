import { expect, test, type Page, type Route } from "@playwright/test";
import type { OverviewResponse } from "@localguard/contracts";

const documentId = "11111111-1111-4111-8111-111111111111";
const currentRevisionId = "22222222-2222-4222-8222-222222222222";
const historicalRevisionId = "99999999-9999-4999-8999-999999999999";
const workflowId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const proposalId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const user = { id: "33333333-3333-4333-8333-333333333333", username: "reviewer", display_name: "Rana Reviewer", role: "reviewer" };
const viewer = { ...user, id: "44444444-4444-4444-8444-444444444444", username: "viewer", display_name: "Vera Viewer", role: "viewer" };

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

const overview: OverviewResponse = {
  documents_total: 1,
  documents_ready: 1,
  documents_processing: 0,
  questions_total: 0,
  questions_failed: 0,
  recent_documents: [],
  pending_approvals: 0,
  extracted_deadlines: [],
  recent_activity: [],
  evaluation_summary: null,
};

async function mockAuthenticatedApi(page: Page, activeUser = user, overviewPayload = overview) {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/auth/me") return json(route, activeUser);
    if (path === "/api/auth/csrf") return json(route, { csrf_token: "playwright-csrf-token" });
    if (path === "/api/health/live") return json(route, { status: "ok", checks: {} });
    if (path === "/api/overview") return json(route, overviewPayload);
    return json(route, { error: { code: "not_mocked", message: `No UI-contract fixture for ${path}`, correlation_id: "corr-unmocked" } }, 404);
  });
}

test.describe("UI contract (intercepted API)", () => {
  test("signs in through the intercepted authentication contract", async ({ page, isMobile }) => {
    let authenticated = false;
    await page.route("**/api/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/api/auth/me") return authenticated ? json(route, user) : json(route, { error: { code: "unauthorized", message: "Sign in required", correlation_id: "corr-auth" } }, 401);
      if (path === "/api/auth/login") { authenticated = true; return json(route, { user, csrf_token: "playwright-csrf-token" }); }
      if (path === "/api/health/live") return json(route, { status: "ok", checks: {} });
      if (path === "/api/overview") return json(route, overview);
      return json(route, { error: { code: "not_mocked", message: path, correlation_id: "corr-unmocked" } }, 404);
    });

    await page.goto("/login");
    await page.getByLabel("Username").fill("reviewer");
    await page.locator("#password").fill("local-only-password");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/overview$/);
    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
    if (isMobile) await expect(page.getByRole("button", { name: "Open navigation" })).toBeVisible();
    else await expect(page.getByText("Local · Private")).toBeVisible();
  });

  test("mobile drawer traps focus, closes with Escape, and restores focus", async ({ page, isMobile }) => {
    test.skip(!isMobile, "Mobile drawer keyboard contract");
    await mockAuthenticatedApi(page);
    await page.goto("/overview");
    const trigger = page.getByRole("button", { name: "Open navigation" });
    await trigger.focus();
    await trigger.click();
    const dialog = page.getByRole("dialog", { name: "Workspace navigation" });
    const close = dialog.getByRole("button", { name: "Close navigation" });
    await expect(close).toBeFocused();
    await expect(page.getByRole("main").evaluate((element) => Boolean(element.parentElement?.inert))).resolves.toBe(true);
    await page.keyboard.press("Shift+Tab");
    await expect(dialog.locator(":focus")).toHaveCount(1);
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(trigger).toBeFocused();
  });

  test("keeps a corrupt latest evaluation visible without inventing metrics", async ({ page }) => {
    const runId = "20260823T080500000000Z-ollama-aaaaaaaaaaaa";
    await mockAuthenticatedApi(page, user, {
      ...overview,
      evaluation_summary: {
        run_id: runId,
        schema_version: null,
        runtime_provider: null,
        completed_case_count: null,
        case_count: null,
        safety_passed: null,
        quality_passed: null,
        run_passed: null,
        integrity_status: "corrupt",
        integrity_note: "The stored summary is malformed.",
        comparability_status: "unavailable",
        comparability_note: "Metric comparability cannot be established.",
      },
    });

    await page.goto("/overview");
    await expect(page.getByText("Corrupt artifact", { exact: true })).toBeVisible();
    await expect(page.getByText("Case metrics unavailable", { exact: true })).toBeVisible();
    await expect(page.getByText("The stored summary is malformed.", { exact: true })).toBeVisible();
    await expect(page.locator(`a[href="/evaluations/${runId}"]`)).toBeVisible();
  });

  test("labels legacy evaluation history and renders metadata without current metrics", async ({ page }) => {
    const runId = "20260823T080500000000Z-ollama-bbbbbbbbbbbb";
    const metadata = {
      schema_version: "1.1.0",
      run_id: runId,
      dataset_version: "1.0.1",
      dataset_sha256: "a".repeat(64),
      requested_provider: "ollama",
      runtime_provider: "ollama",
      completed_case_count: 25,
      case_count: 25,
      safety_passed: true,
      quality_passed: false,
      run_passed: false,
      raw_result_sha256: "b".repeat(64),
      comparability_status: "legacy_metadata_only",
      comparability_note: "Schema 1.1.0 metrics are not directly comparable with schema 1.2.0.",
      integrity_status: "summary_verified",
      integrity_note: "The summary identity was verified.",
    };
    await mockAuthenticatedApi(page);
    await page.route("**/api/evaluations?**", (route) => json(route, {
      items: [metadata],
      total: 1,
      offset: 0,
      limit: 25,
    }));
    await page.route(`**/api/evaluations/${runId}`, (route) => json(route, {
      metadata: {
        ...metadata,
        integrity_status: "run_verified",
        integrity_note: "The exact legacy run bytes were verified.",
      },
      current_run: null,
      legacy_run_metadata: {
        schema_version: "1.1.0",
        run_id: runId,
        started_at: "2026-08-23T08:00:00Z",
        completed_at: "2026-08-23T08:05:00Z",
        wall_clock_ms: 300_000,
        warmup_completed: true,
      },
    }));

    await page.goto("/evaluations");
    const historySurface = page.locator(`[data-table-surface="${(page.viewportSize()?.width ?? 0) < 1440 ? "cards" : "table"}"]`);
    await expect(historySurface.getByText("Legacy metadata", { exact: true })).toBeVisible();
    await historySurface.getByRole("link", { name: runId }).click();
    await expect(page).toHaveURL(new RegExp(`/evaluations/${runId}$`), { timeout: 15_000 });
    await expect(page.getByText("Legacy metadata only", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Stored artifact metadata" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Legacy run timing" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Case results" })).toHaveCount(0);
  });

  test("resolves an exact historical citation range after reprocessing", async ({ page }) => {
    await mockAuthenticatedApi(page);
    await page.route("**/api/documents/**", async (route) => {
      const url = new URL(route.request().url());
      if (url.pathname.includes(`/revisions/${historicalRevisionId}/anchors/`)) {
        expect(url.searchParams.get("start_offset")).toBe("4");
        expect(url.searchParams.get("end_offset")).toBe("39");
        return json(route, {
          document_id: documentId,
          revision_id: historicalRevisionId,
          anchor_key: "lines:10-12",
          anchor_label: "Lines 10–12",
          kind: "text_lines",
          anchor_start_offset: 0,
          anchor_end_offset: 60,
          requested_start_offset: 4,
          requested_end_offset: 39,
          text: "Historical one-hour offboarding rule",
        });
      }
      return json(route, {
        id: documentId, title: "Vendor access policy.txt", state: "ready", current_revision_id: currentRevisionId,
        created_at: "2026-08-20T10:00:00Z", updated_at: "2026-08-23T10:00:00Z",
        current_revision: { id: currentRevisionId, revision_number: 2, original_filename: "Vendor access policy.txt", media_type: "text/plain", byte_size: 1000, content_sha256: "abc123", state: "ready", extracted_characters: 50, anchor_count: 1, created_at: "2026-08-23T10:00:00Z" },
        anchors: [{ id: "55555555-5555-4555-8555-555555555555", stable_key: "lines:10-12", kind: "text_lines", label: "Lines 10–12", ordinal: 1, start_offset: 0, end_offset: 50, text: "The current revision contains different wording." }],
      });
    });

    await page.goto(`/documents/${documentId}?anchor=lines%3A10-12&revision_id=${historicalRevisionId}&start=4&end=39`);
    await expect(page.getByRole("heading", { name: "Cited passage" })).toBeVisible();
    await expect(page.getByText("Historical revision", { exact: false })).toBeVisible();
    await expect(page.locator("mark").first()).toHaveText("Historical one-hour offboarding rule");
    await expect(page.getByText("The current revision contains different wording.")).toBeVisible();
  });

  test("makes insufficient evidence explicit without fabricating a citation", async ({ page }) => {
    await mockAuthenticatedApi(page);
    await page.route("**/api/questions", async (route) => json(route, {
      id: "77777777-7777-4777-8777-777777777777", question: "What is the overseas retention rule?", document_ids: [], state: "succeeded",
      error_code: null, error_detail: null, created_at: "2026-08-23T10:00:00Z", updated_at: "2026-08-23T10:00:01Z",
      answer: { id: "88888888-8888-4888-8888-888888888888", text: "The indexed documents do not establish an overseas retention rule.", insufficient_evidence: true, model_name: "qwen3:1.7b-q4_K_M", prompt_version: "v1", retrieval_ms: 12, generation_ms: 30, created_at: "2026-08-23T10:00:01Z", citations: [] },
    }));
    await page.goto("/ask");
    await page.getByLabel("Ask a question about indexed documents").fill("What is the overseas retention rule?");
    await page.getByRole("button", { name: "Ask" }).click();
    await expect(page.getByText("The indexed evidence is not sufficient")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Sources" })).toHaveCount(0);
  });

  test("keeps an action proposal inert and routes reviewers to its binding", async ({ page }) => {
    await mockAuthenticatedApi(page);
    const run = { id: workflowId, requested_by_id: user.id, question: "Create a task for one-hour offboarding.", document_ids: [documentId], state: "waiting_approval", intent: "workflow_action", answer_text: "The policy requires one-hour offboarding.", insufficient_evidence: false, cited_chunk_ids: ["LG-POL-001:L010"], error_code: null, error_detail: null, created_at: "2026-08-23T10:00:00Z", updated_at: "2026-08-23T10:00:01Z" };
    await page.route("**/api/workflow-runs", (route) => {
      const idempotencyKey = route.request().headers()["idempotency-key"];
      expect(idempotencyKey).toMatch(/^[-0-9a-f]{8,128}$/);
      return json(route, { run, dispatch_job_id: "job-1" }, 202);
    });
    await page.route(`**/api/workflow-runs/${workflowId}`, (route) => json(route, run));
    await page.route("**/api/findings?**", (route) => json(route, { items: [{
      id: "66666666-6666-4666-8666-666666666666",
      workflow_run_id: workflowId,
      finding_type: "required_action",
      summary: "The Service Desk must disable the vendor account within one hour.",
      normalized_value: "2026-09-01T10:00:00Z",
      responsible_party: "Service Desk",
      due_date: "2026-09-01",
      severity: "high",
      cited_chunk_ids: ["chunk-lg-pol-001-l010"],
      cited_marker_ids: ["LG-POL-001:L010"],
      fields: {
        actor: "Service Desk",
        action: "Disable vendor account",
        deadline: "2026-09-01T10:00:00Z",
      },
      origin: "deterministic_evidence_normalizer",
      normalizer_version: "structured-obligation-binding-v2",
      source_marker_sha256: "c".repeat(64),
      derivation_reason: "evidence_binding_confirmed",
      evidence: [],
      created_at: "2026-08-23T10:00:01Z",
    }], total: 1, offset: 0, limit: 100 }));
    await page.route("**/api/approvals?**", (route) => json(route, { items: [{ id: proposalId, workflow_run_id: workflowId, created_by_id: user.id, previous_proposal_id: null, version: 1, kind: "workflow_task", state: "pending", title: "Offboard vendor access", description: "Disable access within one hour.", assignee: "IAM", priority: "high", due_at: null, reasoning_summary: "Grounded in LG-POL-001:L010", cited_chunk_ids: ["LG-POL-001:L010"], evidence: [], payload_hash: "a".repeat(64), evidence_snapshot_hash: "b".repeat(64), expires_at: "2026-08-24T10:00:00Z", created_at: "2026-08-23T10:00:01Z", updated_at: "2026-08-23T10:00:01Z" }], total: 1, offset: 0, limit: 100 }));
    await page.goto("/ask");
    await page.getByText("Propose an action", { exact: true }).click();
    await page.getByLabel("Describe an action to ground in indexed documents").fill("Create a task for one-hour offboarding.");
    await page.getByRole("button", { name: "Analyze action" }).click();
    await expect(page.getByText("Human approval is required")).toBeVisible();
    await expect(page.getByRole("link", { name: "Review proposal" })).toHaveAttribute("href", `/approvals/${proposalId}`);
    await expect(page.getByText("No task exists until", { exact: false })).toBeVisible();
    await expect(page.getByText("Disable vendor account", { exact: true })).toBeVisible();
    await expect(page.getByText("2026-09-01T10:00:00Z", { exact: true })).toBeVisible();
    await page.getByText("Finding provenance", { exact: true }).click();
    await expect(page.getByText("structured-obligation-binding-v2", { exact: true })).toBeVisible();
    await expect(page.getByText("LG-POL-001:L010", { exact: true })).toBeVisible();
  });

  test("viewer sees truthful RBAC boundaries", async ({ page }) => {
    await mockAuthenticatedApi(page, viewer);
    await page.goto(`/approvals/${proposalId}`);
    await expect(page.getByText("Reviewer role required")).toBeVisible();
    await expect(page.getByRole("button", { name: /Approve/ })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Approvals" })).toHaveCount(0);
  });
});
