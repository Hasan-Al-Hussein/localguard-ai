import { readFileSync } from "node:fs";
import type {
  AuditEvent,
  EvaluationHistoryEntry,
  EvaluationRun,
  Proposal,
  QuestionJob,
  WorkflowTask,
} from "@localguard/contracts";
import { describe, expect, it } from "vitest";
import {
  findPortfolioAuditChain,
  isPortfolioCaptureEnabled,
  parsePortfolioArtifacts,
  PORTFOLIO_ACTION,
  PORTFOLIO_ACTION_PROPOSAL_MODE,
  PORTFOLIO_AUDIT_CHAIN,
  PORTFOLIO_BROWSER_USE,
  PORTFOLIO_CASE_COUNT,
  PORTFOLIO_CANONICAL_MANIFEST_SHA256,
  PORTFOLIO_CASES_SHA256,
  PORTFOLIO_CHAT_MODEL,
  PORTFOLIO_CHAT_MODEL_DIGEST,
  PORTFOLIO_CORPUS_BUNDLE_SHA256,
  PORTFOLIO_DATASET_VERSION,
  PORTFOLIO_EMBEDDING_MODEL,
  PORTFOLIO_EMBEDDING_MODEL_DIGEST,
  PORTFOLIO_EVIDENCE_MARKER,
  PORTFOLIO_EVALUATION_SCHEMA_VERSION,
  PORTFOLIO_EXPECTED_DUE_AT,
  PORTFOLIO_GENERATED_FIXTURE_MANIFEST_SHA256,
  PORTFOLIO_OLLAMA_RUNTIME_VERSION,
  PORTFOLIO_QUESTION,
  PORTFOLIO_SCREENSHOT_OPTIONS,
  PORTFOLIO_SCREENSHOTS,
  PORTFOLIO_STRUCTURED_EXTRACTION_MODE,
  readPortfolioCredentials,
  validateApprovedProposal,
  validateExecutedProposal,
  validateExecutedTask,
  validateFreshQuestion,
  validatePendingProposal,
  validatePortfolioEvaluation,
  validatePortfolioEvaluationHistoryEntry,
} from "../e2e/portfolio-support";

const documentId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const revisionId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const workflowId = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const proposalId = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";
const decisionId = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";
const taskId = "ffffffff-ffff-4fff-8fff-ffffffffffff";
const actorId = "11111111-1111-4111-8111-111111111111";
const chunkId = "chunk-lg-pol-001-l010";
const timestamp = "2026-08-23T08:00:00Z";
const hashA = "a".repeat(64);
const hashB = "b".repeat(64);

function demoArtifact() {
  return {
    schema_version: "1.0",
    status: "verified",
    proof_scope: "in_process_domain",
    provider: "ollama",
    chat_model: PORTFOLIO_CHAT_MODEL,
    embedding_model: PORTFOLIO_EMBEDDING_MODEL,
    started_at: timestamp,
    completed_at: "2026-08-23T08:05:00Z",
    document: { source_id: "LG-POL-001", document_id: documentId, revision_id: revisionId },
    question: {
      prompt: PORTFOLIO_QUESTION,
      answer: "The Service Desk must disable the account within one hour.",
      model_name: PORTFOLIO_CHAT_MODEL,
      citations: [{
        citation_id: "22222222-2222-4222-8222-222222222222",
        document_id: documentId,
        revision_id: revisionId,
        anchor_key: "page:1",
        anchor_label: "Page 1",
        start_offset: 10,
        end_offset: 110,
        quote: `[${PORTFOLIO_EVIDENCE_MARKER}] The Service Desk must disable the vendor account within one hour.`,
      }],
    },
    approval_workflow: {
      prompt: PORTFOLIO_ACTION,
      answer: "A high-priority Service Desk task is proposed for review.",
      cited_chunk_ids: [chunkId],
      cited_marker_ids: [PORTFOLIO_EVIDENCE_MARKER],
      workflow_run_id: workflowId,
      proposal_id: proposalId,
      task_id: taskId,
      task_title: "Disable vendor access",
      task_assignee: "Service Desk",
      task_priority: "high",
      task_due_at: PORTFOLIO_EXPECTED_DUE_AT,
      tasks_before_approval: 0,
      tasks_after_approval: 1,
      tasks_after_replay: 1,
    },
  };
}

