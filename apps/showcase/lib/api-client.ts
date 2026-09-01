import type { z } from "zod";
import { PublicDemoApiError, publicDemoApiRequest } from "@/lib/public-demo";

type RequestOptions = Omit<RequestInit, "credentials"> & {
  csrf?: boolean;
};

export { PublicDemoApiError as ApiError };

export function apiRequest<T>(
  path: string,
  schema: z.ZodType<T>,
  options: RequestOptions = {},
): Promise<T> {
  return publicDemoApiRequest(path, schema, options);
}

export function setCsrfToken(token: string | null): void {
  void token;
}

export function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "An unexpected error occurred.";
}
