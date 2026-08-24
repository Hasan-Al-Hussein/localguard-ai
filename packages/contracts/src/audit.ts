import { z } from "zod";
import type { components } from "./openapi.generated";
import { TimestampSchema, UuidSchema } from "./common";

type ApiSchemas = components["schemas"];

export type AuditEvent = ApiSchemas["AuditEventPublic"];
export const AuditEventSchema: z.ZodType<AuditEvent> = z.strictObject({
  id: UuidSchema,
  occurred_at: TimestampSchema,
  actor_id: UuidSchema.nullable(),
  action: z.string(),
  resource_type: z.string(),
  resource_id: UuidSchema.nullable(),
  outcome: z.string(),
  correlation_id: z.string(),
  causation_id: z.string().nullable(),
  thread_id: UuidSchema.nullable(),
  detail: z.record(z.string(), z.unknown()),
});

export const AuditEventsResponseSchema = z.strictObject({
  items: z.array(AuditEventSchema),
  total: z.number().int().nonnegative(),
  offset: z.number().int().nonnegative(),
  limit: z.number().int().positive(),
}) satisfies z.ZodType<ApiSchemas["AuditEventList"]>;

export type AuditEventsResponse = z.infer<typeof AuditEventsResponseSchema>;
