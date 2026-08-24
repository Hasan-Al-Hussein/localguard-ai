import { z } from "zod";
import type { components } from "./openapi.generated";
import { TimestampSchema, UuidSchema } from "./common";

type ApiSchemas = components["schemas"];

const NullableMetricSchema = z.number().nullable().optional();
const Sha256Schema = z.string().regex(/^[0-9a-f]{64}$/);

export const EvaluationComparabilityStatusSchema = z.enum([
  "current",
  "legacy_metadata_only",
  "unavailable",
]);
export const EvaluationIntegrityStatusSchema = z.enum([
  "summary_verified",
  "run_verified",
  "corrupt",
  "unsupported_schema",
  "hash_mismatch",
]);

export const EvaluationHistoryEntrySchema = z.strictObject({
  schema_version: z.string().max(32).nullable().optional(),
  run_id: z.string().min(1),
  dataset_version: z.string().max(80).nullable().optional(),
  dataset_sha256: Sha256Schema.nullable().optional(),
  requested_provider: z.enum(["fake", "ollama"]).nullable().optional(),
  runtime_provider: z.enum(["deterministic", "ollama"]).nullable().optional(),
  completed_case_count: z.number().int().nonnegative().nullable().optional(),
  case_count: z.number().int().nonnegative().nullable().optional(),
  safety_passed: z.boolean().nullable().optional(),
  quality_passed: z.boolean().nullable().optional(),
  run_passed: z.boolean().nullable().optional(),
  raw_result_sha256: Sha256Schema.nullable().optional(),
  comparability_status: EvaluationComparabilityStatusSchema,
  comparability_note: z.string().min(1),
  integrity_status: EvaluationIntegrityStatusSchema,
  integrity_note: z.string().min(1),
}) satisfies z.ZodType<ApiSchemas["EvaluationHistoryEntry"]>;
export type EvaluationHistoryEntry = z.infer<typeof EvaluationHistoryEntrySchema>;

export const EvaluationHistoryListSchema = z.strictObject({
  items: z.array(EvaluationHistoryEntrySchema),
  total: z.number().int().nonnegative(),
  offset: z.number().int().nonnegative(),
  limit: z.number().int().positive().max(100),
}) satisfies z.ZodType<ApiSchemas["EvaluationHistoryList"]>;
export type EvaluationHistoryList = z.infer<typeof EvaluationHistoryListSchema>;

export const LegacyEvaluationRunMetadataSchema = z.strictObject({
  schema_version: z.enum(["1.0.0", "1.1.0"]),
  run_id: z.string().min(1),
  started_at: TimestampSchema,
  completed_at: TimestampSchema,
  wall_clock_ms: z.number().nonnegative(),
  warmup_completed: z.boolean(),
}) satisfies z.ZodType<ApiSchemas["LegacyEvaluationRunMetadata"]>;
export type LegacyEvaluationRunMetadata = z.infer<
  typeof LegacyEvaluationRunMetadataSchema
>;

const RatioMetricSchema = z.strictObject({
  numerator: z.number().int().nonnegative(),
  denominator: z.number().int().nonnegative(),
  value: NullableMetricSchema,
}) satisfies z.ZodType<ApiSchemas["RatioMetric"]>;

const ExtractionAggregateSchema = z.strictObject({
  true_positive: z.number().int().nonnegative(),
  false_positive: z.number().int().nonnegative(),
  false_negative: z.number().int().nonnegative(),
  both_empty_cases: z.number().int().nonnegative(),
  precision: NullableMetricSchema,
  recall: NullableMetricSchema,
  f1: NullableMetricSchema,
}) satisfies z.ZodType<ApiSchemas["ExtractionAggregate"]>;

const RetrievalAggregateSchema = z.strictObject({
  eligible_cases: z.number().int().nonnegative(),
  macro_recall_at_k: z.record(z.string(), z.number().nullable()),
  micro_recall_at_k: z.record(z.string(), z.number().nullable()),
  pooled_gold_spans: z.number().int().nonnegative(),
  pooled_hits_at_k: z.record(z.string(), z.number().int().nonnegative()),
}) satisfies z.ZodType<ApiSchemas["RetrievalAggregate"]>;

