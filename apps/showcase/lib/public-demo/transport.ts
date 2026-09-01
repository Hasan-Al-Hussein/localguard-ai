import {
  ApprovalDecisionRequestSchema,
  QuestionRequestSchema,
  WorkflowRunRequestSchema,
  type AuditEvent,
  type DocumentDetail,
  type Proposal,
} from "@localguard/contracts";
import type { z } from "zod";
import {
  PUBLIC_DEMO_APPROVAL_AUDIT_EVENT,
  PUBLIC_DEMO_CREATED_TASK,
  PUBLIC_DEMO_DECISION,
  PUBLIC_DEMO_DOCUMENTS,
  PUBLIC_DEMO_EVALUATION_DETAIL,
  PUBLIC_DEMO_EVALUATION_LIST,
  PUBLIC_DEMO_FINDING,
  PUBLIC_DEMO_FIXTURES,
  createGroundedQuestion,
  createInitialPublicDemoState,
  createInsufficientQuestion,
} from "./fixtures";
import {
  PUBLIC_DEMO_CORRELATION_IDS,
  PUBLIC_DEMO_IDS,
  PUBLIC_DEMO_TIMESTAMPS,
} from "./ids";

type PublicDemoRequestOptions = Omit<RequestInit, "credentials"> & {
  csrf?: boolean;
};

type Pagination = {
  offset: number;
  limit: number;
};

let state = createInitialPublicDemoState();

export class PublicDemoApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly correlationId = "demo-corr-read-only",
  ) {
    super(message);
    this.name = "PublicDemoApiError";
  }
}

function clone<T>(value: T): T {
  return structuredClone(value);
}

function parseOutput<T>(payload: unknown, schema: z.ZodType<T>): T {
  const result = schema.safeParse(clone(payload));
  if (!result.success) {
    throw new PublicDemoApiError(
      "The synthetic showcase fixture did not match the LocalGuard contract.",
      500,
      "invalid_demo_fixture",
      "demo-corr-contract-validation",
    );
  }
  return result.data;
}

function requestError(message: string): PublicDemoApiError {
  return new PublicDemoApiError(message, 400, "demo_invalid_request", "demo-corr-invalid-request");
}

function notFound(resource = "record"): PublicDemoApiError {
  return new PublicDemoApiError(
    `The requested synthetic ${resource} is not available.`,
    404,
    "demo_not_found",
    "demo-corr-not-found",
  );
}

function readOnly(): PublicDemoApiError {
  return new PublicDemoApiError(
    "This public showcase is read-only. Refresh the page to reset the browser-only walkthrough.",
    403,
    "demo_read_only",
  );
}

function readJsonBody(body: BodyInit | null | undefined): unknown {
  if (typeof body !== "string") {
    throw requestError("The synthetic showcase accepts JSON request bodies only.");
  }
  try {
    return JSON.parse(body) as unknown;
  } catch {
    throw requestError("The request body must contain valid JSON.");
  }
}

function decodeSegment(value: string): string {
  try {
    const decoded = decodeURIComponent(value);
    if (decoded.includes("/") || decoded.includes("\\")) throw notFound();
    return decoded;
  } catch (error) {
    if (error instanceof PublicDemoApiError) throw error;
    throw requestError("The request path contains invalid encoding.");
  }
}

function parsePath(path: string): { url: URL; segments: string[] } {
  if (!path.startsWith("/") || path.startsWith("//")) {
    throw requestError("API paths must be same-origin relative paths.");
  }
  const url = new URL(path, "https://localguard-showcase.invalid");
  if (url.origin !== "https://localguard-showcase.invalid" || url.hash) {
    throw requestError("API paths must be same-origin relative paths without fragments.");
  }
  const segments = url.pathname
    .split("/")
    .filter(Boolean)
    .map(decodeSegment);
  return { url, segments };
}

function parsePagination(url: URL, defaultLimit: number): Pagination {
  const rawOffset = url.searchParams.get("offset") ?? "0";
  const rawLimit = url.searchParams.get("limit") ?? String(defaultLimit);
  if (!/^\d+$/.test(rawOffset) || !/^\d+$/.test(rawLimit)) {
    throw requestError("Pagination values must be non-negative integers.");
  }
  const offset = Number(rawOffset);
  const limit = Number(rawLimit);
  if (!Number.isSafeInteger(offset) || !Number.isSafeInteger(limit) || limit < 1 || limit > 100) {
    throw requestError("Pagination is outside the supported synthetic showcase range.");
  }
  return { offset, limit };
}

function paginate<T>(items: T[], pagination: Pagination): T[] {
  return items.slice(pagination.offset, pagination.offset + pagination.limit);
}

function documentSummary(document: DocumentDetail) {
  return {
    id: document.id,
    title: document.title,
    state: document.state,
    current_revision_id: document.current_revision_id,
    created_at: document.created_at,
    updated_at: document.updated_at,
  };
}

