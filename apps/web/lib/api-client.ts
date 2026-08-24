import {
  ApiErrorEnvelopeSchema,
  CsrfResponseSchema,
  type ApiErrorEnvelope,
} from "@localguard/contracts";
import type { z } from "zod";

let csrfToken: string | null = null;
let csrfRequest: Promise<string> | null = null;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly correlationId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type RequestOptions = Omit<RequestInit, "credentials"> & {
  csrf?: boolean;
};

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
  if (!token) csrfRequest = null;
}

async function parseError(response: Response): Promise<ApiError> {
  let envelope: ApiErrorEnvelope | null = null;
  try {
    envelope = ApiErrorEnvelopeSchema.parse(await response.json());
  } catch {
    // Do not expose untrusted or implementation-specific upstream error bodies.
  }

  const correlationId =
    envelope?.error.correlation_id ?? response.headers.get("x-correlation-id") ?? undefined;
  return new ApiError(
    envelope?.error.message ?? "LocalGuard could not complete the request.",
    response.status,
    envelope?.error.code ?? "request_failed",
    correlationId,
  );
}

async function parseSuccess<T>(response: Response, schema: z.ZodType<T>): Promise<T> {
  try {
    const value = response.status === 204 ? undefined : await response.json();
    return schema.parse(value);
  } catch {
    throw new ApiError(
      "The local API returned an invalid response.",
      response.status,
      "invalid_response",
      response.headers.get("x-correlation-id") ?? undefined,
    );
  }
}

async function loadCsrfToken(): Promise<string> {
  if (csrfToken) return csrfToken;
  if (!csrfRequest) {
    csrfRequest = fetch("/api/auth/csrf", {
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
      headers: { Accept: "application/json" },
    })
      .then(async (response) => {
        if (!response.ok) throw await parseError(response);
        const payload = await parseSuccess(response, CsrfResponseSchema);
        csrfToken = payload.csrf_token;
        return payload.csrf_token;
      })
      .finally(() => {
        csrfRequest = null;
      });
  }
  return csrfRequest;
}

function isStateChanging(method: string): boolean {
  return !["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase());
}

export async function apiRequest<T>(
  path: string,
  schema: z.ZodType<T>,
  options: RequestOptions = {},
): Promise<T> {
  if (!path.startsWith("/")) throw new Error("API paths must be same-origin relative paths");

  const method = (options.method ?? "GET").toUpperCase();
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (isStateChanging(method) && options.csrf !== false) {
    headers.set("X-CSRF-Token", await loadCsrfToken());
  }

  const response = await fetch(`/api${path}`, {
    ...options,
    method,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  });

  const refreshedToken = response.headers.get("x-csrf-token");
  if (refreshedToken) csrfToken = refreshedToken;
  if (!response.ok) {
    if (response.status === 401) setCsrfToken(null);
    throw await parseError(response);
  }

  return parseSuccess(response, schema);
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "An unexpected error occurred.";
}
