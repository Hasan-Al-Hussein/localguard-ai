import { z } from "zod";
import { UserSchema } from "./common";

export const LoginRequestSchema = z.object({
  username: z.string().trim().min(3, "Enter at least 3 characters").max(128),
  password: z.string().min(1, "Enter your password").max(1024),
});
export type LoginRequest = z.infer<typeof LoginRequestSchema>;

export const AuthResponseSchema = z.object({
  user: UserSchema,
  csrf_token: z.string().min(16),
});
export type AuthResponse = z.infer<typeof AuthResponseSchema>;

export const CurrentUserResponseSchema = UserSchema;

export const CsrfResponseSchema = z.object({
  csrf_token: z.string().min(16),
});
export type CsrfResponse = z.infer<typeof CsrfResponseSchema>;
