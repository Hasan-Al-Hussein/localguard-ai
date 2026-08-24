import { z } from "zod";
import type { components } from "./openapi.generated";
import { TimestampSchema, UuidSchema } from "./common";

export const DocumentStateSchema = z.enum(["queued", "processing", "ready", "failed", "deleted"]);
export type DocumentState = z.infer<typeof DocumentStateSchema>;

export const DocumentSummarySchema = z.object({
  id: UuidSchema,
  title: z.string().min(1),
  state: DocumentStateSchema,
  current_revision_id: UuidSchema.nullable(),
  created_at: TimestampSchema,
  updated_at: TimestampSchema,
});
export type DocumentSummary = z.infer<typeof DocumentSummarySchema>;

export const DocumentsResponseSchema = z.object({
  items: z.array(DocumentSummarySchema),
  total: z.number().int().nonnegative(),
  offset: z.number().int().nonnegative(),
  limit: z.number().int().positive(),
});
export type DocumentsResponse = z.infer<typeof DocumentsResponseSchema>;

export const DocumentAnchorSchema = z.object({
  id: UuidSchema,
  stable_key: z.string().min(1),
  kind: z.string().min(1),
  label: z.string().min(1),
  ordinal: z.number().int().nonnegative(),
  start_offset: z.number().int().nonnegative(),
  end_offset: z.number().int().nonnegative(),
  text: z.string(),
});
export type DocumentAnchor = z.infer<typeof DocumentAnchorSchema>;

export const DocumentRevisionSchema = z.object({
  id: UuidSchema,
  revision_number: z.number().int().positive(),
  original_filename: z.string().min(1),
  media_type: z.string().min(1),
  byte_size: z.number().int().nonnegative(),
  content_sha256: z.string().min(1),
  state: DocumentStateSchema,
  extracted_characters: z.number().int().nonnegative().nullable(),
  anchor_count: z.number().int().nonnegative().nullable(),
  created_at: TimestampSchema,
});
export type DocumentRevision = z.infer<typeof DocumentRevisionSchema>;

export const DocumentDetailSchema = DocumentSummarySchema.extend({
  current_revision: DocumentRevisionSchema.nullable(),
  anchors: z.array(DocumentAnchorSchema),
});
export type DocumentDetail = z.infer<typeof DocumentDetailSchema>;

export type RevisionSection = components["schemas"]["RevisionSectionPublic"];
export const RevisionSectionSchema: z.ZodType<RevisionSection> = z.strictObject({
  document_id: UuidSchema,
  revision_id: UuidSchema,
  anchor_key: z.string().min(1),
  anchor_label: z.string().min(1),
  kind: z.string().min(1),
  anchor_start_offset: z.number().int().nonnegative(),
  anchor_end_offset: z.number().int().nonnegative(),
  requested_start_offset: z.number().int().nonnegative(),
  requested_end_offset: z.number().int().positive(),
  text: z.string(),
});

export const UploadAcceptedSchema = z.object({
  document: DocumentSummarySchema,
  revision_id: UuidSchema,
  ingestion_job_id: z.string().nullable(),
  duplicate: z.boolean().default(false),
});
export type UploadAccepted = z.infer<typeof UploadAcceptedSchema>;