const LatencyStatsSchema = z.strictObject({
  sample_count: z.number().int().nonnegative(),
  minimum_ms: NullableMetricSchema,
  maximum_ms: NullableMetricSchema,
  mean_ms: NullableMetricSchema,
  p50_ms: NullableMetricSchema,
  p95_ms: NullableMetricSchema,
}) satisfies z.ZodType<ApiSchemas["LatencyStats"]>;

export const AggregateMetricsSchema = z.strictObject({
  case_count: z.number().int().nonnegative(),
  completed_case_count: z.number().int().nonnegative(),
  failed_case_count: z.number().int().nonnegative(),
  grounded_retrieval: RetrievalAggregateSchema,
  citation_precision: RatioMetricSchema,
  citation_eligible_case_count: z.number().int().nonnegative(),
  citation_precision_macro: NullableMetricSchema,
  extraction: ExtractionAggregateSchema,
  unsupported_claim_rate: RatioMetricSchema,
  grounding_score: NullableMetricSchema,
  missing_expected_claim_count: z.number().int().nonnegative(),
  zero_citation_answer_count: z.number().int().nonnegative(),
  tool_selection_accuracy: RatioMetricSchema,
  first_tool_confusion_matrix: z.record(z.string(), z.record(z.string(), z.number().int().nonnegative())),
  approval_gate_compliance: RatioMetricSchema,
  approval_transition_coverage: RatioMetricSchema,
  forbidden_outcome_compliance: RatioMetricSchema,
  forbidden_outcome_control_coverage: RatioMetricSchema,
  injection_policy_compliance: RatioMetricSchema,
  insufficient_abstention: RatioMetricSchema,
  proposal_exact_match: RatioMetricSchema,
  status_accuracy: RatioMetricSchema,
  schema_validity: RatioMetricSchema,
  latency_by_stage: z.record(z.string(), LatencyStatsSchema),
  pre_approval_execution_count: z.number().int().nonnegative(),
  pre_approval_task_count: z.number().int().nonnegative(),
}) satisfies z.ZodType<ApiSchemas["AggregateMetrics"]>;

export const GateStatusSchema = z.strictObject({
  safety_passed: z.boolean(),
  quality_passed: z.boolean().nullable(),
  run_passed: z.boolean(),
  failed_gates: z.array(z.string()),
}) satisfies z.ZodType<ApiSchemas["GateStatus"]>;

const CapabilitySchema = z.enum(["retrieval", "answer", "extraction", "tool_trace", "action_proposal", "approval_resume", "policy_observability", "stage_latency"]);
const CategorySchema = z.enum(["grounded", "insufficient", "injection", "action"]);
const ClaimOriginSchema = z.enum([
  "model",
  "deterministic_test_provider",
  "deterministic_evidence_normalizer",
]);
const ToolNameSchema = z.enum(["NONE", "search_documents", "get_document_section", "propose_workflow_task", "list_pending_approvals", "get_audit_event"]);
const ForbiddenOutcomeSchema = z.enum(["unsupported_claim_asserted", "invalid_citation_accepted", "document_instruction_followed", "role_escalated", "system_prompt_disclosed", "sensitive_configuration_disclosed", "external_network_request", "audit_suppressed", "forged_tool_call_executed", "proposal_created_without_user_action", "workflow_task_created_before_approval", "privileged_action_executed_without_approval", "proposal_payload_mutated_after_approval", "duplicate_task_created"]);

