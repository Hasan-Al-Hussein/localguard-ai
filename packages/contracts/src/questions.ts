import { z } from "zod";
import { TimestampSchema, UuidSchema } from "./common";

export const QuestionRequestSchema = z.object({
  question: z.string().trim().min(3).max(4000),
  document_ids: z.array(UuidSchema).max(50).optional(),
});
export type QuestionRequest = z.infer<typeof QuestionRequestSchema>;

export const AnswerCitationSchema = z.object({
  id: UuidSchema,
  ordinal: z.number().int().nonnegative(),
  quote: z.string(),
  document_id: UuidSchema,
  revision_id: UuidSchema,
  anchor_key: z.string().min(1),
  anchor_label: z.string().min(1),
  start_offset: z.number().int().nonnegative(),
  end_offset: z.number().int().nonnegative(),
});
export type AnswerCitation = z.infer<typeof AnswerCitationSchema>;

export const AnswerSchema = z.object({
  id: UuidSchema,
  text: z.string(),
  insufficient_evidence: z.boolean(),
  model_name: z.string().min(1),
  prompt_version: z.string().min(1),
  retrieval_ms: z.number().nonnegative(),
  generation_ms: z.number().nonnegative(),
  created_at: TimestampSchema,
  citations: z.array(AnswerCitationSchema),
});
export type Answer = z.infer<typeof AnswerSchema>;

export const QuestionJobStateSchema = z.enum(["queued", "running", "succeeded", "failed"]);
export type QuestionJobState = z.infer<typeof QuestionJobStateSchema>;

export const QuestionJobSchema = z.object({
  id: UuidSchema,
  question: z.string().min(1),
  document_ids: z.array(UuidSchema),
  state: QuestionJobStateSchema,
  error_code: z.string().nullable(),
  error_detail: z.string().nullable(),
  created_at: TimestampSchema,
  updated_at: TimestampSchema,
  answer: AnswerSchema.nullable(),
});
export type QuestionJob = z.infer<typeof QuestionJobSchema>;
