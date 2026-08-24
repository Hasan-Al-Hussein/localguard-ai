import {
  DecisionAcceptedSchema,
  ClaimProvenanceObservationSchema,
  EvaluationHistoryDetailSchema,
  EvaluationHistoryEntrySchema,
  EvaluationHistoryListSchema,
  EvaluationRunSchema,
  CaseRunResultSchema,
  ClaimProvenanceSummarySchema,
  FindingProvenanceSummarySchema,
  FindingSchema,
  ProviderCallDiagnosticSchema,
  ProposalSchema,
  RevisionSectionSchema,
  WorkflowRunRequestSchema,
  WorkflowRunSchema,
  WorkflowStartAcceptedSchema,
  RuntimeModelIdentitySchema,
} from "@localguard/contracts";
import { describe, expect, it } from "vitest";
import { z, type ZodType } from "zod";
import openapi from "../../../packages/contracts/openapi.json";

type ObjectDefinition = {
  type?: string;
  properties?: Record<string, unknown>;
  required?: string[];
  additionalProperties?: boolean;
};

type ApiDocument = {
  components: { schemas: Record<string, ObjectDefinition> };
  paths: Record<string, { post?: { parameters?: Array<{ in?: string; name?: string; required?: boolean; schema?: { minLength?: number; maxLength?: number } }> } }>;
};

const api = openapi as unknown as ApiDocument;

const criticalSchemas: Array<[string, ZodType]> = [
  ["WorkflowRunRequest", WorkflowRunRequestSchema],
  ["WorkflowRunPublic", WorkflowRunSchema],
  ["WorkflowStartAccepted", WorkflowStartAcceptedSchema],
  ["ProposalPublic", ProposalSchema],
  ["DecisionAccepted", DecisionAcceptedSchema],
  ["RevisionSectionPublic", RevisionSectionSchema],
  ["RuntimeModelIdentity", RuntimeModelIdentitySchema],
  ["ClaimProvenanceSummary", ClaimProvenanceSummarySchema],
  ["FindingProvenanceSummary", FindingProvenanceSummarySchema],
  ["ProviderCallDiagnostic", ProviderCallDiagnosticSchema],
  ["FindingPublic", FindingSchema],
  ["EvaluationHistoryEntry", EvaluationHistoryEntrySchema],
  ["EvaluationHistoryList", EvaluationHistoryListSchema],
  ["EvaluationHistoryDetail", EvaluationHistoryDetailSchema],
  ["EvaluationRun", EvaluationRunSchema],
];

describe("critical runtime Zod/OpenAPI parity", () => {
  it.each(criticalSchemas)("keeps %s object keys and required fields aligned", (name, runtimeSchema) => {
    const serverSchema = api.components.schemas[name];
    const runtimeJson = z.toJSONSchema(runtimeSchema) as ObjectDefinition;

    expect(serverSchema, `${name} must exist in the checked OpenAPI snapshot`).toBeDefined();
    expect(Object.keys(runtimeJson.properties ?? {}).sort()).toEqual(Object.keys(serverSchema?.properties ?? {}).sort());
    expect([...(runtimeJson.required ?? [])].sort()).toEqual([...(serverSchema?.required ?? [])].sort());
    // Runtime responses deliberately reject unknown fields even where FastAPI's
    // generated component omits an explicit additionalProperties constraint.
    expect(runtimeJson.additionalProperties).toBe(false);
  });

  it("requires a bounded Idempotency-Key on workflow creation", () => {
    const parameters = api.paths["/workflow-runs"]?.post?.parameters ?? [];
    const header = parameters.find((parameter) => parameter.in === "header" && parameter.name === "Idempotency-Key");

    expect(header).toMatchObject({ required: true, schema: { minLength: 8, maxLength: 128 } });
  });

  it("enforces evaluator identity and normalizer provenance invariants at runtime", () => {
    const digest = "a".repeat(64);
    expect(() => RuntimeModelIdentitySchema.parse({
      provider: "ollama",
      chat_model_name: "chat",
      chat_model_digest: digest,
      embedding_model_name: "embed",
      embedding_model_digest: digest,
      runtime_version: "1.0.0",
    })).not.toThrow();
    expect(() => RuntimeModelIdentitySchema.parse({
      provider: "ollama",
      chat_model_name: "chat",
      embedding_model_name: "embed",
      runtime_version: "1.0.0",
    })).toThrow(/requires resolved chat and embedding model digests/);
    expect(() => ClaimProvenanceObservationSchema.parse({
      claim_index: 0,
      predicate: "deadline",
      origin: "deterministic_evidence_normalizer",
    })).toThrow(/complete source binding/);
    expect(() => ClaimProvenanceObservationSchema.parse({
      claim_index: 0,
      predicate: "deadline",
      origin: "model",
      normalizer_version: "action-obligation-v1",
      source_marker_sha256: digest,
      fallback_reason: "duration_tuple_mismatch",
    })).toThrow(/cannot assert normalizer metadata/);
    expect(() => ClaimProvenanceObservationSchema.parse({
      claim_index: 0,
      predicate: "notification_deadline",
      origin: "deterministic_evidence_normalizer",
      normalizer_version: "qa-fact-binding-v1",
      source_marker_sha256: digest,
      fallback_reason: "evidence_binding_confirmed",
    })).not.toThrow();
    expect(() => ClaimProvenanceObservationSchema.parse({
      claim_index: 0,
      predicate: "notification_deadline",
      origin: "deterministic_evidence_normalizer",
      normalizer_version: "action-obligation-binding-v2",
      source_marker_sha256: digest,
      fallback_reason: "evidence_binding_confirmed",
    })).toThrow(/reserved for QA facts/);
  });

  it("attests the four-call provider boundary without admitting a fifth network response", () => {
    const measured = [1, 2, 3, 4].map((callIndex) => ({
      call_index: callIndex,
      phase: callIndex % 2 === 1 ? "workflow_initial" : "workflow_repair",
      http_status: 200,
      duration_ms: callIndex,
      response_sha256: String(callIndex).repeat(64),
      validation_stage: "semantic_grounding",
      validation_hint: "predicate_not_grounded",
      final_reason_code: null,
      raw_excerpt: null,
    }));
    const denial = {
      call_index: 5,
      phase: "workflow_initial",
      http_status: null,
      duration_ms: 0,
      response_sha256: null,
      validation_stage: "call_bound",
      validation_hint: null,
      final_reason_code: "evaluation_call_bound_exceeded",
      raw_excerpt: null,
    };
    const result = {
      case_id: "LG-EVAL-ACT-001",
      category: "action",
      task_type: "action_proposal",
      output: null,
      metrics: null,
      failure: {
        code: "provider_call_bound_exceeded",
        message: "The provider exceeded the measured call budget.",
      },
      missing_capabilities: [],
      provider_diagnostics: [...measured, denial],
      wall_clock_ms: 10,
    };

    expect(() => CaseRunResultSchema.parse(result)).not.toThrow();
    expect(() => ProviderCallDiagnosticSchema.parse({
      ...denial,
      http_status: 200,
      duration_ms: 1,
      response_sha256: "a".repeat(64),
    })).toThrow(/cannot claim an executed provider response/);
    expect(() => CaseRunResultSchema.parse({
      ...result,
      provider_diagnostics: [measured[0], { ...measured[1], phase: "qa_repair" }, ...measured.slice(2), denial],
    })).toThrow(/cannot mix request families/);
    expect(() => CaseRunResultSchema.parse({
      ...result,
      provider_diagnostics: [...measured, { ...denial, phase: "workflow_repair" }],
    })).toThrow(/must start a new graph attempt/);
  });
});