export const ClaimProvenanceObservationSchema = z.strictObject({
  claim_index: z.number().int().nonnegative(),
  predicate: z.string().min(1),
  origin: ClaimOriginSchema,
  normalizer_version: z.enum([
    "action-obligation-v1",
    "action-obligation-binding-v2",
    "qa-fact-binding-v1",
  ]).nullable().optional(),
  source_marker_sha256: Sha256Schema.nullable().optional(),
  fallback_reason: z.enum([
    "duration_tuple_mismatch",
    "duration_unit_agreement",
    "evidence_binding_confirmed",
    "evidence_binding_selected",
    "performing_actor_scope",
    "predicate_not_grounded",
    "normalized_value_not_grounded",
  ]).nullable().optional(),
}).superRefine((value, context) => {
  const normalizerMetadata = [
    value.normalizer_version,
    value.source_marker_sha256,
    value.fallback_reason,
  ];
  if (
    value.origin === "deterministic_evidence_normalizer"
    && normalizerMetadata.some((item) => item == null)
  ) {
    context.addIssue({
      code: "custom",
      message: "Normalizer claim provenance must include its complete source binding",
    });
  }
  if (
    value.origin !== "deterministic_evidence_normalizer"
    && normalizerMetadata.some((item) => item != null)
  ) {
    context.addIssue({
      code: "custom",
      message: "Provider claim provenance cannot assert normalizer metadata",
    });
  }
  if (
    value.normalizer_version === "qa-fact-binding-v1"
    && value.fallback_reason !== "evidence_binding_confirmed"
  ) {
    context.addIssue({
      code: "custom",
      message: "QA fact normalization requires confirmed-binding provenance",
    });
  }
  if (
    value.fallback_reason === "evidence_binding_confirmed"
    && value.normalizer_version !== "qa-fact-binding-v1"
  ) {
    context.addIssue({
      code: "custom",
      message: "Confirmed-binding claim provenance is reserved for QA facts",
    });
  }
}) satisfies z.ZodType<ApiSchemas["ClaimProvenanceObservation"]>;

export const ClaimProvenanceSummarySchema = z.strictObject({
  total_claim_count: z.number().int().nonnegative(),
  model_claim_count: z.number().int().nonnegative(),
  deterministic_test_provider_claim_count: z.number().int().nonnegative(),
  deterministic_normalizer_claim_count: z.number().int().nonnegative(),
  claim_bearing_case_count: z.number().int().nonnegative(),
  deterministic_normalizer_case_ids: z.array(z.string()),
  deterministic_normalizer_case_rate: z.number().min(0).max(1),
}) satisfies z.ZodType<ApiSchemas["ClaimProvenanceSummary"]>;

const FindingOriginSchema = z.enum([
  "model",
  "deterministic_test_provider",
  "deterministic_evidence_normalizer",
]);

export const FindingProvenanceSummarySchema = z.strictObject({
  total_finding_count: z.number().int().nonnegative(),
  model_finding_count: z.number().int().nonnegative(),
  deterministic_test_provider_finding_count: z.number().int().nonnegative(),
  deterministic_normalizer_finding_count: z.number().int().nonnegative(),
  finding_bearing_case_count: z.number().int().nonnegative(),
  deterministic_normalizer_case_ids: z.array(z.string()),
  deterministic_normalizer_case_rate: z.number().min(0).max(1),
}) satisfies z.ZodType<ApiSchemas["FindingProvenanceSummary"]>;

export const RuntimeModelIdentitySchema = z.strictObject({
  provider: z.enum(["deterministic", "ollama"]),
  chat_model_name: z.string().min(1),
  chat_model_digest: Sha256Schema.nullable().optional(),
  embedding_model_name: z.string().min(1),
  embedding_model_digest: Sha256Schema.nullable().optional(),
  runtime_version: z.string().min(1),
}).superRefine((value, context) => {
  const hasChatDigest = value.chat_model_digest != null;
  const hasEmbeddingDigest = value.embedding_model_digest != null;
  if (value.provider === "ollama" && (!hasChatDigest || !hasEmbeddingDigest)) {
    context.addIssue({
      code: "custom",
      message: "Ollama identity requires resolved chat and embedding model digests",
    });
  }
  if (value.provider === "deterministic" && (hasChatDigest || hasEmbeddingDigest)) {
    context.addIssue({
      code: "custom",
      message: "Deterministic identity cannot claim Ollama model digests",
    });
  }
}) satisfies z.ZodType<ApiSchemas["RuntimeModelIdentity"]>;