function findDocument(id: string): DocumentDetail {
  const document = PUBLIC_DEMO_DOCUMENTS.find((candidate) => candidate.id === id);
  if (!document) throw notFound("document");
  return document;
}

function findAuditEvent(id: string): AuditEvent {
  const event = state.auditEvents.find((candidate) => candidate.id === id);
  if (!event) throw notFound("audit event");
  return event;
}

function isGroundedQuestion(question: string): boolean {
  const normalized = question.toLocaleLowerCase("en");
  return ["vendor", "offboard", "disable", "service desk", "one hour", "account"].some((term) =>
    normalized.includes(term),
  );
}

function answerQuestion(body: BodyInit | null | undefined) {
  const request = QuestionRequestSchema.safeParse(readJsonBody(body));
  if (!request.success) throw requestError("The evidence question does not match the LocalGuard contract.");
  const job = isGroundedQuestion(request.data.question)
    ? createGroundedQuestion(request.data.question, request.data.document_ids)
    : createInsufficientQuestion(request.data.question, request.data.document_ids);
  state.questionJobs[job.id] = job;
  return job;
}

function startWorkflow(body: BodyInit | null | undefined) {
  const request = WorkflowRunRequestSchema.safeParse(readJsonBody(body));
  if (!request.success) throw requestError("The action request does not match the LocalGuard contract.");

  state.workflow = {
    ...clone(PUBLIC_DEMO_FIXTURES.workflow),
    question: request.data.question,
    document_ids: request.data.document_ids?.length
      ? [...request.data.document_ids]
      : [PUBLIC_DEMO_IDS.vendorDocument],
  };
  return { run: state.workflow, dispatch_job_id: "demo-browser-job-workflow-001" };
}

function approveProposal(body: BodyInit | null | undefined) {
  const binding = ApprovalDecisionRequestSchema.safeParse(readJsonBody(body));
  if (!binding.success) throw requestError("The approval binding does not match the LocalGuard contract.");
  if (
    binding.data.version !== state.proposal.version ||
    binding.data.payload_hash !== state.proposal.payload_hash ||
    binding.data.evidence_snapshot_hash !== state.proposal.evidence_snapshot_hash
  ) {
    throw new PublicDemoApiError(
      "The proposal binding changed. Refresh the showcase before approving it.",
      409,
      "demo_binding_mismatch",
      PUBLIC_DEMO_CORRELATION_IDS.approval,
    );
  }

  if (!state.approved) {
    state.approved = true;
    state.proposal = {
      ...state.proposal,
      state: "approved",
      updated_at: PUBLIC_DEMO_TIMESTAMPS.approved,
    };
    state.workflow = {
      ...state.workflow,
      state: "completed",
      updated_at: PUBLIC_DEMO_TIMESTAMPS.approved,
    };
    state.tasks = [clone(PUBLIC_DEMO_CREATED_TASK), ...state.tasks];
    state.auditEvents = [clone(PUBLIC_DEMO_APPROVAL_AUDIT_EVENT), ...state.auditEvents];
  }

  return {
    decision: {
      ...PUBLIC_DEMO_DECISION,
      comment: binding.data.comment ?? PUBLIC_DEMO_DECISION.comment,
    },
    proposal: state.proposal,
    replacement: null,
    task: PUBLIC_DEMO_CREATED_TASK,
    dispatch_job_id: null,
  };
}

function overviewPayload() {
  return {
    ...PUBLIC_DEMO_FIXTURES.overview,
    pending_approvals: state.proposal.state === "pending" ? 1 : 0,
    recent_activity: state.auditEvents.slice(0, 5).map((event) => ({
      id: event.id,
      occurred_at: event.occurred_at,
      action: event.action,
      resource_type: event.resource_type,
      resource_id: event.resource_id,
      outcome: event.outcome,
      correlation_id: event.correlation_id,
    })),
  };
}

function citationPayload(documentId: string, revisionId: string, anchorKey: string, url: URL) {
  const document = findDocument(documentId);
  const revision = document.current_revision;
  const anchor = document.anchors.find((candidate) => candidate.stable_key === anchorKey || candidate.id === anchorKey);
  if (!revision || revision.id !== revisionId || !anchor) throw notFound("citation");

  const rawStart = url.searchParams.get("start_offset");
  const rawEnd = url.searchParams.get("end_offset");
  if (rawStart == null || rawEnd == null || !/^\d+$/.test(rawStart) || !/^\d+$/.test(rawEnd)) {
    throw requestError("A citation requires valid start and end offsets.");
  }
  const start = Number(rawStart);
  const end = Number(rawEnd);
  if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start < 0 || end <= start || end > anchor.text.length) {
    throw requestError("The citation range is outside the synthetic anchor.");
  }

  return {
    document_id: document.id,
    revision_id: revision.id,
    anchor_key: anchor.stable_key,
    anchor_label: anchor.label,
    kind: anchor.kind,
    anchor_start_offset: anchor.start_offset,
    anchor_end_offset: anchor.end_offset,
    requested_start_offset: start,
    requested_end_offset: end,
    text: anchor.text.slice(start, end),
  };
}

