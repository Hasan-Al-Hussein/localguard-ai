import {
  AuditEventSchema,
  AuditEventsResponseSchema,
  CurrentUserResponseSchema,
  DecisionAcceptedSchema,
  DocumentDetailSchema,
  DocumentsResponseSchema,
  EvaluationHistoryDetailSchema,
  EvaluationHistoryListSchema,
  FindingsResponseSchema,
  OverviewResponseSchema,
  ProposalSchema,
  ProposalsResponseSchema,
  QuestionJobSchema,
  RevisionSectionSchema,
  ServiceHealthSchema,
  TasksResponseSchema,
  WorkflowStartAcceptedSchema,
} from "@localguard/contracts";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";
import {
  PUBLIC_DEMO_FIXTURES,
  PUBLIC_DEMO_IDS,
  publicDemoApiRequest,
  resetPublicDemoState,
} from "../lib/public-demo";

beforeEach(() => {
  resetPublicDemoState();
});

describe("publicDemoApiRequest", () => {
  it("serves contract-valid reviewer, health, and overview fixtures without fetch", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    const [reviewer, health, overview] = await Promise.all([
      publicDemoApiRequest("/auth/me", CurrentUserResponseSchema),
      publicDemoApiRequest("/health/live", ServiceHealthSchema),
      publicDemoApiRequest("/overview", OverviewResponseSchema),
    ]);

    expect(reviewer).toMatchObject({ id: PUBLIC_DEMO_IDS.reviewer, role: "reviewer" });
    expect(health.checks.persistence).toBe("browser_memory_only");
    expect(overview).toMatchObject({ documents_total: 3, pending_approvals: 1 });
    expect(overview.evaluation_summary?.run_id).toBe(PUBLIC_DEMO_IDS.evaluationRun);
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it("resolves every synthetic document and its exact citation range", async () => {
    const list = await publicDemoApiRequest("/documents?offset=0&limit=15", DocumentsResponseSchema);
    expect(list.items).toHaveLength(3);

    for (const summary of list.items) {
      const detail = await publicDemoApiRequest(`/documents/${summary.id}`, DocumentDetailSchema);
      expect(detail.current_revision_id).toBeTruthy();
      expect(detail.anchors).not.toHaveLength(0);
    }

    const evidence = PUBLIC_DEMO_FIXTURES.finding.evidence?.[0];
    expect(evidence?.end_offset).toBeTypeOf("number");
    const section = await publicDemoApiRequest(
      `/documents/${PUBLIC_DEMO_IDS.vendorDocument}/revisions/${PUBLIC_DEMO_IDS.vendorRevision}/anchors/lines%3A10-13?start_offset=0&end_offset=${evidence?.end_offset}`,
      RevisionSectionSchema,
    );
    expect(section.text).toContain("within one hour");
    expect(section.requested_end_offset).toBe(evidence?.end_offset);
  });

  it("returns grounded evidence for covered questions and abstains for unsupported claims", async () => {
    const grounded = await publicDemoApiRequest("/questions", QuestionJobSchema, {
      method: "POST",
      body: JSON.stringify({ question: "When must the Service Desk disable a vendor account?" }),
    });
    expect(grounded.answer).toMatchObject({ insufficient_evidence: false });
    expect(grounded.answer?.citations).toHaveLength(1);

    const abstention = await publicDemoApiRequest("/questions", QuestionJobSchema, {
      method: "POST",
      body: JSON.stringify({ question: "What is the overseas data-retention period?" }),
    });
    expect(abstention.answer).toMatchObject({ insufficient_evidence: true });
    expect(abstention.answer?.citations).toEqual([]);

    await expect(
      publicDemoApiRequest(`/questions/${grounded.id}`, QuestionJobSchema),
    ).resolves.toEqual(grounded);
    await expect(
      publicDemoApiRequest(`/questions/${abstention.id}`, QuestionJobSchema),
    ).resolves.toEqual(abstention);
  });

  it("simulates the bounded workflow and creates exactly one memory-only task after approval", async () => {
    const accepted = await publicDemoApiRequest("/workflow-runs", WorkflowStartAcceptedSchema, {
      method: "POST",
      body: JSON.stringify({
        question: "Create a task for the one-hour vendor offboarding requirement.",
        document_ids: [PUBLIC_DEMO_IDS.vendorDocument],
      }),
    });
    expect(accepted.run).toMatchObject({
      id: PUBLIC_DEMO_IDS.workflow,
      state: "waiting_approval",
    });

    const findings = await publicDemoApiRequest(
      `/findings?workflow_run_id=${PUBLIC_DEMO_IDS.workflow}&offset=0&limit=100`,
      FindingsResponseSchema,
    );
    expect(findings.items).toHaveLength(1);
    expect(findings.items[0].origin).toBe("deterministic_evidence_normalizer");

    const proposal = await publicDemoApiRequest(
      `/approvals/${PUBLIC_DEMO_IDS.proposal}`,
      ProposalSchema,
    );
    const approvalBody = JSON.stringify({
      version: proposal.version,
      payload_hash: proposal.payload_hash,
      evidence_snapshot_hash: proposal.evidence_snapshot_hash,
      comment: "Approve the browser-only demonstration task.",
    });
    const first = await publicDemoApiRequest(
      `/approvals/${PUBLIC_DEMO_IDS.proposal}/approve`,
      DecisionAcceptedSchema,
      { method: "POST", body: approvalBody },
    );
    const second = await publicDemoApiRequest(
      `/approvals/${PUBLIC_DEMO_IDS.proposal}/approve`,
      DecisionAcceptedSchema,
      { method: "POST", body: approvalBody },
    );

    expect(first.task?.id).toBe(PUBLIC_DEMO_IDS.createdTask);
    expect(second.task?.id).toBe(PUBLIC_DEMO_IDS.createdTask);
    const tasks = await publicDemoApiRequest("/tasks?offset=0&limit=15", TasksResponseSchema);
    expect(tasks.items.filter((task) => task.id === PUBLIC_DEMO_IDS.createdTask)).toHaveLength(1);

    const approvals = await publicDemoApiRequest("/approvals?offset=0&limit=15", ProposalsResponseSchema);
    expect(approvals.items[0].state).toBe("approved");
    const overview = await publicDemoApiRequest("/overview", OverviewResponseSchema);
    expect(overview.pending_approvals).toBe(0);
  });

  it("serves evaluation and audit list/detail routes through their published contracts", async () => {
    const evaluations = await publicDemoApiRequest(
      "/evaluations?offset=0&limit=25",
      EvaluationHistoryListSchema,
    );
    expect(evaluations.items[0].run_id).toBe(PUBLIC_DEMO_IDS.evaluationRun);
    await expect(
      publicDemoApiRequest(
        `/evaluations/${PUBLIC_DEMO_IDS.evaluationRun}`,
        EvaluationHistoryDetailSchema,
      ),
    ).resolves.toMatchObject({ current_run: { gates: { run_passed: true } } });

    const events = await publicDemoApiRequest(
      "/audit-events?offset=0&limit=15",
      AuditEventsResponseSchema,
    );
    expect(events.items.length).toBeGreaterThan(2);
    await expect(
      publicDemoApiRequest(`/audit-events/${events.items[0].id}`, AuditEventSchema),
    ).resolves.toEqual(events.items[0]);
  });

  it.each([
    ["/auth/login", "POST", JSON.stringify({ username: "demo", password: "not-used" })],
    ["/auth/logout", "POST", undefined],
    ["/documents", "POST", new FormData()],
    [`/documents/${PUBLIC_DEMO_IDS.vendorDocument}`, "DELETE", undefined],
    [`/documents/${PUBLIC_DEMO_IDS.vendorDocument}/reprocess`, "POST", undefined],
    [`/tasks/${PUBLIC_DEMO_IDS.historicalTask}`, "PATCH", JSON.stringify({ state: "open" })],
    [`/approvals/${PUBLIC_DEMO_IDS.proposal}/reject`, "POST", JSON.stringify({ comment: "no" })],
    [`/approvals/${PUBLIC_DEMO_IDS.proposal}/edit`, "POST", JSON.stringify({ title: "changed" })],
  ])("fails closed with demo_read_only for %s", async (path, method, body) => {
    const request = publicDemoApiRequest(path, z.unknown(), { method, body });
    await expect(request).rejects.toMatchObject({
      status: 403,
      code: "demo_read_only",
    });
  });

  it("resets every simulated mutation and rejects a caller-supplied incompatible output schema", async () => {
    const proposal = await publicDemoApiRequest(
      `/approvals/${PUBLIC_DEMO_IDS.proposal}`,
      ProposalSchema,
    );
    await publicDemoApiRequest(
      `/approvals/${PUBLIC_DEMO_IDS.proposal}/approve`,
      DecisionAcceptedSchema,
      {
        method: "POST",
        body: JSON.stringify({
          version: proposal.version,
          payload_hash: proposal.payload_hash,
          evidence_snapshot_hash: proposal.evidence_snapshot_hash,
        }),
      },
    );

    resetPublicDemoState();
    const tasks = await publicDemoApiRequest("/tasks?offset=0&limit=15", TasksResponseSchema);
    const approval = await publicDemoApiRequest(
      `/approvals/${PUBLIC_DEMO_IDS.proposal}`,
      ProposalSchema,
    );
    expect(tasks.items).toHaveLength(1);
    expect(approval.state).toBe("pending");

    await expect(
      publicDemoApiRequest("/overview", z.object({ impossible: z.literal(true) })),
    ).rejects.toMatchObject({
      status: 500,
      code: "invalid_demo_fixture",
    });
  });
});