const ApprovalCaseMetricSchema = z.strictObject({
  compliance: NullableMetricSchema,
  compliant_transitions: z.number().int().nonnegative(),
  observed_transitions: z.number().int().nonnegative(),
  tested_transitions: z.number().int().nonnegative(),
  pre_approval_execution_count: z.number().int().nonnegative(),
  pre_approval_task_count: z.number().int().nonnegative(),
});
const ExtractionCaseMetricSchema = z.strictObject({
  true_positive: z.number().int().nonnegative(),
  false_positive: z.number().int().nonnegative(),
  false_negative: z.number().int().nonnegative(),
  both_empty: z.boolean(),
  precision: NullableMetricSchema,
  recall: NullableMetricSchema,
  f1: NullableMetricSchema,
});
const PolicyCaseMetricSchema = z.strictObject({
  tested_controls: z.number().int().nonnegative(),
  passed_controls: z.number().int().nonnegative(),
  compliance: z.number(),
  triggered_forbidden_outcomes: z.array(ForbiddenOutcomeSchema),
});
const RetrievalCaseMetricSchema = z.strictObject({
  eligible: z.boolean(),
  gold_span_count: z.number().int().nonnegative(),
  hits_at_k: z.record(z.string(), z.number().int().nonnegative()),
  recall_at_k: z.record(z.string(), z.number()),
});
const UnsupportedClaimMetricSchema = z.strictObject({
  actual_claim_count: z.number().int().nonnegative(),
  unsupported_count: z.number().int().nonnegative(),
  missing_expected_claim_count: z.number().int().nonnegative(),
  rate: NullableMetricSchema,
  grounding_score: NullableMetricSchema,
  answer_failure: z.boolean(),
});
const CaseMetricsSchema = z.strictObject({
  actual_first_tool: ToolNameSchema,
  expected_first_tool: ToolNameSchema,
  approval: ApprovalCaseMetricSchema,
  citation_precision: RatioMetricSchema,
  extraction: ExtractionCaseMetricSchema,
  policy: PolicyCaseMetricSchema,
  proposal_exact: z.boolean().nullable(),
  retrieval: RetrievalCaseMetricSchema,
  stage_latency_ms: z.record(z.string(), z.number().nonnegative()),
  status_correct: z.boolean(),
  tool_sequence_exact: z.boolean(),
  unsupported_claims: UnsupportedClaimMetricSchema,
});

const ApprovalObservationSchema = z.strictObject({
  decision: z.enum(["approve", "edit", "reject", "expire", "replay"]),
  payload_integrity_valid: z.boolean(),
  proposal_status: z.enum(["pending", "approved", "rejected", "expired", "executed"]),
  step: z.number().int().nonnegative(),
  task_count: z.number().int().nonnegative(),
  task_ids: z.array(z.string()),
});
const CitationObservationSchema = z.strictObject({ marker_id: z.string(), source_id: z.string() });
const ClaimObservationSchema = z.strictObject({ predicate: z.string(), normalized_value: z.string(), span_ids: z.array(z.string()) });
const ExtractionObservationSchema = z.strictObject({
  extraction_type: z.enum(["obligation", "deadline", "risk", "required_action", "responsible_party"]),
  fields: z.record(z.string(), z.string()),
  span_ids: z.array(z.string()),
  origin: FindingOriginSchema,
  normalizer_version: z.literal("structured-obligation-binding-v2").nullable().optional(),
  source_marker_sha256: Sha256Schema.nullable().optional(),
  derivation_reason: z.literal("evidence_binding_confirmed").nullable().optional(),
}).superRefine((value, context) => {
  const normalizerMetadata = [
    value.normalizer_version,
    value.source_marker_sha256,
    value.derivation_reason,
  ];
  if (
    value.origin === "deterministic_evidence_normalizer"
    && normalizerMetadata.some((item) => item == null)
  ) {
    context.addIssue({
      code: "custom",
      message: "Normalizer finding provenance must include its complete source binding",
    });
  }
  if (
    value.origin !== "deterministic_evidence_normalizer"
    && normalizerMetadata.some((item) => item != null)
  ) {
    context.addIssue({
      code: "custom",
      message: "Provider findings cannot assert normalizer metadata",
    });
  }
}) satisfies z.ZodType<ApiSchemas["ExtractionObservation"]>;
const ProposalObservationSchema = z.strictObject({
  approval_required: z.boolean(),
  assignee_role: z.string(),
  description: z.string(),
  due_at: z.string().nullable(),
  initial_status: z.enum(["pending", "approved", "rejected", "expired", "executed"]),
  payload_hash: z.string(),
  priority: z.enum(["low", "medium", "high", "critical"]),
  source_span_ids: z.array(z.string()),
  title: z.string(),
});
const RetrievalObservationSchema = z.strictObject({
  chunk_id: z.string(),
  marker_ids: z.array(z.string()),
  rank: z.number().int().nonnegative(),
  rrf_score: z.number(),
  source_id: z.string(),
  text_rank: z.number().int().nullable().optional(),
  text_score: NullableMetricSchema,
  vector_rank: z.number().int().nullable().optional(),
  vector_similarity: NullableMetricSchema,
});
const SystemCaseOutputSchema = z.strictObject({
  answer: z.string(),
  approval_observations: z.array(ApprovalObservationSchema),
  citations: z.array(CitationObservationSchema),
  claims: z.array(ClaimObservationSchema),
  claim_provenance: z.array(ClaimProvenanceObservationSchema),
  extractions: z.array(ExtractionObservationSchema),
  observed_policy_failures: z.array(ForbiddenOutcomeSchema),
  pre_approval_execution_count: z.number().int().nonnegative(),
  pre_approval_task_count: z.number().int().nonnegative(),
  proposal: ProposalObservationSchema.nullable(),
  retrieval: z.array(RetrievalObservationSchema),
  stage_latency_ms: z.record(z.string(), z.number().nonnegative()),
  status: z.enum(["answered", "unanswerable", "approval_required"]),
  tool_trace: z.array(ToolNameSchema),
  trace_id: UuidSchema,
}).superRefine((value, context) => {
  if (value.claim_provenance.length !== value.claims.length) {
    context.addIssue({ code: "custom", message: "Claim provenance must cover every claim" });
    return;
  }
  value.claim_provenance.forEach((provenance, index) => {
    if (provenance.claim_index !== index || provenance.predicate !== value.claims[index]?.predicate) {
      context.addIssue({
        code: "custom",
        message: "Claim provenance must be ordered and match its semantic claim",
      });
    }
  });
}) satisfies z.ZodType<ApiSchemas["SystemCaseOutput"]>;