function evaluationArtifact(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: PORTFOLIO_EVALUATION_SCHEMA_VERSION,
    run_id: "20260823T080500000000Z-ollama-aaaaaaaaaaaa",
    dataset_version: PORTFOLIO_DATASET_VERSION,
    dataset_sha256: PORTFOLIO_CASES_SHA256,
    cases_sha256: PORTFOLIO_CASES_SHA256,
    canonical_manifest_sha256: PORTFOLIO_CANONICAL_MANIFEST_SHA256,
    generated_fixture_manifest_sha256: PORTFOLIO_GENERATED_FIXTURE_MANIFEST_SHA256,
    corpus_bundle_sha256: PORTFOLIO_CORPUS_BUNDLE_SHA256,
    raw_result_sha256: hashB,
    requested_provider: "ollama",
    runtime_provider: "ollama",
    provider_raw_response_capture_enabled: true,
    runtime_model_identity: {
      provider: "ollama",
      chat_model_name: PORTFOLIO_CHAT_MODEL,
      chat_model_digest: PORTFOLIO_CHAT_MODEL_DIGEST,
      embedding_model_name: PORTFOLIO_EMBEDDING_MODEL,
      embedding_model_digest: PORTFOLIO_EMBEDDING_MODEL_DIGEST,
      runtime_version: PORTFOLIO_OLLAMA_RUNTIME_VERSION,
    },
    structured_extraction_mode: PORTFOLIO_STRUCTURED_EXTRACTION_MODE,
    action_proposal_mode: PORTFOLIO_ACTION_PROPOSAL_MODE,
    aggregate: {
      case_count: PORTFOLIO_CASE_COUNT,
      completed_case_count: PORTFOLIO_CASE_COUNT,
      failed_case_count: 0,
      pre_approval_execution_count: 0,
      pre_approval_task_count: 0,
    },
    gates: {
      safety_passed: true,
      quality_passed: false,
      run_passed: false,
      failed_gates: ["quality"],
    },
    claim_provenance: {
      total_claim_count: 2,
      model_claim_count: 1,
      deterministic_test_provider_claim_count: 0,
      deterministic_normalizer_claim_count: 1,
      claim_bearing_case_count: 2,
      deterministic_normalizer_case_ids: ["LG-EVAL-ACT-001"],
      deterministic_normalizer_case_rate: 0.5,
    },
    finding_provenance: {
      total_finding_count: 1,
      model_finding_count: 0,
      deterministic_test_provider_finding_count: 0,
      deterministic_normalizer_finding_count: 1,
      finding_bearing_case_count: 1,
      deterministic_normalizer_case_ids: ["LG-EVAL-GRD-001"],
      deterministic_normalizer_case_rate: 1,
    },
    ...overrides,
  };
}

function evaluationHistoryEntry(
  integrityStatus: "summary_verified" | "run_verified" = "summary_verified",
): EvaluationHistoryEntry {
  const artifact = evaluationArtifact();
  return {
    schema_version: artifact.schema_version,
    run_id: artifact.run_id,
    dataset_version: artifact.dataset_version,
    dataset_sha256: artifact.dataset_sha256,
    requested_provider: "ollama",
    runtime_provider: "ollama",
    completed_case_count: artifact.aggregate.completed_case_count,
    case_count: artifact.aggregate.case_count,
    safety_passed: artifact.gates.safety_passed,
    quality_passed: artifact.gates.quality_passed,
    run_passed: artifact.gates.run_passed,
    raw_result_sha256: artifact.raw_result_sha256,
    comparability_status: "current",
    comparability_note: "Schema 1.2.0 uses the current evaluation contract.",
    integrity_status: integrityStatus,
    integrity_note: integrityStatus === "summary_verified"
      ? "The summary schema and directory identity were verified."
      : "The summary, run identity, and exact run-byte digest were verified.",
  };
}

function runtimeLockArtifact() {
  return {
    containers: {
      ollama: { tag: `ollama/ollama:${PORTFOLIO_OLLAMA_RUNTIME_VERSION}` },
    },
    models: {
      generation_selected: {
        tag: PORTFOLIO_CHAT_MODEL,
        manifest_sha256: PORTFOLIO_CHAT_MODEL_DIGEST,
      },
      embedding: {
        tag: PORTFOLIO_EMBEDDING_MODEL,
        manifest_sha256: PORTFOLIO_EMBEDDING_MODEL_DIGEST,
      },
    },
  };
}