function listPayload(url: URL, kind: "documents" | "approvals" | "tasks" | "evaluations" | "audit") {
  const pagination = parsePagination(url, kind === "evaluations" ? 25 : 15);
  if (kind === "documents") {
    const items = PUBLIC_DEMO_DOCUMENTS.map(documentSummary);
    return { items: paginate(items, pagination), total: items.length, ...pagination };
  }
  if (kind === "approvals") {
    const items: Proposal[] = [state.proposal];
    return { items: paginate(items, pagination), total: items.length, ...pagination };
  }
  if (kind === "tasks") {
    return {
      items: paginate(state.tasks, pagination),
      total: state.tasks.length,
      ...pagination,
    };
  }
  if (kind === "evaluations") {
    return {
      items: paginate(PUBLIC_DEMO_EVALUATION_LIST.items, pagination),
      total: PUBLIC_DEMO_EVALUATION_LIST.items.length,
      ...pagination,
    };
  }
  return {
    items: paginate(state.auditEvents, pagination),
    total: state.auditEvents.length,
    ...pagination,
  };
}

function readPayload(segments: string[], url: URL): unknown {
  const route = segments.join("/");
  if (route === "auth/me") return PUBLIC_DEMO_FIXTURES.reviewer;
  if (route === "auth/csrf") return { csrf_token: "synthetic-demo-csrf-token-0001" };
  if (route === "health/live" || route === "health/ready") return PUBLIC_DEMO_FIXTURES.health;
  if (route === "overview") return overviewPayload();
  if (route === "documents") return listPayload(url, "documents");
  if (segments[0] === "documents" && segments.length === 2) return findDocument(segments[1]);
  if (
    segments[0] === "documents" &&
    segments[2] === "revisions" &&
    segments[4] === "anchors" &&
    segments.length === 6
  ) {
    return citationPayload(segments[1], segments[3], segments[5], url);
  }
  if (segments[0] === "questions" && segments.length === 2) {
    const job = state.questionJobs[segments[1]];
    if (!job) throw notFound("question job");
    return job;
  }
  if (segments[0] === "workflow-runs" && segments.length === 2) {
    if (segments[1] !== PUBLIC_DEMO_IDS.workflow) throw notFound("workflow run");
    return state.workflow;
  }
  if (route === "findings") {
    const requestedWorkflow = url.searchParams.get("workflow_run_id");
    const items = !requestedWorkflow || requestedWorkflow === PUBLIC_DEMO_IDS.workflow
      ? [PUBLIC_DEMO_FINDING]
      : [];
    const pagination = parsePagination(url, 100);
    return { items: paginate(items, pagination), total: items.length, ...pagination };
  }
  if (route === "approvals") return listPayload(url, "approvals");
  if (segments[0] === "approvals" && segments.length === 2) {
    if (segments[1] !== PUBLIC_DEMO_IDS.proposal) throw notFound("approval proposal");
    return state.proposal;
  }
  if (route === "tasks") return listPayload(url, "tasks");
  if (segments[0] === "tasks" && segments.length === 2) {
    const task = state.tasks.find((candidate) => candidate.id === segments[1]);
    if (!task) throw notFound("workflow task");
    return task;
  }
  if (route === "evaluations") return listPayload(url, "evaluations");
  if (segments[0] === "evaluations" && segments.length === 2) {
    if (segments[1] !== "latest" && segments[1] !== PUBLIC_DEMO_IDS.evaluationRun) {
      throw notFound("evaluation run");
    }
    return PUBLIC_DEMO_EVALUATION_DETAIL;
  }
  if (route === "audit-events") return listPayload(url, "audit");
  if (segments[0] === "audit-events" && segments.length === 2) return findAuditEvent(segments[1]);
  throw notFound("route");
}

function writePayload(
  method: string,
  segments: string[],
  body: BodyInit | null | undefined,
): unknown {
  const route = segments.join("/");
  if (method === "POST" && route === "questions") return answerQuestion(body);
  if (method === "POST" && route === "workflow-runs") return startWorkflow(body);
  if (
    method === "POST" &&
    segments[0] === "approvals" &&
    segments[1] === PUBLIC_DEMO_IDS.proposal &&
    segments[2] === "approve" &&
    segments.length === 3
  ) {
    return approveProposal(body);
  }
  throw readOnly();
}

export async function publicDemoApiRequest<T>(
  path: string,
  schema: z.ZodType<T>,
  options: PublicDemoRequestOptions = {},
): Promise<T> {
  const { url, segments } = parsePath(path);
  const method = (options.method ?? "GET").toUpperCase();
  const payload = method === "GET" || method === "HEAD"
    ? readPayload(segments, url)
    : writePayload(method, segments, options.body);
  return parseOutput(payload, schema);
}

export function resetPublicDemoState(): void {
  state = createInitialPublicDemoState();
}