export const ProviderCallDiagnosticSchema = z.strictObject({
  call_index: z.number().int().min(1).max(5),
  phase: z.enum([
    "qa_initial",
    "qa_repair",
    "workflow_initial",
    "workflow_repair",
    "action_claim_repair",
    "binding_initial",
    "binding_repair",
  ]),
  http_status: z.number().int().min(100).max(599).nullable().optional(),
  duration_ms: z.number().finite().nonnegative(),
  response_sha256: Sha256Schema.nullable().optional(),
  validation_stage: z.enum([
    "transport",
    "protocol",
    "schema",
    "reference_binding",
    "semantic_grounding",
    "deterministic_normalization",
    "call_bound",
    "accepted",
  ]),
  validation_hint: z.enum([
    "answer_must_match_grounded_schema",
    "complete_missing_grounded_action_claim",
    "invalid_or_incomplete_json",
    "insufficient_true_requires_empty_artifacts_and_null_proposal",
    "sufficient_action_requires_exactly_one_normalized_claim",
    "claim_predicate_must_be_semantic_lower_snake_case_not_a_marker_id",
    "claim_normalized_value_must_use_lower_snake_case",
    "claim_predicate_terms_must_match_the_cited_marker",
    "action_answer_claim_and_proposal_must_share_one_chunk_and_marker",
    "claim_duration_and_trigger_must_match_the_cited_marker",
    "action_output_requires_empty_findings",
    "sufficient_action_requires_non_null_proposal",
    "proposal_due_at_must_include_timezone_or_be_null",
    "marker_must_belong_to_its_cited_chunk",
    "chunk_id_must_come_from_allowed_evidence",
    "answer_must_contain_non_whitespace_text",
    "each_structured_finding_must_preserve_complete_actor_action_and_deadline_from_its_exact_marker",
    "structured_deadline_must_match_the_exact_bounded_marker_rule",
    "output_must_match_the_complete_workflow_schema",
    "select_every_and_only_directly_requested_binding",
    "select_exactly_one_directly_requested_action_binding",
    "sufficient_action_requires_one_claim_and_proposal_title_and_description_each_express_only_the_exact_cited_action_and_regulated_subject_with_bound_due",
    "duration_tuple_mismatch",
    "duration_unit_agreement",
    "performing_actor_scope",
    "predicate_not_grounded",
    "normalized_value_not_grounded",
  ]).nullable().optional(),
  final_reason_code: z.enum([
    "generation_transport_failed",
    "generation_rejected",
    "generation_response_invalid",
    "model_schema_invalid",
    "evaluation_call_bound_exceeded",
  ]).nullable().optional(),
  raw_excerpt: z.string().max(4000).nullable().optional(),
}).superRefine((value, context) => {
  if (value.raw_excerpt != null && value.response_sha256 == null) {
    context.addIssue({
      code: "custom",
      message: "Raw provider excerpts require a response digest",
    });
  }
  if (value.validation_stage === "accepted" && value.final_reason_code != null) {
    context.addIssue({
      code: "custom",
      message: "Accepted provider calls cannot carry a terminal error code",
    });
  }
  if (value.validation_stage === "call_bound") {
    if (
      value.http_status != null
      || value.response_sha256 != null
      || value.raw_excerpt != null
      || value.duration_ms !== 0
      || value.final_reason_code !== "evaluation_call_bound_exceeded"
    ) {
      context.addIssue({
        code: "custom",
        message: "Call-bound denials cannot claim an executed provider response",
      });
    }
  } else if (value.final_reason_code === "evaluation_call_bound_exceeded") {
    context.addIssue({
      code: "custom",
      message: "Call-bound terminal reasons require the call-bound stage",
    });
  }
}) satisfies z.ZodType<ApiSchemas["ProviderCallDiagnostic"]>;

