import { z } from "zod";
import type { components } from "./openapi.generated";
import { TimestampSchema, UuidSchema } from "./common";
import { DocumentSummarySchema } from "./documents";
import {
  EvaluationComparabilityStatusSchema,
  EvaluationIntegrityStatusSchema,
} from "./evaluations";

type ApiSchemas = components["schemas"];

export const DeadlineSummarySchema = z.strictObject({
  id: UuidSchema,
  workflow_run_id: UuidSchema,
  summary: z.string(),
  due_date: z.string(),
  severity: z.string().nullable(),
}) satisfies z.ZodType<ApiSchemas["DeadlineSummary"]>;

export const ActivitySummarySchema = z.strictObject({
  id: UuidSchema,
  occurred_at: TimestampSchema,
  action: z.string(),
  resource_type: z.string(),
  resource_id: UuidSchema.nullable(),
  outcome: z.string(),
  correlation_id: z.string(),
}) satisfies z.ZodType<ApiSchemas["ActivitySummary"]>;

export const EvaluationOverviewSchema = z.strictObject({
  run_id: z.string(),
  schema_version: z.string().nullable(),
  runtime_provider: z.string().nullable(),
  completed_case_count: z.number().int().nonnegative().nullable(),
  case_count: z.number().int().nonnegative().nullable(),
  safety_passed: z.boolean().nullable(),
  quality_passed: z.boolean().nullable(),
  run_passed: z.boolean().nullable(),
  integrity_status: EvaluationIntegrityStatusSchema,
  integrity_note: z.string().min(1),
  comparability_status: EvaluationComparabilityStatusSchema,
  comparability_note: z.string().min(1),
});
export type EvaluationOverview = z.infer<typeof EvaluationOverviewSchema>;

export const OverviewResponseSchema = z.strictObject({
  documents_total: z.number().int().nonnegative(),
  documents_ready: z.number().int().nonnegative(),
  documents_processing: z.number().int().nonnegative(),
  questions_total: z.number().int().nonnegative(),
  questions_failed: z.number().int().nonnegative(),
  recent_documents: z.array(DocumentSummarySchema),
  pending_approvals: z.number().int().nonnegative(),
  extracted_deadlines: z.array(DeadlineSummarySchema),
  recent_activity: z.array(ActivitySummarySchema),
  evaluation_summary: EvaluationOverviewSchema.nullable().optional(),
});
export type OverviewResponse = z.infer<typeof OverviewResponseSchema>;
