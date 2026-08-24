import { z } from "zod";
import type { components } from "./openapi.generated";
import { TimestampSchema, UuidSchema } from "./common";

type ApiSchemas = components["schemas"];

export const WorkflowStateSchema = z.enum([
  "running",
  "waiting_approval",
  "completed",
  "rejected",
  "insufficient",
  "failed",
]);
export const ProposalStateSchema = z.enum([
  "pending",
  "approved",
  "rejected",
  "invalidated",
  "expired",
  "executed",
  "failed",
]);
export const TaskPrioritySchema = z.enum(["low", "medium", "high", "critical"]);
export const TaskStateSchema = z.enum(["open", "in_progress", "completed", "cancelled"]);
export const DecisionKindSchema = z.enum(["approve", "reject", "edit"]);

export type WorkflowRunRequest = ApiSchemas["WorkflowRunRequest"];
export const WorkflowRunRequestSchema: z.ZodType<WorkflowRunRequest> = z.strictObject({
  question: z.string().trim().min(3).max(4000),
  document_ids: z.array(UuidSchema).max(50).optional(),
});

export type WorkflowRun = ApiSchemas["WorkflowRunPublic"];
export const WorkflowRunSchema: z.ZodType<WorkflowRun> = z.strictObject({
  id: UuidSchema,
  requested_by_id: UuidSchema,
  question: z.string(),
  document_ids: z.array(UuidSchema),
  state: WorkflowStateSchema,
  intent: z.string().nullable(),
  answer_text: z.string().nullable(),
  insufficient_evidence: z.boolean().nullable(),
  cited_chunk_ids: z.array(z.string()),
  error_code: z.string().nullable(),
  error_detail: z.string().nullable(),
  created_at: TimestampSchema,
  updated_at: TimestampSchema,
});

export type WorkflowStartAccepted = ApiSchemas["WorkflowStartAccepted"];
export const WorkflowStartAcceptedSchema: z.ZodType<WorkflowStartAccepted> = z.strictObject({
  run: WorkflowRunSchema,
  dispatch_job_id: z.string().nullable(),
});

export type EvidenceReference = ApiSchemas["EvidenceReferencePublic"];
export const EvidenceReferenceSchema: z.ZodType<EvidenceReference> = z.strictObject({
  chunk_id: z.string().min(1),
  available: z.boolean(),
  document_id: UuidSchema.nullable().optional(),
  revision_id: UuidSchema.nullable().optional(),
  document_title: z.string().nullable().optional(),
  anchor_key: z.string().nullable().optional(),
  anchor_label: z.string().nullable().optional(),
  start_offset: z.number().int().nonnegative().nullable().optional(),
  end_offset: z.number().int().nonnegative().nullable().optional(),
  excerpt: z.string().nullable().optional(),
});

export const FindingOriginSchema = z.enum([
  "model",
  "deterministic_test_provider",
  "deterministic_evidence_normalizer",
]);

export const FindingSchema = z.strictObject({
  id: UuidSchema,
  workflow_run_id: UuidSchema,
  finding_type: z.string(),
  summary: z.string(),
  normalized_value: z.string().nullable(),
  responsible_party: z.string().nullable(),
  due_date: z.string().nullable(),
  severity: z.string().nullable(),
  cited_chunk_ids: z.array(z.string()),
  cited_marker_ids: z.array(z.string()),
  fields: z.record(z.string(), z.string()),
  origin: FindingOriginSchema,
  normalizer_version: z.literal("structured-obligation-binding-v2").nullable(),
  source_marker_sha256: z.string().regex(/^[0-9a-f]{64}$/).nullable().optional(),
  derivation_reason: z.literal("evidence_binding_confirmed").nullable(),
  evidence: z.array(EvidenceReferenceSchema).optional(),
  created_at: TimestampSchema,
}).superRefine((finding, context) => {
  const provenance = [
    finding.normalizer_version,
    finding.source_marker_sha256,
    finding.derivation_reason,
  ];
  if (finding.origin === "deterministic_evidence_normalizer") {
    if (provenance.some((value) => value == null)) {
      context.addIssue({
        code: "custom",
        message: "Evidence-derived findings require complete normalizer provenance",
      });
    }
    const requiredFields = ["actor", "action", "deadline"];
    if (
      Object.keys(finding.fields).sort().join(",") !== requiredFields.sort().join(",")
      || requiredFields.some((field) => !finding.fields[field]?.trim())
    ) {
      context.addIssue({
        code: "custom",
        message: "Evidence-derived findings require exact actor, action, and deadline fields",
      });
    }
    if (!finding.cited_marker_ids.some((marker) => marker.trim().length > 0)) {
      context.addIssue({
        code: "custom",
        message: "Evidence-derived findings require at least one exact source marker",
      });
    }
  } else if (provenance.some((value) => value != null)) {
    context.addIssue({
      code: "custom",
      message: "Provider findings cannot assert application normalizer provenance",
    });
  }
});
export type Finding = z.infer<typeof FindingSchema>;