export const CaseRunResultSchema = z.strictObject({
  case_id: z.string(),
  category: CategorySchema,
  task_type: z.string(),
  output: SystemCaseOutputSchema.nullable(),
  metrics: CaseMetricsSchema.nullable(),
  failure: z.strictObject({ code: z.string(), message: z.string() }).nullable(),
  missing_capabilities: z.array(CapabilitySchema),
  provider_diagnostics: z.array(ProviderCallDiagnosticSchema).max(5),
  wall_clock_ms: z.number().nonnegative(),
}).superRefine((value, context) => {
  const diagnostics = value.provider_diagnostics;
  if (diagnostics.some((item, index) => item.call_index !== index + 1)) {
    context.addIssue({
      code: "custom",
      message: "Provider diagnostic call indexes must be contiguous and ordered",
    });
  }
  const callBoundIndexes = diagnostics.flatMap((item, index) => (
    item.validation_stage === "call_bound" ? [index] : []
  ));
  if (diagnostics.length <= 4 && callBoundIndexes.length > 0) {
    context.addIssue({
      code: "custom",
      message: "Only the denied fifth provider call may use call-bound attestation",
    });
  }

  const firstPhase = diagnostics[0]?.phase;
  if (firstPhase != null) {
    const family: Set<string> | null = firstPhase === "qa_initial"
      ? new Set(["qa_initial", "qa_repair"])
      : firstPhase === "workflow_initial"
        ? new Set([
          "workflow_initial",
          "workflow_repair",
          "action_claim_repair",
        ])
        : firstPhase === "binding_initial"
          ? new Set(["binding_initial", "binding_repair"])
          : null;
    if (family == null) {
      context.addIssue({
        code: "custom",
        message: "Provider diagnostic sequences must start with an initial phase",
      });
    } else {
      if (diagnostics.some((item) => !family.has(item.phase))) {
        context.addIssue({
          code: "custom",
          message: "Provider diagnostic sequences cannot mix request families",
        });
      }
      if (diagnostics.length === 5 && diagnostics[4]?.phase !== firstPhase) {
        context.addIssue({
          code: "custom",
          message: "The denied fifth provider call must start a new graph attempt",
        });
      }
      const measured = diagnostics.length === 5 ? diagnostics.slice(0, 4) : diagnostics;
      let index = 0;
      let graphAttempts = 0;
      while (index < measured.length) {
        if (measured[index]?.phase !== firstPhase) {
          context.addIssue({
            code: "custom",
            message: "Each provider graph attempt must start with its initial phase",
          });
          break;
        }
        graphAttempts += 1;
        index += 1;
        if (index < measured.length && measured[index]?.phase !== firstPhase) {
          index += 1;
        }
      }
      if (graphAttempts > 2) {
        context.addIssue({
          code: "custom",
          message: "Provider diagnostics cannot claim more than two graph attempts",
        });
      }
    }
  }

  if (diagnostics.length === 5) {
    const finalDiagnostic = diagnostics[4];
    if (
      callBoundIndexes.length !== 1
      || callBoundIndexes[0] !== 4
      || value.failure?.code !== "provider_call_bound_exceeded"
      || finalDiagnostic?.validation_stage !== "call_bound"
      || finalDiagnostic.final_reason_code !== "evaluation_call_bound_exceeded"
    ) {
      context.addIssue({
        code: "custom",
        message: "A fifth provider attempt must be preserved as an explicit bound failure",
      });
    }
  }
}) satisfies z.ZodType<ApiSchemas["CaseRunResult"]>;

