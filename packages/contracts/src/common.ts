import { z } from "zod";

export const IdentifierSchema = z.string().min(1).max(128);
export const UuidSchema = z.uuid();
export const TimestampSchema = z.string().min(1);

export const RoleSchema = z.enum(["admin", "reviewer", "viewer"]);
export type Role = z.infer<typeof RoleSchema>;

export const UserSchema = z.object({
  id: UuidSchema,
  username: z.string().min(1).max(128),
  display_name: z.string().min(1).max(160),
  role: RoleSchema,
});
export type User = z.infer<typeof UserSchema>;

export const PaginationSchema = z.object({
  page: z.number().int().positive(),
  page_size: z.number().int().positive(),
  total: z.number().int().nonnegative(),
  total_pages: z.number().int().nonnegative(),
});
export type Pagination = z.infer<typeof PaginationSchema>;

export const ApiErrorEnvelopeSchema = z.object({
  error: z.object({
    code: z.string().min(1),
    message: z.string().min(1),
    correlation_id: z.string().optional(),
    details: z.record(z.string(), z.unknown()).optional(),
  }),
});
export type ApiErrorEnvelope = z.infer<typeof ApiErrorEnvelopeSchema>;

export const ServiceHealthSchema = z.object({
  status: z.string().min(1),
  checks: z.record(z.string(), z.string()).default({}),
});
export type ServiceHealth = z.infer<typeof ServiceHealthSchema>;

export const PrioritySchema = z.enum(["low", "medium", "high", "critical"]);
export type Priority = z.infer<typeof PrioritySchema>;

export const EvidenceStatusSchema = z.enum(["strong", "partial", "insufficient"]);
export type EvidenceStatus = z.infer<typeof EvidenceStatusSchema>;