export const FindingsResponseSchema = z.strictObject({
  items: z.array(FindingSchema),
  total: z.number().int().nonnegative(),
  offset: z.number().int().nonnegative(),
  limit: z.number().int().positive(),
});
export type FindingsResponse = z.infer<typeof FindingsResponseSchema>;

export type Proposal = ApiSchemas["ProposalPublic"];
export const ProposalSchema: z.ZodType<Proposal> = z.strictObject({
  id: UuidSchema,
  workflow_run_id: UuidSchema,
  created_by_id: UuidSchema,
  previous_proposal_id: UuidSchema.nullable(),
  version: z.number().int().positive(),
  kind: z.string(),
  state: ProposalStateSchema,
  title: z.string(),
  description: z.string(),
  assignee: z.string().nullable(),
  priority: TaskPrioritySchema,
  due_at: TimestampSchema.nullable(),
  reasoning_summary: z.string(),
  cited_chunk_ids: z.array(z.string()),
  evidence: z.array(EvidenceReferenceSchema).optional(),
  payload_hash: z.string().regex(/^[0-9a-f]{64}$/),
  evidence_snapshot_hash: z.string().regex(/^[0-9a-f]{64}$/),
  expires_at: TimestampSchema,
  created_at: TimestampSchema,
  updated_at: TimestampSchema,
});

export const ProposalsResponseSchema = z.strictObject({
  items: z.array(ProposalSchema),
  total: z.number().int().nonnegative(),
  offset: z.number().int().nonnegative(),
  limit: z.number().int().positive(),
}) satisfies z.ZodType<ApiSchemas["ProposalList"]>;

export type ApprovalDecisionRequest = ApiSchemas["ApprovalRequest"];
const ApprovalDecisionRequestObjectSchema = z.strictObject({
  version: z.number().int().positive(),
  payload_hash: z.string().regex(/^[0-9a-f]{64}$/),
  evidence_snapshot_hash: z.string().regex(/^[0-9a-f]{64}$/),
  comment: z.string().max(1000).nullable().optional(),
});
export const ApprovalDecisionRequestSchema: z.ZodType<ApprovalDecisionRequest> = ApprovalDecisionRequestObjectSchema;

export type ProposalEditRequest = ApiSchemas["EditRequest"];
export const ProposalEditRequestSchema: z.ZodType<ProposalEditRequest> = ApprovalDecisionRequestObjectSchema.extend({
  title: z.string().min(1).max(300).nullable().optional(),
  description: z.string().min(1).max(2000).nullable().optional(),
  assignee: z.string().max(200).nullable().optional(),
  priority: TaskPrioritySchema.nullable().optional(),
  due_at: TimestampSchema.nullable().optional(),
  reasoning_summary: z.string().min(1).max(1000).nullable().optional(),
});

export type Decision = ApiSchemas["DecisionPublic"];
export const DecisionSchema: z.ZodType<Decision> = z.strictObject({
  id: UuidSchema,
  proposal_id: UuidSchema,
  proposal_version: z.number().int().positive(),
  decided_by_id: UuidSchema,
  decision: DecisionKindSchema,
  payload_hash: z.string(),
  evidence_snapshot_hash: z.string(),
  comment: z.string().nullable(),
  replacement_proposal_id: UuidSchema.nullable(),
  decided_at: TimestampSchema,
  applied_at: TimestampSchema.nullable(),
});

export type WorkflowTask = ApiSchemas["WorkflowTaskPublic"];
export const WorkflowTaskSchema: z.ZodType<WorkflowTask> = z.strictObject({
  id: UuidSchema,
  proposal_id: UuidSchema,
  approval_decision_id: UuidSchema,
  created_by_id: UuidSchema,
  title: z.string(),
  description: z.string(),
  assignee: z.string().nullable(),
  priority: TaskPrioritySchema,
  due_at: TimestampSchema.nullable(),
  state: TaskStateSchema,
  created_at: TimestampSchema,
  updated_at: TimestampSchema,
});

export const TasksResponseSchema = z.strictObject({
  items: z.array(WorkflowTaskSchema),
  total: z.number().int().nonnegative(),
  offset: z.number().int().nonnegative(),
  limit: z.number().int().positive(),
}) satisfies z.ZodType<ApiSchemas["TaskList"]>;

export type DecisionAccepted = ApiSchemas["DecisionAccepted"];
export const DecisionAcceptedSchema: z.ZodType<DecisionAccepted> = z.strictObject({
  decision: DecisionSchema,
  proposal: ProposalSchema,
  replacement: ProposalSchema.nullable(),
  task: WorkflowTaskSchema.nullable(),
  dispatch_job_id: z.string().nullable(),
});

export type TaskPatch = ApiSchemas["TaskPatch"];
export const TaskPatchSchema: z.ZodType<TaskPatch> = z.strictObject({
  state: TaskStateSchema.nullable().optional(),
  assignee: z.string().min(1).max(200).nullable().optional(),
  priority: TaskPrioritySchema.nullable().optional(),
  due_at: TimestampSchema.nullable().optional(),
});