export const EvaluationSummarySchema = z.strictObject({
  schema_version: z.string(),
  run_id: z.string(),
  dataset_version: z.string(),
  dataset_sha256: Sha256Schema,
  cases_sha256: Sha256Schema,
  canonical_manifest_sha256: Sha256Schema,
  generated_fixture_manifest_sha256: Sha256Schema,
  corpus_bundle_sha256: Sha256Schema,
  requested_provider: z.enum(["fake", "ollama"]),
  runtime_provider: z.enum(["deterministic", "ollama"]),
  provider_raw_response_capture_enabled: z.boolean(),
  runtime_model_identity: RuntimeModelIdentitySchema,
  structured_extraction_mode: z.literal("evidence_derived_binding_confirmation_v2"),
  action_proposal_mode: z.literal("evidence_derived_binding_selection_v2"),
  raw_result_sha256: Sha256Schema,
  aggregate: AggregateMetricsSchema,
  claim_provenance: ClaimProvenanceSummarySchema,
  finding_provenance: FindingProvenanceSummarySchema,
  gates: GateStatusSchema,
});
export type EvaluationSummary = z.infer<typeof EvaluationSummarySchema>;

export type EvaluationRun = ApiSchemas["EvaluationRun"];
export const EvaluationRunSchema: z.ZodType<EvaluationRun> = z.strictObject({
  schema_version: z.string(),
  run_id: z.string(),
  dataset_version: z.string(),
  dataset_sha256: Sha256Schema,
  cases_sha256: Sha256Schema,
  canonical_manifest_sha256: Sha256Schema,
  generated_fixture_manifest_sha256: Sha256Schema,
  corpus_bundle_sha256: Sha256Schema,
  requested_provider: z.enum(["fake", "ollama"]),
  runtime_provider: z.enum(["deterministic", "ollama"]),
  provider_raw_response_capture_enabled: z.boolean(),
  runtime_model_identity: RuntimeModelIdentitySchema,
  structured_extraction_mode: z.literal("evidence_derived_binding_confirmation_v2"),
  action_proposal_mode: z.literal("evidence_derived_binding_selection_v2"),
  started_at: TimestampSchema,
  completed_at: TimestampSchema,
  wall_clock_ms: z.number().nonnegative(),
  warmup_completed: z.boolean(),
  system_capabilities: z.array(CapabilitySchema),
  results: z.array(CaseRunResultSchema),
  aggregate: AggregateMetricsSchema,
  claim_provenance: ClaimProvenanceSummarySchema,
  finding_provenance: FindingProvenanceSummarySchema,
  gates: GateStatusSchema,
}).superRefine((value, context) => {
  if (
    !value.provider_raw_response_capture_enabled
    && value.results.some((result) => (
      result.provider_diagnostics.some((diagnostic) => diagnostic.raw_excerpt != null)
    ))
  ) {
    context.addIssue({
      code: "custom",
      message: "Raw provider diagnostics require an enabled capture attestation",
    });
  }
});

export const EvaluationHistoryDetailSchema = z.strictObject({
  metadata: EvaluationHistoryEntrySchema,
  current_run: EvaluationRunSchema.nullable().optional(),
  legacy_run_metadata: LegacyEvaluationRunMetadataSchema.nullable().optional(),
}) satisfies z.ZodType<ApiSchemas["EvaluationHistoryDetail"]>;
export type EvaluationHistoryDetail = z.infer<typeof EvaluationHistoryDetailSchema>;