function portfolioArtifacts() {
  return parsePortfolioArtifacts(
    demoArtifact(),
    evaluationArtifact(),
    runtimeLockArtifact(),
  );
}

function liveEvaluationRun(): EvaluationRun {
  const artifact = evaluationArtifact();
  const results = Array.from({ length: PORTFOLIO_CASE_COUNT }, (_, index) => {
    const caseId = index === 0
      ? "LG-EVAL-GRD-001"
      : index === 1
        ? "LG-EVAL-ACT-001"
        : `LG-EVAL-GRD-${String(index).padStart(3, "0")}`;
    const claimProvenance = index === 0
      ? [{ claim_index: 0, predicate: "offboarding deadline", origin: "model" }]
      : index === 1
        ? [{
            claim_index: 0,
            predicate: "offboarding action",
            origin: "deterministic_evidence_normalizer",
            normalizer_version: "action-obligation-v1",
            source_marker_sha256: hashA,
            fallback_reason: "duration_tuple_mismatch",
          }]
        : [];
    const extractions = index === 0
      ? [{ origin: "deterministic_evidence_normalizer" }]
      : [];
    return {
      case_id: caseId,
      failure: null,
      output: { claim_provenance: claimProvenance, extractions },
    };
  });
  return {
    schema_version: artifact.schema_version,
    run_id: artifact.run_id,
    requested_provider: artifact.requested_provider,
    runtime_provider: artifact.runtime_provider,
    provider_raw_response_capture_enabled: artifact.provider_raw_response_capture_enabled,
    runtime_model_identity: artifact.runtime_model_identity,
    structured_extraction_mode: artifact.structured_extraction_mode,
    action_proposal_mode: artifact.action_proposal_mode,
    dataset_version: artifact.dataset_version,
    dataset_sha256: artifact.dataset_sha256,
    cases_sha256: artifact.cases_sha256,
    canonical_manifest_sha256: artifact.canonical_manifest_sha256,
    generated_fixture_manifest_sha256: artifact.generated_fixture_manifest_sha256,
    corpus_bundle_sha256: artifact.corpus_bundle_sha256,
    aggregate: artifact.aggregate,
    claim_provenance: artifact.claim_provenance,
    finding_provenance: artifact.finding_provenance,
    results,
    gates: artifact.gates,
  } as unknown as EvaluationRun;
}

function questionJob(): QuestionJob {
  return {
    id: "33333333-3333-4333-8333-333333333333",
    question: PORTFOLIO_QUESTION,
    document_ids: [documentId],
    state: "succeeded",
    error_code: null,
    error_detail: null,
    created_at: timestamp,
    updated_at: timestamp,
    answer: {
      id: "44444444-4444-4444-8444-444444444444",
      text: "The cited deadline is one hour after the notice.",
      insufficient_evidence: false,
      model_name: PORTFOLIO_CHAT_MODEL,
      prompt_version: "qa-v1",
      retrieval_ms: 10,
      generation_ms: 20,
      created_at: timestamp,
      citations: [{
        id: "55555555-5555-4555-8555-555555555555",
        ordinal: 1,
        quote: `[${PORTFOLIO_EVIDENCE_MARKER}] Disable the account within one hour.`,
        document_id: documentId,
        revision_id: revisionId,
        anchor_key: "page:1",
        anchor_label: "Page 1",
        start_offset: 10,
        end_offset: 90,
      }],
    },
  };
}

function pendingProposal(): Proposal {
  return {
    id: proposalId,
    workflow_run_id: workflowId,
    created_by_id: actorId,
    previous_proposal_id: null,
    version: 1,
    kind: "workflow_task",
    state: "pending",
    title: "Disable vendor access",
    description: "Disable the vendor account within one hour after the notice.",
    assignee: "Service Desk",
    priority: "high",
    due_at: "2026-09-01T10:00:00+00:00",
    reasoning_summary: "The cited policy requires action within one hour.",
    cited_chunk_ids: [chunkId],
    evidence: [{
      chunk_id: chunkId,
      available: true,
      document_id: documentId,
      revision_id: revisionId,
      document_title: "Vendor access policy",
      anchor_key: "page:1",
      anchor_label: "Page 1",
      start_offset: 10,
      end_offset: 110,
      excerpt: `[${PORTFOLIO_EVIDENCE_MARKER}] The Service Desk must disable the vendor account within one hour.`,
    }],
    payload_hash: hashA,
    evidence_snapshot_hash: hashB,
    expires_at: "2026-08-24T08:00:00Z",
    created_at: timestamp,
    updated_at: timestamp,
  };
}

function workflowTask(): WorkflowTask {
  const proposal = pendingProposal();
  return {
    id: taskId,
    proposal_id: proposal.id,
    approval_decision_id: decisionId,
    created_by_id: actorId,
    title: proposal.title,
    description: proposal.description,
    assignee: proposal.assignee,
    priority: proposal.priority,
    due_at: proposal.due_at,
    state: "open",
    created_at: timestamp,
    updated_at: timestamp,
  };
}

function auditEvent(
  action: string,
  outcome: string,
  resourceId: string,
  minute: number,
  causationId: string | null = null,
): AuditEvent {
  return {
    id: `00000000-0000-4000-8000-0000000000${String(minute).padStart(2, "0")}`,
    occurred_at: `2026-08-23T08:${String(minute).padStart(2, "0")}:00Z`,
    actor_id: actorId,
    action,
    resource_type: "portfolio-proof",
    resource_id: resourceId,
    outcome,
    correlation_id: `correlation-${minute}`,
    causation_id: causationId,
    thread_id: workflowId,
    detail: {},
  };
}

describe("portfolio capture guardrails", () => {
  it("requires the explicit capture gate and named actors", () => {
    expect(isPortfolioCaptureEnabled({ LOCALGUARD_PORTFOLIO_CAPTURE: "1" })).toBe(true);
    expect(isPortfolioCaptureEnabled({ LOCALGUARD_PORTFOLIO_CAPTURE: "true" })).toBe(false);
    expect(readPortfolioCredentials({
      LOCALGUARD_PORTFOLIO_VIEWER_USERNAME: "demo-viewer",
      LOCALGUARD_PORTFOLIO_VIEWER_PASSWORD: "viewer-secret",
      LOCALGUARD_PORTFOLIO_REVIEWER_USERNAME: "demo-reviewer",
      LOCALGUARD_PORTFOLIO_REVIEWER_PASSWORD: "reviewer-secret",
    }).reviewer.username).toBe("demo-reviewer");
    expect(() => readPortfolioCredentials({})).toThrow(/VIEWER_USERNAME/);
  });

  it("accepts only complete locked-model Ollama artifacts with exact demo evidence", () => {
    const parsed = portfolioArtifacts();
    expect(parsed.demo.chat_model).toBe(PORTFOLIO_CHAT_MODEL);
    expect(() => parsePortfolioArtifacts(
      { ...demoArtifact(), chat_model: "other-model" },
      evaluationArtifact(),
      runtimeLockArtifact(),
    )).toThrow();
    expect(() => parsePortfolioArtifacts(
      demoArtifact(),
      evaluationArtifact({
        aggregate: {
          ...evaluationArtifact().aggregate,
          completed_case_count: 24,
          failed_case_count: 1,
        },
      }),
      runtimeLockArtifact(),
    )).toThrow();
    expect(() => parsePortfolioArtifacts(
      demoArtifact(),
      evaluationArtifact({ corpus_bundle_sha256: hashA }),
      runtimeLockArtifact(),
    )).toThrow();
    expect(() => parsePortfolioArtifacts(
      demoArtifact(),
      evaluationArtifact({ structured_extraction_mode: "unconstrained" }),
      runtimeLockArtifact(),
    )).toThrow();
    expect(() => parsePortfolioArtifacts(
      demoArtifact(),
      evaluationArtifact(),
      {
        ...runtimeLockArtifact(),
        models: {
          ...runtimeLockArtifact().models,
          generation_selected: {
            ...runtimeLockArtifact().models.generation_selected,
            manifest_sha256: hashA,
          },
        },
      },
    )).toThrow();
    expect(() => parsePortfolioArtifacts(
      demoArtifact(),
      evaluationArtifact({
        claim_provenance: {
          ...evaluationArtifact().claim_provenance,
          deterministic_normalizer_case_rate: 0,
        },
      }),
      runtimeLockArtifact(),
    )).toThrow(/Normalizer case rate/);
  });

  it("binds a fresh answer to its own exact immutable one-hour citation", () => {
    const { demo } = portfolioArtifacts();
    expect(validateFreshQuestion(questionJob(), demo).revision_id).toBe(revisionId);
    const invalid = questionJob();
    invalid.answer!.citations[0]!.quote = "A different passage without the required marker.";
    expect(() => validateFreshQuestion(invalid, demo)).toThrow(/live immutable L010 citation/);
  });

  it("requires the verified proposal semantics and preserves them through approval and execution", () => {
    const { demo } = portfolioArtifacts();
    const proposal = pendingProposal();
    expect(() => validatePendingProposal(proposal, workflowId, demo)).not.toThrow();
    expect(() => validateApprovedProposal({ ...proposal, state: "approved" }, proposal)).not.toThrow();
    expect(() => validateExecutedTask(workflowTask(), proposal)).not.toThrow();
    expect(() => validateExecutedProposal({ ...proposal, state: "executed" }, proposal)).not.toThrow();
    expect(() => validatePendingProposal({ ...proposal, priority: "medium" }, workflowId, demo))
      .toThrow(/ACT-001 task semantics/);
  });

  it("selects the exact ordered and decision-bound workflow audit chain", () => {
    const events = [
      auditEvent("workflow.request", "queued", workflowId, 1),
      auditEvent("workflow.analysis", "grounded", workflowId, 2),
      auditEvent("proposal.create", "pending", proposalId, 3),
      auditEvent("proposal.approve", "approved", proposalId, 4, decisionId),
      auditEvent("workflow.resume", "started", workflowId, 5, decisionId),
      auditEvent("workflow_task.create", "succeeded", taskId, 6, decisionId),
      auditEvent("workflow.resume", "applied", workflowId, 7, decisionId),
    ].reverse();
    const identity = { workflowId, proposalId, decisionId, taskId };
    expect(findPortfolioAuditChain(events, identity)?.map((event) => event.action))
      .toEqual(PORTFOLIO_AUDIT_CHAIN.map((event) => event.action));
    expect(findPortfolioAuditChain(events.slice(1), identity)).toBeNull();
  });

  it("requires a live 25/25 Ollama evaluation with no execution failures", () => {
    const artifacts = portfolioArtifacts();
    const run = liveEvaluationRun();
    expect(() => validatePortfolioEvaluation(run, artifacts.evaluation, artifacts.demo)).not.toThrow();
    expect(() => validatePortfolioEvaluationHistoryEntry(
      evaluationHistoryEntry(),
      artifacts.evaluation,
      "summary_verified",
    )).not.toThrow();
    expect(() => validatePortfolioEvaluation({
      ...run,
      results: run.results.map((result, index) => (
        index === 0 ? { ...result, failure: { code: "failed", message: "failed" } } : result
      )),
    }, artifacts.evaluation, artifacts.demo)).toThrow(/25\/25 safety-passing/);
    expect(() => validatePortfolioEvaluation({
      ...run,
      runtime_model_identity: {
        ...run.runtime_model_identity,
        chat_model_digest: hashA,
      },
    }, artifacts.evaluation, artifacts.demo)).toThrow(/runtime model lock/);
    expect(() => validatePortfolioEvaluation({
      ...run,
      results: run.results.map((result, index) => (
        index === 1 && result.output
          ? { ...result, output: { ...result.output, claim_provenance: [] } }
          : result
      )),
    }, artifacts.evaluation, artifacts.demo)).toThrow(/case outputs/);
  });

  it("hard-disables incidental recordings and keeps the capture unintercepted", () => {
    expect(PORTFOLIO_BROWSER_USE).toMatchObject({ trace: "off", video: "off", screenshot: "off" });
    expect(PORTFOLIO_SCREENSHOT_OPTIONS).toEqual({
      animations: "disabled",
      caret: "hide",
      fullPage: true,
      type: "png",
    });
    expect(new Set(Object.values(PORTFOLIO_SCREENSHOTS)).size)
      .toBe(Object.keys(PORTFOLIO_SCREENSHOTS).length);
    const source = readFileSync(
      new URL("../e2e/portfolio-capture.spec.ts", import.meta.url),
      "utf8",
    );
    expect(source).not.toMatch(/\b(?:page|context)\.route\s*\(/);
    expect(source).not.toMatch(/\bdotenv\b|readFileSync?\([^)]*["'][^"']*\.env["']/);
  });
});
